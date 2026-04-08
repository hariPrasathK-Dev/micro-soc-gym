# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import os
import subprocess
import sys
import time
import uuid
import random

def _random_ip():
    return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

from openenv.core.env_server import Environment

from models import MicroSocGymAction, MicroSocGymObservation, MicroSocGymState


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCESS_LOG = "/var/log/nginx/access.log"
AUTH_LOG = "/var/log/auth.log"
BLOCKLIST = "/etc/nginx/blocklist.conf"
WEBROOT = "/var/www/html"

# Scenario-specific attacker IPs injected by the attack scripts (defaults)
EASY_ATTACKER_IP = "10.0.0.1"
MEDIUM_ATTACKER_IP = "10.0.0.2"
HARD_ATTACKER_IP = "10.0.0.3"
MEDIUM_WHITELIST = {"10.0.0.100"}
HARD_BACKDOOR_NAME = "backdoor.php"

# Reward values
REWARD_CORRECT_BLOCK = 1.0
REWARD_FALSE_POSITIVE = 0.0
REWARD_KILL_PID = 0.5
REWARD_DELETE_FILE = 0.5
REWARD_STEP_PENALTY = 0.0
REWARD_WRONG_TOOL = 0.0
MAX_STEPS = 8


class MicroSocGymEnvironment(Environment):
    """
    Micro-SOC Gym: three cybersecurity threat scenarios for RL agents.

    Scenario routing is round-robin per reset() call:
        easy   -> detect 404 scanner, block_ip correct IP
        medium -> detect brute-force in auth.log, block correct IP without false positives
        hard   -> find webshell C2 traffic, kill_process + delete_file
    """

    _SCENARIOS = ["easy", "medium", "hard"]

    def __init__(self) -> None:
        super().__init__()
        self._scenario_index = 0
        self._state = MicroSocGymState()

        self._hard_pid_killed: bool = False
        self._hard_file_deleted: bool = False

    # ------------------------------------------------------------------
    # OpenEnv API
    # ------------------------------------------------------------------

    def reset(self) -> MicroSocGymObservation:
        """Start a new episode: pick next scenario, clean env, restart attackers."""

        scenario = self._SCENARIOS[self._scenario_index % len(self._SCENARIOS)]
        self._scenario_index += 1

        # Generate attack properties
        global EASY_ATTACKER_IP, MEDIUM_ATTACKER_IP, MEDIUM_WHITELIST, HARD_ATTACKER_IP, HARD_BACKDOOR_NAME
        EASY_ATTACKER_IP = _random_ip()
        EASY_NORMAL_IPS = [_random_ip() for _ in range(4)]
        MEDIUM_ATTACKER_IP = _random_ip()
        MEDIUM_WHITELIST = {_random_ip()}
        HARD_ATTACKER_IP = _random_ip()
        HARD_BACKDOOR_NAME = random.choice(["backdoor.php", "shell.php", "cmd.php", "wp-config.php.bak", "admin_helper.php"])
        
        # Write to env file for bash scripts
        with open("/tmp/micro_soc_state.env", "w") as f:
            f.write(f'EASY_ATTACKER_IP="{EASY_ATTACKER_IP}"\n')
            f.write(f'EASY_NORMAL_IPS=("{" ".join(EASY_NORMAL_IPS)}")\n')
            f.write(f'MEDIUM_ATTACKER_IP="{MEDIUM_ATTACKER_IP}"\n')
            f.write(f'MEDIUM_ADMIN_IP="{list(MEDIUM_WHITELIST)[0]}"\n')
            f.write(f'HARD_ATTACKER_IP="{HARD_ATTACKER_IP}"\n')
            f.write(f'HARD_BACKDOOR_NAME="{HARD_BACKDOOR_NAME}"\n')

        self._state = MicroSocGymState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            scenario=scenario,
            total_reward=0.0,
            threat_neutralised=False,
        )

        # Reset hard scenario tracking flags each episode
        self._hard_pid_killed = False
        self._hard_file_deleted = False

        # 1. Clear log files
        self._clear_file(ACCESS_LOG)
        self._clear_file(AUTH_LOG)

        # 2. Clear blocklist and reload nginx
        self._clear_file(BLOCKLIST)
        self._nginx_reload()

        # 3. Remove any planted backdoor from previous episode
        for path_name in ["backdoor.php", "shell.php", "cmd.php", "wp-config.php.bak", "admin_helper.php"]:
            backdoor = os.path.join(WEBROOT, path_name)
            if os.path.exists(backdoor):
                try:
                    os.remove(backdoor)
                except Exception:
                    pass

        # 4. Restart the correct attacker script via supervisord
        self._restart_attacker(scenario)

        # 5. Wait briefly so fresh logs are populated
        time.sleep(3)

        logs = self._read_logs(scenario)

        return MicroSocGymObservation(
            logs=logs,
            reward=0.0,
            done=False,
            success=False,
            info=f"Episode started. Scenario: {scenario}. Analyse the logs and neutralise the threat.",
        )

    def step(self, action: MicroSocGymAction) -> MicroSocGymObservation:
        """Execute one agent action, run grader, return observation."""

        self._state.step_count += 1
        scenario = self._state.scenario

        reward, done, success, feedback = self._grade(action, scenario)

        self._state.total_reward += reward
        if success:
            self._state.threat_neutralised = True

        # Timeout: max steps reached
        if self._state.step_count >= MAX_STEPS and not done:
            done = True
            feedback += f" | Episode timed out after {MAX_STEPS} steps."

        logs = self._read_logs(scenario)
        return MicroSocGymObservation(
            logs=logs,
            reward=reward,
            done=done,
            success=success,
            info=feedback,
        )

    @property
    def state(self) -> MicroSocGymState:
        return self._state

    # ------------------------------------------------------------------
    # Grader - the core reward logic
    # ------------------------------------------------------------------

    def _grade(self, action: MicroSocGymAction, scenario: str):
        """Returns (reward, done, success, feedback)."""
        
        if scenario == "easy":
            reward, done, success, feedback = self._grade_easy(action)
        elif scenario == "medium":
            reward, done, success, feedback = self._grade_medium(action)
        elif scenario == "hard":
            reward, done, success, feedback = self._grade_hard(action)
        else:
            reward, done, success, feedback = REWARD_WRONG_TOOL, False, False, "Unknown scenario."

        # Apply step penalty once
        reward += REWARD_STEP_PENALTY
        return reward, done, success, feedback

    def _grade_easy(self, action: MicroSocGymAction):
        if action.tool != "block_ip":
            return REWARD_WRONG_TOOL, False, False, "Wrong tool. Use block_ip to stop the scanner."

        ip = (action.ip_address or "").strip()

        if ip == EASY_ATTACKER_IP:
            self._block_ip(ip)
            return REWARD_CORRECT_BLOCK, True, True, f"Correct! Blocked attacker {ip}. Threat neutralised."

        if ip in MEDIUM_WHITELIST:
            return REWARD_FALSE_POSITIVE, True, False, f"False positive: {ip} is a legitimate host. Episode failed."

        return REWARD_WRONG_TOOL, False, False, f"Blocked {ip} but that is not the attacker. Check the logs."

    def _grade_medium(self, action: MicroSocGymAction):
        if action.tool != "block_ip":
            return REWARD_WRONG_TOOL, False, False, "Wrong tool. Check auth.log and use correct tool."

        ip = (action.ip_address or "").strip()

        if ip in MEDIUM_WHITELIST:
            return REWARD_FALSE_POSITIVE, True, False, (
                f"False positive! {ip} is a whitelisted admin IP. Do NOT block it. Episode failed."
            )

        if ip == MEDIUM_ATTACKER_IP:
            self._block_ip(ip)
            return REWARD_CORRECT_BLOCK, True, True, f"Correct! Blocked brute-force attacker {ip}."

        return REWARD_WRONG_TOOL, False, False, f"Blocked {ip} - not the attacker. Re-read auth.log."

    def _grade_hard(self, action: MicroSocGymAction):
        backdoor_path = os.path.join(WEBROOT, HARD_BACKDOOR_NAME)
        backdoor_exists = os.path.exists(backdoor_path)

        if action.tool == "kill_process":
            pid = action.pid
            if pid is None:
                return REWARD_WRONG_TOOL, False, False, "Provide a pid to kill_process."
            killed = self._kill_process(pid)
            if killed:
                self._hard_pid_killed = True
                partial = " Now delete the malicious file." if backdoor_exists else ""
                r = REWARD_KILL_PID
            else:
                r = REWARD_WRONG_TOOL
                partial = f" PID {pid} not found or already gone."
            done, success = self._hard_check_complete()
            return r, done, success, f"kill_process({pid}): {'OK' if killed else 'FAILED'}.{partial}"

        elif action.tool == "delete_file":
            path = (action.file_path or "").strip()
            if path == backdoor_path and backdoor_exists:
                os.remove(backdoor_path)
                self._hard_file_deleted = True
                partial = " Now kill the attacker process." if not self._hard_pid_killed else ""
                done, success = self._hard_check_complete()
                return REWARD_DELETE_FILE, done, success, f"Deleted {path}.{partial}"
            elif not backdoor_exists:
                return REWARD_WRONG_TOOL, False, False, "Backdoor already gone or wrong path."
            else:
                return REWARD_WRONG_TOOL, False, False, f"{path} is not the backdoor. Look for .php files."

        else:
            return REWARD_WRONG_TOOL, False, False, "Use kill_process or delete_file for this scenario."

    def _hard_check_complete(self):
        if self._hard_pid_killed and self._hard_file_deleted:
            return True, True
        return False, False

    # ------------------------------------------------------------------
    # System actions
    # ------------------------------------------------------------------

    def _block_ip(self, ip: str) -> None:
        """Append deny rule to blocklist and reload nginx."""
        with open(BLOCKLIST, "a") as f:
            f.write(f"deny {ip};\n")
        self._nginx_reload()

    def _kill_process(self, pid: int) -> bool:
        """Kill pid. Returns True if pid is gone after the attempt."""
        try:
            proc_cmdline = f"/proc/{pid}/cmdline"
            proc_status  = f"/proc/{pid}/status"

            # Validate the PID exists before attempting anything
            if not os.path.exists(proc_status):
                print(f"[KILL] pid={pid} does not exist", file=sys.stderr, flush=True)
                return False

            try:
                with open(proc_cmdline, "rb") as f:
                    cmdline = f.read().replace(b"\x00", b" ").decode(errors="replace").strip()
                print(f"[KILL] pid={pid} cmdline={cmdline!r}", file=sys.stderr, flush=True)
            except OSError:
                cmdline = "<unknown>"
                print(f"[KILL] pid={pid} cmdline unreadable", file=sys.stderr, flush=True)

            import signal
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[KILL] sent SIGKILL to {pid}", file=sys.stderr, flush=True)
            except ProcessLookupError:
                print(f"[KILL] pid={pid} already gone", file=sys.stderr, flush=True)

            r = subprocess.run(
                ["supervisorctl", "stop", "hard_attack"],
                capture_output=True, text=True, timeout=5
            )
            print(f"[KILL] supervisorctl stop: rc={r.returncode} out={r.stdout.strip()!r}", file=sys.stderr, flush=True)

            time.sleep(1.0)

            if not os.path.exists(proc_status):
                print(f"[KILL] result=True (proc gone)", file=sys.stderr, flush=True)
                return True

            try:
                with open(proc_status) as f:
                    state_line = next((l for l in f if l.startswith("State:")), "")
                print(f"[KILL] state_after={state_line.strip()!r}", file=sys.stderr, flush=True)
                return "Z" in state_line
            except OSError:
                return True

        except Exception as e:
            print(f"[KILL] exception: {e}", file=sys.stderr, flush=True)
            return False

    def _nginx_reload(self) -> None:
        try:
            subprocess.run(["nginx", "-s", "reload"], capture_output=True, timeout=5)
        except Exception:
            pass

    def _restart_attacker(self, scenario: str) -> None:
        """Stop all attacker processes, start only the one for this scenario."""
        for s in self._SCENARIOS:
            try:
                subprocess.run(
                    ["supervisorctl", "stop", f"{s}_attack"],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
        try:
            subprocess.run(
                ["supervisorctl", "start", f"{scenario}_attack"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    def _clear_file(self, path: str) -> None:
        try:
            with open(path, "w") as f:
                f.write("")
        except Exception:
            pass

    def _read_logs(self, scenario: str) -> str:
        """Return the relevant log tail depending on scenario."""
        log_file = AUTH_LOG if scenario == "medium" else ACCESS_LOG
        try:
            result = subprocess.run(
                ["tail", "-n", "50", log_file],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout or "(log empty - attacker may not have fired yet)"
        except Exception:
            return "(could not read log file)"
