import os
import json
from typing import List
from openai import OpenAI

from models import MicroSocGymAction
from client import MicroSocGymClient
from server.constants import MAX_STEPS, SCENARIOS

# Environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

TEMPERATURE = 0.5 # Set to 0.5 to make sure model is balanced between creativity and determinism

# Utility function to extract tool JSON from model response
def extract_json(text: str) -> str:
    import re

    # First try to extract JSON from markdown code blocks
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        candidate = match.group(1)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    
    # If markdown fence based etraction fails, extract by searching for JSON-like substrings and validate them
    candidates = []
    for i, ch in enumerate(text):
        if ch == "{":
            depth = 0
            for j, c in enumerate(text[i:], start=i):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1

                if depth == 0:
                    candidate = text[i:j + 1]
                    try:
                        json.loads(candidate)
                        candidates.append(candidate)
                    except json.JSONDecodeError:
                        pass
                    break

    if candidates:
        return max(candidates, key=len)

    return "{}"


def main():
    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL) # Connect to model API

    env_client = MicroSocGymClient(base_url="http://localhost:7860") # Connect to local environment server (docker container)

    # Runs the full episode loop for each scenario
    for scenario_idx in range(len(SCENARIOS)):
        obs = env_client.reset() # Resets environment to start a new episode

        scenario_name = SCENARIOS[scenario_idx]
        benchmark = "micro-soc-gym" # Hardcoded benchmark name as only one benchmark written for now

        # Emit [START] log with scenario and model info
        print(f"[START] task={scenario_name} env={benchmark} model={MODEL_NAME}", flush=True)

        step_idx = 0
        rewards: List[float] = []
        action_history: List[str] = []

        done = obs.get("done", False)
        success = obs.get("success", False)

        # Get the initial alert info to give context to the agent and append to action_history
        initial_info = obs.get("info", "")
        if initial_info:
            action_history.append(f"Step 0: {initial_info}")

        # Exits loop when episode is done / expires / errors out
        while not done and step_idx < MAX_STEPS:
            step_idx += 1

            # Main system prompt with agent context, tool descriptions and instructions
            system_prompt = (
                "You are an expert Security Operations Center (SOC) analyst."
                "Your job is to investigate web server logs and take exactly ONE action per turn until the threat is neutralised.\n\n"

                "BEFORE ACTING - CHECK YOUR HISTORY FIRST:\n"
                "The action history contains the full output and feedback of all previous actions including logs."
                "If logs have already been read, do NOT read them again - extract the evidence you need directly from action history. "
                "Only read a log if it has not been read yet in this episode.\n\n"

                "Available tools:\n\n"
                "  read_access_log()\n"
                "    - Reads the web server access log.\n"
                "    - Use ONCE to investigate potential web-based attacks.\n\n"
                "  read_auth_log()\n"
                "    - Reads the system authentication log.\n"
                "    - Use ONCE to investigate potential brute-force or unauthorized login attempts.\n\n"
                "  block_ip(ip_address: str)\n"
                "    - Adds an IP to the firewall blocklist.\n"
                "    - Use when you see a single IP causing repeated suspicious traffic.\n"
                '    - Requires field: "ip_address" (string)\n\n'
                "  kill_process(pid: int)\n"
                "    - Sends SIGKILL to a running process by its PID.\n"
                "    - Use when a process is actively running malicious commands from within the server.\n"
                '    - The PID appears as a bracketed integer in the user-agent field, e.g. "AppleWebKit/537.36 [1234]" means PID=1234.\n'
                "    - Extract the PID from the logs. Do NOT guess.\n"
                '    - Requires field: "pid" (integer)\n\n'
                "  delete_file(file_path: str)\n"
                "    - Permanently removes a file from the filesystem.\n"
                "    - Use when a malicious file has been planted on the server.\n"
                "    - Always use the FULL absolute path e.g. /var/www/html/shell.php.\n"
                '    - Requires field: "file_path" (string)\n\n'

                "Output ONLY a single raw JSON object. No markdown fences, no explanation."
            )

            # Calculates cumulative reward and gets action_history_str for prompt
            action_history_str = "\n".join(action_history) if action_history else "None"
            current_total_reward = sum(rewards)
            
            # Passes action_history, cumulative reward and available tools in the prompt for the agent to decide next action
            prompt = (
                f"Action History:\n{action_history_str}\n\n"
                f"Total Reward So Far: {current_total_reward:.2f}\n\n"
                f"Choose the single best action. Output ONLY valid JSON, one of:\n"
                f'  {{"tool": "read_access_log"}}\n'
                f'  {{"tool": "read_auth_log"}}\n'
                f'  {{"tool": "block_ip", "ip_address": "<ip>"}}\n'
                f'  {{"tool": "kill_process", "pid": <integer>}}\n'
                f'  {{"tool": "delete_file", "file_path": "<absolute_path>"}}\n'
            )

            action_str = ""
            error_msg = "null"
            reward = 0.00
            inner_info = ""

            try:
                # Sends prompt to model and fetches response
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=TEMPERATURE,
                )
                
                # Gets respnse content and extracts actin from JSON
                raw_content = response.choices[0].message.content or ""
                action_str = extract_json(raw_content)
                action_dict = json.loads(action_str)
                action = MicroSocGymAction(**action_dict)

                # Extracts action param values
                action_kwargs = {"tool": action.tool}
                if action.ip_address:
                    action_kwargs["ip_address"] = action.ip_address
                if action.file_path:
                    action_kwargs["file_path"] = action.file_path
                if action.pid is not None:
                    action_kwargs["pid"] = action.pid

                obs = env_client.step(**action_kwargs) # Calls the step function to run the action in the environment

                # Gets results of the step function
                reward = obs.get("reward", 0.0)
                done = obs.get("done", False)
                success = obs.get("success", False)
                inner_info = obs.get("info", "")

            except Exception as e:
                # If an error occurs, we end the episode cleanly and log the msg
                error_msg = str(e).replace("\n", " ")
                action_str = action_str or "{}"
                reward = -1.0
                done = True
                inner_info = "Error: " + error_msg

            rewards.append(reward)

            action_log = (action_str.replace("\n", "").replace("\r", "") if action_str else "{}")

            # Appends action and its result to action_history for future context
            is_action_read_log = '"read_' in action_log

            # If it is a remediation action, then info is "Feedback", else its the logs itself, so "Information" is used 
            info_prefix = "Information:\n" if is_action_read_log else "Feedback: " 

            action_history.append(
                f"Step {step_idx}: Action: {action_log} -> Reward: {reward:.2f} | {info_prefix}{inner_info}"
            )

            # Emit [STEP] log
            print(
                f"[STEP] step={step_idx} "
                f"action={action_log} "
                f"reward={reward:.2f} "
                f"done={str(done).lower()} "
                f"error={error_msg}",
                flush=True,
            )

        # Creates the rewards string showing all rewards obtained in the episode
        rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"

        # Grades the episode and fetches the final score
        grade = env_client.grade_episode()
        score = grade["score"]

        # Emit [END] log
        print(
            f"[END] success={str(success).lower()} "
            f"steps={step_idx} "
            f"score={score:.2f} "
            f"rewards={rewards_str}",
            flush=True,
        )


if __name__ == "__main__":
    main()