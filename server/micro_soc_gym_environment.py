# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import os
import time
import uuid
import random

from openenv.core.env_server import Environment

from models import MicroSocGymAction, MicroSocGymObservation, MicroSocGymState
from server.constants import (
    SCENARIOS,
    ACCESS_LOG_PATH,
    AUTH_LOG_PATH,
    IP_BLOCKLIST_PATH,
    WEBROOT_PATH,
    BACKDOOR_FILE_NAMES,
    MAX_STEPS,
    CORRECT_ACTION_REWARD,
    PARTIAL_ACTION_REWARD,
    FATAL_ACTION_PENALTY,
    WRONG_TOOL_PENALTY,
)
from server.utils import (
    clear_file,
    nginx_reload,
    kill_process,
    restart_attacker,
    block_ip,
    is_ip_blocked,
    check_hard_attack_process,
    random_ip,
    read_logs,
)


class MicroSocGymEnvironment(Environment):
    def __init__(self) -> None:
        super().__init__()
        self._scenario_index = 0
        self._state = MicroSocGymState()

    def _clear_previous_environment(self):
        clear_file(ACCESS_LOG_PATH)
        clear_file(AUTH_LOG_PATH)
        clear_file(IP_BLOCKLIST_PATH)
        nginx_reload()

        if os.path.exists("/tmp/micro_soc_state.env"):
            try:
                os.remove("/tmp/micro_soc_state.env")
            except Exception:
                pass

        if os.path.exists("/tmp/.hard_attack_active"):
            try:
                os.remove("/tmp/.hard_attack_active")
            except Exception:
                pass

        for path_name in BACKDOOR_FILE_NAMES:
            backdoor = os.path.join(WEBROOT_PATH, path_name)
            if os.path.exists(backdoor):
                try:
                    os.remove(backdoor)
                except Exception:
                    pass

    def _generate_scenario_attack_properties(self, scenario: str):
        self.attacker_ip = None
        self.normal_ips = []
        self.admin_ip = set()
        self.backdoor_file_name = None

        with open("/tmp/micro_soc_state.env", "w") as f:
            if scenario == "easy":
                self.attacker_ip = random_ip()
                self.normal_ips = [random_ip() for _ in range(4)]
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'NORMAL_IPS=("{" ".join(self.normal_ips)}")\n')
            elif scenario == "medium":
                self.attacker_ip = random_ip()
                self.admin_ip = {random_ip()}
                while list(self.admin_ip)[0] == self.attacker_ip:
                    self.admin_ip = {random_ip()}
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'ADMIN_IP="{list(self.admin_ip)[0]}"\n')
            elif scenario == "hard":
                self.attacker_ip = random_ip()
                self.backdoor_file_name = random.choice(BACKDOOR_FILE_NAMES)
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'BACKDOOR_FILE_NAME="{self.backdoor_file_name}"\n')

    def reset(self) -> MicroSocGymObservation:
        scenario = SCENARIOS[self._scenario_index % len(SCENARIOS)]
        self._scenario_index += 1

        self._state = MicroSocGymState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            scenario=scenario,
            total_reward=0.0,
            threat_neutralised=False,
            investigated=False,
        )

        self._last_tool = None
        self._used_tools = set()

        self._clear_previous_environment()
        self._generate_scenario_attack_properties(scenario)
        restart_attacker(scenario, SCENARIOS)

        time.sleep(3)

        alert = "Alert: A threat has been detected. Analyse and neutralise the threat."
        if scenario == "easy":
            alert = "Alert: External monitoring has detected an unusual spike in HTTP traffic and bandwidth consumption on the primary web server. Analyse and neutralise the root cause."
        elif scenario == "medium":
            alert = "Alert: Endpoint detection has flagged an anomalous pattern of authentication events and minor CPU spikes tied to remote access services. Analyse and neutralise the root cause."
        elif scenario == "hard":
            alert = "Alert: Network monitors have detected persistent, suspicious traffic originating from within the web application itself. Analyse and neutralise the root cause."

        return MicroSocGymObservation(
            reward=0.0,
            done=False,
            success=False,
            info=f"Episode started. {alert}",
        )

    def step(self, action: MicroSocGymAction) -> MicroSocGymObservation:
        self._state.step_count += 1
        scenario = self._state.scenario

        reward, done, success, info = self._calculate_reward(action, scenario)

        self._state.total_reward += reward
        if success:
            self._state.threat_neutralised = True

        if self._state.step_count >= MAX_STEPS and not done:
            done = True
            info += f" | Episode timed out after {MAX_STEPS} steps."

        return MicroSocGymObservation(
            reward=reward,
            done=done,
            success=success,
            info=info,
        )

    @property
    def state(self) -> MicroSocGymState:
        return self._state

    def _calculate_reward(self, action: MicroSocGymAction, scenario: str):
        last_tool = getattr(self, "_last_tool", None)
        self._last_tool = action.tool

        if not hasattr(self, "_used_tools"):
            self._used_tools = set()

        if action.tool in ("read_access_log", "read_auth_log"):
            if action.tool in self._used_tools:
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    "Logs are unchanged. You have already investigated and read the logs. Focus on what the system is still doing.",
                )
            remediation_tools = {"block_ip", "delete_file", "kill_process"}
            if remediation_tools.issubset(self._used_tools):
                self._used_tools.add(action.tool)
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    "You have already investigated and attempted remediation. Focus on what the system is still doing.",
                )

        self._used_tools.add(action.tool)

        if action.tool == "read_access_log":
            self._state.investigated = True
            logs = read_logs(ACCESS_LOG_PATH)

            if scenario in ["easy", "hard"]:
                reward = (
                    0.0 if last_tool == "read_access_log" else CORRECT_ACTION_REWARD
                )
                return reward, False, False, f"Here are the Access Logs:\n{logs}"
            else:
                reward = (
                    0.0 if last_tool == "read_access_log" else PARTIAL_ACTION_REWARD
                )
                return (
                    reward,
                    False,
                    False,
                    f"Wrong logfile accessed.",
                )

        if action.tool == "read_auth_log":
            self._state.investigated = True
            logs = read_logs(AUTH_LOG_PATH)

            if scenario == "medium":
                reward = 0.0 if last_tool == "read_auth_log" else CORRECT_ACTION_REWARD
                return reward, False, False, f"Here are the Auth Logs:\n{logs}"
            else:
                reward = 0.0 if last_tool == "read_auth_log" else PARTIAL_ACTION_REWARD
                return (
                    reward,
                    False,
                    False,
                    f"Wrong logfile accessed.",
                )

        if not self._state.investigated:
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "You must investigate the logs first before taking remediation actions.",
            )

        if scenario == "easy":
            reward, done, success, info = self._calculate_reward_easy(action)
        elif scenario == "medium":
            reward, done, success, info = self._calculate_reward_medium(action)
        elif scenario == "hard":
            reward, done, success, info = self._calculate_reward_hard(action)
        else:
            reward, done, success, info = (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Unknown scenario.",
            )

        return reward, done, success, info

    def _calculate_reward_easy(self, action: MicroSocGymAction):
        if action.tool != "block_ip":
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Wrong tool. Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

        ip = (action.ip_address or "").strip()

        if ip == self.attacker_ip:
            block_ip(ip)
            return (
                CORRECT_ACTION_REWARD,
                True,
                True,
                f"CORRECT! Attacker IP - {ip} is blocked. Threat neutralised.",
            )

        return (
            PARTIAL_ACTION_REWARD,
            False,
            False,
            f"Blocked {ip}, but that is not the attacker. Re-check the logs.",
        )

    def _calculate_reward_medium(self, action: MicroSocGymAction):
        if action.tool != "block_ip":
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Wrong tool. Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

        ip = (action.ip_address or "").strip()

        if ip in self.admin_ip:
            return (
                FATAL_ACTION_PENALTY,
                True,
                False,
                f"FATAL! {ip} is the admin IP and should not be blocked. Episode failed.",
            )

        if ip == self.attacker_ip:
            block_ip(ip)
            return (
                CORRECT_ACTION_REWARD,
                True,
                True,
                f"CORRECT! Brute force attacker IP - {ip} is blocked. Threat neutralised.",
            )

        return (
            PARTIAL_ACTION_REWARD,
            False,
            False,
            f"Blocked {ip}, but that is not the attacker. Re-check the logs.",
        )

    def _get_hard_scenario_hint(
        self, backdoor_exists: bool, process_alive: bool, ip_blocked: bool
    ) -> str:
        if not backdoor_exists and ip_blocked and process_alive:
            return f"IP blocked and backdoor removed. However, requests to /{self.backdoor_file_name} are still being generated from within the server itself. Investigate the source."

        hints = []
        if not ip_blocked:
            hints.append("suspicious external traffic is still being received")
        if backdoor_exists:
            hints.append("an unauthorized file is still present in the web root")
        if process_alive:
            hints.append(
                "anomalous outbound requests are still being generated from the server"
            )
        return (
            "Threat still active: "
            + ", ".join(hints)
            + ". Re-examine your observations."
        )

    def _calculate_reward_hard(self, action: MicroSocGymAction):
        backdoor_path = os.path.join(WEBROOT_PATH, self.backdoor_file_name)
        backdoor_exists = os.path.exists(backdoor_path)

        if action.tool == "block_ip":
            ip = (action.ip_address or "").strip()

            if is_ip_blocked(ip):
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    f"IP {ip} is already blocked. Re-check the logs for other indicators of compromise and choose the right action.",
                )

            if ip == self.attacker_ip:
                block_ip(ip)

                process_alive = check_hard_attack_process()
                done = not os.path.exists(backdoor_path) and not process_alive
                hint = self._get_hard_scenario_hint(
                    os.path.exists(backdoor_path), process_alive, True
                )
                return (
                    CORRECT_ACTION_REWARD,
                    done,
                    done,
                    f"CORRECT! Attacker IP - {ip} is blocked. {'Threat neutralised.' if done else hint}",
                )

            return (
                PARTIAL_ACTION_REWARD,
                False,
                False,
                f"Wrong IP {ip} blocked. Re-check the logs and choose the right IP.",
            )

        elif action.tool == "kill_process":
            pid = action.pid

            if pid is None:
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    "No PID provided to kill_process.",
                )

            killed = kill_process(pid)

            if killed:
                process_alive = check_hard_attack_process()
                if not process_alive:
                    ip_blocked = is_ip_blocked(self.attacker_ip)
                    done = not os.path.exists(backdoor_path) and ip_blocked
                    hint = self._get_hard_scenario_hint(
                        os.path.exists(backdoor_path), False, ip_blocked
                    )
                    return (
                        CORRECT_ACTION_REWARD,
                        done,
                        done,
                        f"CORRECT! PID {pid} is killed. {'Threat neutralised.' if done else hint}",
                    )
                else:
                    return (
                        WRONG_TOOL_PENALTY,
                        False,
                        False,
                        f"Process {pid} killed, but it was not the malicious process. Re-check the logs and choose the right action.",
                    )
            else:
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    f"Process {pid} may already be dead or not found or could not be killed.",
                )

        elif action.tool == "delete_file":
            path = (action.file_path or "").strip()

            if path == backdoor_path and backdoor_exists:
                os.remove(backdoor_path)
                self._file_deleted = True

                process_alive = check_hard_attack_process()
                ip_blocked = is_ip_blocked(self.attacker_ip)
                done = not process_alive and ip_blocked

                hint = self._get_hard_scenario_hint(False, process_alive, ip_blocked)

                return (
                    CORRECT_ACTION_REWARD,
                    done,
                    done,
                    f"CORRECT! Backdoor file {path} deleted. {'Threat neutralised.' if done else hint}",
                )
            elif not backdoor_exists and path == backdoor_path:
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    "Backdoor file not found or already deleted.",
                )
            else:
                return (
                    WRONG_TOOL_PENALTY,
                    False,
                    False,
                    "Wrong file deleted. Re-check the logs and identify the right file to delete.",
                )

        else:
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

    def grade_episode(self, scenario: str) -> float:
        score = 0.0

        if scenario == "easy":
            if is_ip_blocked(self.attacker_ip):
                score = 0.99

        elif scenario == "medium":
            if is_ip_blocked(self.attacker_ip):
                score = 0.99

        elif scenario == "hard":
            backdoor_file = self.backdoor_file_name

            if is_ip_blocked(self.attacker_ip):
                score += 0.33

            if backdoor_file:
                path = os.path.join(WEBROOT_PATH, backdoor_file)
                if not os.path.exists(path):
                    score += 0.33

            if not check_hard_attack_process():
                score += 0.33

        if score <= 0.0:
            return 0.01
        if score >= 1.0:
            return 0.99
        return score
