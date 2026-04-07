import json
import os
import re
import sys
from typing import List

from openai import OpenAI

from models import MicroSocGymAction
from server.micro_soc_gym_environment import MicroSocGymEnvironment

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
    
    # Instantiate the custom OpenEnv environment directly
    env = MicroSocGymEnvironment()

    # The environment has exactly 3 specific scenarios.
    # We will trigger all 3 sequentially to get the baseline for the entire benchmark.
    for scenario_idx in range(3):
        obs = env.reset()
        task_name = env.state.scenario

        # Skip hard scenario if disabled (e.g. Windows dev mode prevents backdoor.php)
        if "disabled" in obs.info.lower():
            continue

        # Emit [START] event
        print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)

        step_idx = 0
        rewards: List[float] = []
        done = obs.done
        success = obs.success
        
        while not done and step_idx < MAX_STEPS:
            step_idx += 1
            
            prompt = (
                f"You are an AI Security Operations Center (SOC) analyst.\n"
                f"Current Threat Scenario: {task_name}\n\n"
                f"Logs from the server:\n{obs.logs}\n\n"
                f"Feedback from last action: {obs.info}\n\n"
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
                
                # Step the environment
                obs = env.step(action)
                
                reward = obs.reward
                rewards.append(reward)
                done = obs.done
                success = obs.success

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
        score = env.state.total_reward
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
