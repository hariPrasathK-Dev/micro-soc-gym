import os
import re
import json
from typing import List

from openai import OpenAI

from models import MicroSocGymAction
from client import MicroSocGymClient

# ---------------------------------------------------------------------------
# Required Environment Configuration via os.getenv
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

BENCHMARK = os.getenv("MY_ENV_V4_BENCHMARK", "micro_soc_gym")
MAX_STEPS = 8
TEMPERATURE = 0.7


def extract_json(text: str) -> str:
    """Extract JSON object from LLM output, handling markdown blocks."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return "{}"


def main():
    # Instantiate the OpenAI client
    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)
    
    # We must connect to the live Docker Environment via HTTP
    env_client = MicroSocGymClient(base_url="http://localhost:7860")

    # The environment has exactly 3 specific scenarios.
    for scenario_idx in range(3):
        obs = env_client.reset()
        
        inner_info = obs.get("observation", {}).get("info", "")
        
        # Extract scenario from the initial info string
        task_name = "easy"
        if "Scenario: medium" in inner_info:
            task_name = "medium"
        elif "Scenario: hard" in inner_info:
            task_name = "hard"

        # Skip hard scenario if disabled
        if "disabled" in inner_info.lower():
            continue

        # Emit [START] event
        print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)

        step_idx = 0
        rewards: List[float] = []
        done = obs.get("done", False)
        success = obs.get("observation", {}).get("success", False)
        
        while not done and step_idx < MAX_STEPS:
            step_idx += 1
            
            logs_content = obs.get("observation", {}).get("logs", "")

            system_prompt = (
                "You are an expert Security Operations Center (SOC) analyst. "
                "Your job is to investigate server logs and take exactly ONE remediation action per turn.\n\n"
                "Available tools and their descriptions:\n\n"
                "  block_ip(ip_address: str)\n"
                "    - Adds an IP to the firewall blocklist.\n"
                "    - Use when you see a single IP causing suspicious repeated traffic.\n"
                "    - Requires field: \"ip_address\" (string)\n\n"
                "  kill_process(pid: int)\n"
                "    - Sends SIGKILL to a running process by its PID.\n"
                "    - Use when a process is actively running malicious commands or a webshell.\n"
                "    - The PID usually appears as a bracketed integer in the log user-agent field, "
                "e.g. \"AppleWebKit/537.36 [1234]\" means PID=1234. Do NOT guess random PIDs.\n"
                "    - Requires field: \"pid\" (integer)\n\n"
                "  delete_file(file_path: str)\n"
                "    - Permanently removes a file from the filesystem.\n"
                "    - Use when a malicious file has been planted on the server.\n"
                "    - Always use the FULL absolute filesystem path. (Hint: access logs often show paths relative to the web server's document root. You must infer the absolute path based on standard Linux web server configurations).\n"
                "    - Requires field: \"file_path\" (string)\n\n"
                "Take one action per turn and continue until the threat is neutralised.\n\n"
                "Output ONLY a single raw JSON object. No markdown fences, no explanation."
            )

            prompt = (
                f"Scenario: {task_name}\n\n"
                f"Last action feedback: {inner_info}\n\n"
                f"Current server logs:\n{logs_content}\n\n"
                f"Choose the single best action. Output ONLY valid JSON, one of:\n"
                f'  {{"tool": "block_ip", "ip_address": "<ip>"}}\n'
                f'  {{"tool": "delete_file", "file_path": "<absolute_path>"}}\n'
                f'  {{"tool": "kill_process", "pid": <integer>}}\n'
            )

            action_str = ""
            error_msg = "null"
            reward = 0.00
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=TEMPERATURE,
                )
                
                raw_content = response.choices[0].message.content or ""
                action_str = extract_json(raw_content)
                
                # Parse to ensure it conforms to our Environment's Pydantic schema
                action_dict = json.loads(action_str)
                action = MicroSocGymAction(**action_dict)
                
                # Step the environment via the proxy client payload
                action_kwargs = {"tool": action.tool}
                if action.ip_address: action_kwargs["ip_address"] = action.ip_address
                if action.file_path: action_kwargs["file_path"] = action.file_path
                if action.pid is not None: action_kwargs["pid"] = action.pid

                obs = env_client.step(**action_kwargs)
                
                reward = obs.get("reward", 0.0)
                rewards.append(reward)
                done = obs.get("done", False)
                success = obs.get("observation", {}).get("success", False)
                inner_info = obs.get("observation", {}).get("info", "")

            except Exception as e:
                # Catch validation layers (e.g., Pydantic parsing errors)
                error_msg = str(e).replace('\n', ' ')
                action_str = action_str or "{}"
                reward = 0.0
                rewards.append(reward)
                done = False

            # Format action string cleanly for single-line STDOUT
            action_log = action_str.replace('\n', '').replace('\r', '') if action_str else "{}"
            
            # Emit [STEP] event
            print(
                f"[STEP] step={step_idx} "
                f"action={action_log} "
                f"reward={reward:.2f} "
                f"done={str(done).lower()} "
                f"error={error_msg}", 
                flush=True
            )

        # End of Episode
        score = sum(rewards)
        rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
        
        # Emit [END] event
        print(
            f"[END] success={str(success).lower()} "
            f"steps={step_idx} "
            f"score={score:.2f} "
            f"rewards={rewards_str}", 
            flush=True
        )


if __name__ == "__main__":
    main()
