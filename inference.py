import json
import os
import re
import sys
from typing import List

from openai import OpenAI

from models import MicroSocGymAction
from client import MicroSocGymClient

# ---------------------------------------------------------------------------
# Required Environment Configuration via os.getenv
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or "EMPTY"

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
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
    
    # We must connect to the live Docker Environment (The "World") via HTTP
    # This prevents Windows executing Linux specific background logic.
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
            prompt = (
                f"You are an AI Security Operations Center (SOC) analyst.\n"
                f"Current Threat Scenario: {task_name}\n\n"
                f"Logs from the server:\n{logs_content}\n\n"
                f"Feedback from last action: {inner_info}\n\n"
                f"You must resolve the threat by taking an action. Your output must be ONLY a valid JSON object. Do NOT include markdown blocks.\n"
                f"Valid actions (tools) are:\n"
                f"1. block_ip: requires 'ip_address' (string)\n"
                f"2. delete_file: requires 'file_path' (string)\n"
                f"3. kill_process: requires 'pid' (int)\n\n"
                f"Example JSON format:\n"
                f"{{\"tool\": \"block_ip\", \"ip_address\": \"10.0.0.1\"}}\n"
            )

            action_str = ""
            error_msg = "null"
            reward = 0.00
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a helpful security agent that ONLY outputs raw valid JSON."},
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
                # The agent failed severely (likely syntax error), step ends 
                # but we give it a chance to try again next step unless MAX_STEPS reached
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
