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
    HARD_ATTACK_FLAG_FILE_PATH,
    PID_FILE_PATH,
    MAX_STEPS,
    CORRECT_ACTION_REWARD,
    CORRECT_INVESTIGATIVE_DIRECTION_REWARD,
    CORRECT_TOOL_WRONG_TARGET_REWARD,
    NON_INVESTIGATIVE_REMEDIATION_ACTION_PENALTY,
    ADMIN_IP_BLOCK_PENALTY,
    WRONG_FILE_DELETION_PENALTY,
    WRONG_TOOL_PENALTY,
    UNWARRANTED_ACTION_REPEAT_PENALTY,
    ACTION_TO_STALL_PENALTY,
    PROCESS_KILL_FAIL_PENALTY,
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


# Environment class for micro-soc-gym
class MicroSocGymEnvironment(Environment):
    def __init__(self) -> None:
        super().__init__()
        self._scenario_index = 0
        self._state = MicroSocGymState()

    # Helper method that clears the environment for new episode
    def _clear_previous_environment(self):
        # Clears the logs, blocklist and restarts nginx
        clear_file(ACCESS_LOG_PATH)
        clear_file(AUTH_LOG_PATH)
        clear_file(IP_BLOCKLIST_PATH)
        nginx_reload()

        # Deletes the state env file with attack properties
        if os.path.exists("/tmp/micro_soc_state.env"):
            try:
                os.remove("/tmp/micro_soc_state.env")
            except Exception:
                pass
           
        # Deletes the hard attack flag file
        if os.path.exists(HARD_ATTACK_FLAG_FILE_PATH):
            try:
                os.remove(HARD_ATTACK_FLAG_FILE_PATH)
            except Exception:
                pass
        
        # Deletes the hard attack process PID file
        if os.path.exists(PID_FILE_PATH):
            try:
                os.remove(PID_FILE_PATH)
            except Exception:
                pass
        
        # Deletes any backdoor files that may be present in the webroot
        for path_name in BACKDOOR_FILE_NAMES:
            backdoor = os.path.join(WEBROOT_PATH, path_name)
            if os.path.exists(backdoor):
                try:
                    os.remove(backdoor)
                except Exception:
                    pass
    
    # Helper method to generate attack properties for each scenario and save them to the state env
    def _generate_scenario_attack_properties(self, scenario: str):
        self.attacker_ip = None
        self.normal_ips = []
        self.admin_ip = set()
        self.backdoor_file_name = None

        with open("/tmp/micro_soc_state.env", "w") as f:
            # Generates attaker IP and normal IPs for the easy scenario and writes to the state env file
            if scenario == "easy":
                self.attacker_ip = random_ip()
                self.normal_ips = [random_ip() for _ in range(4)]
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'NORMAL_IPS=("{" ".join(self.normal_ips)}")\n')

            # Generates attacker IP and admin IP for the medium scenario and writes to the state env file
            elif scenario == "medium":
                self.attacker_ip = random_ip()
                self.admin_ip = {random_ip()}
                while list(self.admin_ip)[0] == self.attacker_ip:
                    self.admin_ip = {random_ip()}
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'ADMIN_IP="{list(self.admin_ip)[0]}"\n')
            
            # Generates attacker IP and backdoor file name for the hard scenario and writes to the state env file
            elif scenario == "hard":
                self.attacker_ip = random_ip()
                self.backdoor_file_name = random.choice(BACKDOOR_FILE_NAMES)
                f.write(f'ATTACKER_IP="{self.attacker_ip}"\n')
                f.write(f'BACKDOOR_FILE_NAME="{self.backdoor_file_name}"\n')

    # Reset method to start a new episode
    def reset(self) -> MicroSocGymObservation:
        scenario = SCENARIOS[self._scenario_index % len(SCENARIOS)]
        self._scenario_index += 1

        # Sets the state for the new episode
        self._state = MicroSocGymState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            scenario=scenario,
            total_reward=0.0,
            threat_neutralised=False,
            investigated=False,
            episode_done=False,
        )

        self._used_tools = set() # Create set to track used tools in the episode

        # Clears the environment, generates the attack properties for the scenario and starts the attack
        self._clear_previous_environment()
        self._generate_scenario_attack_properties(scenario)
        restart_attacker(scenario, SCENARIOS)

        # Waits for the initial logs to be generated
        time.sleep(3)

        # Sets the initial observation and alert based on the scenario
        alert = "Alert: A threat has been detected. Analyse and neutralise the threat."
        if scenario == "easy":
            alert = "Alert: External monitoring has detected an unusual spike in HTTP traffic and bandwidth consumption on the primary web server. Analyse and neutralise the root cause."
        elif scenario == "medium":
            alert = "Alert: Endpoint detection has flagged an anomalous pattern of authentication events and minor CPU spikes tied to remote access services. Analyse and neutralise the root cause."
        elif scenario == "hard":
            alert = "Alert: Network monitors have detected persistent, suspicious traffic originating from within the web application itself. Analyse and neutralise the root cause."

        # Returns the observation for step 0 (initial reset)
        return MicroSocGymObservation(
            reward=0.0,
            done=False,
            success=False,
            info=f"Episode started. {alert}",
        )

    # Step method that executes an action and returns its results and a new observation
    def step(self, action: MicroSocGymAction) -> MicroSocGymObservation:
        # Guard against post-episode calls
        if self._state.episode_done:
            return MicroSocGymObservation(
                reward=0.0,
                done=True,
                success=self._state.threat_neutralised,
                info="Episode is already over. Call reset() to start a new episode.",
            )

        self._state.step_count += 1
        reward, done, success, info = self._calculate_reward(action, scenario)

        self._state.total_reward += reward
        if success:
            self._state.threat_neutralised = True

        if self._state.step_count >= MAX_STEPS and not done:
            done = True
            info += f" | Episode timed out after {MAX_STEPS} steps."

        if done:
            self._state.episode_done = True    # ← set the flag

        return MicroSocGymObservation(
            reward=reward,
            done=done,
            success=success,
            info=info,
        )

    # Property to get the current state of the environment
    @property
    def state(self) -> MicroSocGymState:
        return self._state

    # Helper methods to calculate the reward for an action
    # The only part that gave me a logical headache while building the whole thing
    # So many edge cases and ways agent tries to beat the system (impressive work by the model lol...)
    def _calculate_reward(self, action: MicroSocGymAction, scenario: str):
        if not hasattr(self, "_used_tools"):
            self._used_tools = set() # Creates the _used_tools set to keep track of tools used in the episode

        if action.tool in ("read_access_log", "read_auth_log"):
            # If the agent tries reading the same log file again, penalty given as it's and attempt to game the system
            # Agent re reading same logs consecutively like read_access_log, read_access_log,... is handled later below
            # But agent then decided to read_access_log, read_auth_log, read_access_log, read_auth_log..... (lowkey clever)
            # So this prevents the agent from re-reading logs by penalising it (UNWARRANTED_ACTION_REPEAT_PENALTY)
            # But what if the agent needs logs for context for taking multiple steps?
            # Well, action_history which is passed to the agent every time will contain the logs from the first read, so it can use that as context for the scenario
            if action.tool in self._used_tools:
                return (
                    UNWARRANTED_ACTION_REPEAT_PENALTY,
                    False,
                    False,
                    "Logs are unchanged. You have already investigated and read the logs. Focus on what the system is still doing.",
                )
            
            # If the agent tries reading a different logfile after executing all remediation actions atleast once
            # This is basically the agent stalling as it already has all the information it needs, and is executing the remediation actions incorrectly 
            # So agent is penalised with ACTION_TO_STALL_PENALTY 
            remediation_tools = {"block_ip", "delete_file", "kill_process"}
            if remediation_tools.issubset(self._used_tools): # If all the remediation tools are in the used tools set
                self._used_tools.add(action.tool)
                return (
                    ACTION_TO_STALL_PENALTY,
                    False,
                    False,
                    "You have already investigated and attempted remediation. Focus on what the system is still doing.",
                )

        self._used_tools.add(action.tool) # Adds tool to set once used

        # Investigative action taken - Read the access log
        if action.tool == "read_access_log":
            self._state.investigated = True # Sets investegated to True as logs are read atleast once
            logs = read_logs(ACCESS_LOG_PATH) # Gets the access logs from the environment

            # Easy and hard scenarios needs access log to investigate the attack, not auth log 
            if scenario in ["easy", "hard"]:
                 # Since its the correct action, CORRECT_ACTION_REWARD is given
                return CORRECT_ACTION_REWARD, False, False, f"Here are the Access Logs:\n{logs}"
            else:
                # Partial reward as wrong logfile chosen but direction of investigation is correct
                return (
                    CORRECT_INVESTIGATIVE_DIRECTION_REWARD,
                    False,
                    False,
                    f"Wrong logfile accessed.",
                )

        # Investigative action taken - Read the auth log
        if action.tool == "read_auth_log":
            self._state.investigated = True # Sets investegated to True as logs are read atleast once
            logs = read_logs(AUTH_LOG_PATH) # Gets the auth logs from the environment

            # Medium scenario needs the auth log to investigate the attack, not access log
            if scenario == "medium":
                # Since its the correct action, CORRECT_ACTION_REWARD is given
                return CORRECT_ACTION_REWARD, False, False, f"Here are the Auth Logs:\n{logs}"
            else:
                # Partial reward as wrong logfile chosen but direction of investigation is correct
                return (
                    CORRECT_INVESTIGATIVE_DIRECTION_REWARD,
                    False,
                    False,
                    f"Wrong logfile accessed.",
                )

        # Penalise the agent for executing a remediation action without ever investigating the alert
        # Agent will just try to wing through the whole episode, hence no point continuing...
        if not self._state.investigated:
            return (
                NON_INVESTIGATIVE_REMEDIATION_ACTION_PENALTY,
                True,
                False,
                "Episode FAILED! You must investigate the logs first before taking remediation actions.",
            )

        # Calculating the reward for the agent based on the action and the scenario
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

    # Calculates the reward for the action taken in the easy scenario
    # Correct action: Block_IP
    def _calculate_reward_easy(self, action: MicroSocGymAction):
        # Wrong tool used, so penalty given and feedback given
        if action.tool != "block_ip":
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Wrong tool. Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

        ip = (action.ip_address or "").strip()

        # If block_ip tool is used and the attacker IP is what is blocked, then CORRECT_ACTION_REWARD is given
        # Threat is neutralised and episode is marked done 
        if ip == self.attacker_ip:
            block_ip(ip)
            return (
                CORRECT_ACTION_REWARD,
                True,
                True,
                f"CORRECT! Attacker IP - {ip} is blocked. Threat neutralised.",
            )

        # If block_ip tool is used but the IP blocked is not the attacker IP, then CORRECT_TOOL_WRONG_TARGET_REWARD is given
        # Tool choice is correct but wrong IP is blocked, so feedback is given accordingly
        return (
            CORRECT_TOOL_WRONG_TARGET_REWARD,
            False,
            False,
            f"Blocked {ip}, but that is not the attacker. Re-check the logs.",
        )

    # Calculates the reward for the action taken in the medium scenario
    # Correct action: Block_IP (But Admin IP must not be blocked -> FATAL as system may crash)
    def _calculate_reward_medium(self, action: MicroSocGymAction):
        # Wrong tool used, so penalty given and feedback given
        if action.tool != "block_ip":
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Wrong tool. Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

        ip = (action.ip_address or "").strip()

        # If admin IP is blocked, then ADMIN_IP_BLOCK_PENALTY is given as it is very important to the system
        if ip in self.admin_ip:
            return (
                ADMIN_IP_BLOCK_PENALTY,
                False,
                False,
                f"FATAL! {ip} is the admin IP and should not be blocked. System stability is compromised.",
            )

        # If attacker IP is blocked, then CORRECT_ACTION_REWARD is given
        # Threat is neutralised and episode is marked done
        if ip == self.attacker_ip:
            block_ip(ip)
            return (
                CORRECT_ACTION_REWARD,
                True,
                True,
                f"CORRECT! Brute force attacker IP - {ip} is blocked. Threat neutralised.",
            )

        # If block_ip tool is used but the IP blocked is not the attacker IP, then CORRECT_TOOL_WRONG_TARGET_REWARD is given
        # Tool choice is correct but wrong IP is blocked, so feedback is given accordingly
        return (
            CORRECT_TOOL_WRONG_TARGET_REWARD,
            False,
            False,
            f"Blocked {ip}, but that is not the attacker. Re-check the logs.",
        )
    
    # Helper method to generate hints for the hard scenario based on the current state of the attack
    def _get_hard_scenario_hint(
        self, backdoor_exists: bool, process_alive: bool, ip_blocked: bool
    ) -> str:
        # Agent kept messing up by blocking the IP and deleting the backdoor file but not killing the process
        # This exact situation is kinda why this method even exists
        # This small help did the trick suprisingly
        if not backdoor_exists and ip_blocked and process_alive:
            return f"IP blocked and backdoor removed. However, requests to /{self.backdoor_file_name} are still being generated from within the server itself. Investigate the source."

        # For any other combination of attack state, generates compiled hints
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

    # Calculates the reward for the action taken in the hard scenario
    # Correct action: Block_IP, Delete_File, Kill_Process (Specifically Kill_Process must be done only after Delete_File to prevent re-spawn)
    # Frankly, this was not as hard as I thought, very lengthy though as 3 tools have to be used... Maybe a bit complicated
    def _calculate_reward_hard(self, action: MicroSocGymAction):
        backdoor_path = os.path.join(WEBROOT_PATH, self.backdoor_file_name)
        backdoor_exists = os.path.exists(backdoor_path)
        
        # If block_ip tools is used
        if action.tool == "block_ip":
            ip = (action.ip_address or "").strip()

            # If IP was already blocked (agent already executed this tool in a previous step) then penalise it
            # Another way the agent tried to game the system by lowkey just blocking IP again and again
            if is_ip_blocked(ip):
                return (
                    UNWARRANTED_ACTION_REPEAT_PENALTY,
                    False,
                    False,
                    f"IP {ip} is already blocked. Re-check the logs for other indicators of compromise and choose the right action.",
                )

            # If the attacker IP is blocked, then CORRECT_ACTION_REWARD is given
            if ip == self.attacker_ip:
                block_ip(ip) # Blocks the attacker IP
                
                # Episode is only done if backdoor is also deleted and process is killed before this
                process_alive = check_hard_attack_process()
                done = not os.path.exists(backdoor_path) and not process_alive

                hint = self._get_hard_scenario_hint(os.path.exists(backdoor_path), process_alive, True)
                return (
                    CORRECT_ACTION_REWARD,
                    done,
                    done,
                    f"CORRECT! Attacker IP - {ip} is blocked. {'Threat neutralised.' if done else hint}",
                )

            # If block_ip tool is used but the IP blocked is not the attacker IP, then CORRECT_TOOL_WRONG_TARGET_REWARD is given
            # Tool choice is correct but wrong IP is blocked, so feedback is given accordingly
            return (
                CORRECT_TOOL_WRONG_TARGET_REWARD,
                False,
                False,
                f"Wrong IP {ip} blocked. Re-check the logs and choose the right IP.",
            )

        # If kill_process tool is used
        elif action.tool == "kill_process":
            pid = action.pid

            # Kills the process with the given PID 
            killed = kill_process(pid)

            # If process killing is successful
            if killed:
                # Checks if the hard_attack script is still alive
                process_alive = check_hard_attack_process()

                # If it was killed then this action was successful and CORRECT_ACTION_REWARD is given
                if not process_alive:

                    # Episode is only done if backdoor is also deleted and IP is blocked before this
                    ip_blocked = is_ip_blocked(self.attacker_ip)
                    done = not os.path.exists(backdoor_path) and ip_blocked
                    
                    hint = self._get_hard_scenario_hint(os.path.exists(backdoor_path), False, ip_blocked)
                    return (
                        CORRECT_ACTION_REWARD,
                        done,
                        done,
                        f"CORRECT! PID {pid} is killed. {'Threat neutralised.' if done else hint}",
                    )
                
                # If hard_attack script is alive and running then wrong PID was given, so CORRECT_TOOL_WRONG_TARGET_REWARD is given and feedback is given
                else:
                    return (
                        CORRECT_TOOL_WRONG_TARGET_REWARD,
                        False,
                        False,
                        f"Process {pid} killed, but it was not the malicious process. Re-check the logs and choose the right action.",
                    )
            # If process killing is not successful, then penalty is given and feedback is given
            else:
                return (
                    PROCESS_KILL_FAIL_PENALTY,
                    False,
                    False,
                    f"Process {pid} may already be dead or not found or could not be killed.",
                )

        # If delete_file tool is used
        elif action.tool == "delete_file":
            path = (action.file_path or "").strip()

            # If the backdoor file path is used and the backdoor still exists before deletion
            # This is correct so CORRECT_ACTION_REWARD is given
            if path == backdoor_path and backdoor_exists:
                os.remove(backdoor_path) # Deletes the backdoor

                # Episode is only done if process is killed and IP is blocked before this
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

            # If backdoor file doesn't exist but the agent tries to delete it, then it is an attempt to game the system
            # So, UNWARRANTED_ACTION_REPEAT_PENALTY is given and feedback is provided accordingly  
            # The agent didn't do this, but seeing it trying that with block_ip, added it here as a safeguard as well
            elif not backdoor_exists and path == backdoor_path:
                return (
                    UNWARRANTED_ACTION_REPEAT_PENALTY,
                    False,
                    False,
                    "Backdoor file not found or already deleted.",
                )
            
            # If a wrong file is attempted to be deleted, then that is very bad, but data is still recoverable so not as bad as FATAL
            # WRONG_FILE_DELETION_PENALTY is given and feedback is given accordingly
            else:
                return (
                    WRONG_FILE_DELETION_PENALTY,
                    False,
                    False,
                    "Wrong file deleted. Re-check the logs and identify the right file to delete.",
                )

        # If an invalid tool is used
        else:
            return (
                WRONG_TOOL_PENALTY,
                False,
                False,
                "Re-analyse the logs and identify the type of attack and choose the right tool.",
            )

    # Method that grades the episode after it is marked done
    # This method disregards the method and steps that the agent took. 
    # It's only goal is to check the current state of the environment to see if the agent succeeded.
    # (After episode ends, is the threat actually neutralised?) A kind of verification...
    def grade_episode(self, scenario: str) -> float:
        score = 0.0

        # For easy attack scenario, if the attacker IP is blocked then gives the highest score
        if scenario == "easy":
            if is_ip_blocked(self.attacker_ip):
                score = 0.99

        # For medium attack scenario, if the attacker IP is blocked then gives the highest score
        elif scenario == "medium":
            if is_ip_blocked(self.attacker_ip):
                score = 0.99

        # 3 things to check for the hard attack scenario 
        #   - IP should be blocked
        #   - Backdoor must be deleted
        #   - Process must be killed
        # Each carries an equal score of 0.33
        elif scenario == "hard":
            backdoor_file = self.backdoor_file_name

            # If IP is blocked, then 0.33 is awarded
            if is_ip_blocked(self.attacker_ip):
                score += 0.33

            # If Backdoor file doesnt exist, then 0.33 is awarded
            if backdoor_file:
                path = os.path.join(WEBROOT_PATH, backdoor_file)
                if not os.path.exists(path):
                    score += 0.33

            # If hard_attack process is dead, then 0.33 is awarded
            if not check_hard_attack_process():
                score += 0.33

        # Final score of an episode must lie in (0,1) exclusive
        # Hence highest score is 0.99 and lowest is 0.01
        if score <= 0.0:
            return 0.01
        if score >= 1.0:
            return 0.99
            
        return score
