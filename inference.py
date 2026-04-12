import os
import re
import json
from typing import List
from openai import OpenAI

from models import MicroSocGymAction
from client import MicroSocGymClient
from server.constants import MAX_STEPS, SCENARIOS

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN")

TEMPERATURE  = 0.5


def extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        candidate = match.group(1)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

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
    client     = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)
    env_client = MicroSocGymClient(base_url="http://localhost:7860")

    for scenario_idx in range(len(SCENARIOS)):
        obs           = env_client.reset()
        scenario_name = SCENARIOS[scenario_idx]
        benchmark     = "micro-soc-gym"

        print(f"[START] task={scenario_name} env={benchmark} model={MODEL_NAME}", flush=True)

        step_idx       = 0
        rewards: List[float] = []
        action_history: List[str] = []

        # FIX 1: obs fields are flat — no "observation" wrapper
        done    = obs.get("done", False)
        success = obs.get("success", False)

        initial_info = obs.get("info", "")
        if initial_info:
            action_history.append(f"Step 0: {initial_info}")

        while not done and step_idx < MAX_STEPS:
            step_idx += 1

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

            action_history_str   = "\n".join(action_history) if action_history else "None"
            current_total_reward = sum(rewards)

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

            # FIX 3: initialise inner_info before try so it's always in scope
            action_str = ""
            error_msg  = "null"
            reward     = 0.00
            inner_info = ""

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=TEMPERATURE,
                )

                raw_content = response.choices[0].message.content or ""
                action_str  = extract_json(raw_content)
                action_dict = json.loads(action_str)
                action      = MicroSocGymAction(**action_dict)

                action_kwargs = {"tool": action.tool}
                if action.ip_address:
                    action_kwargs["ip_address"] = action.ip_address
                if action.file_path:
                    action_kwargs["file_path"] = action.file_path
                if action.pid is not None:
                    action_kwargs["pid"] = action.pid

                obs = env_client.step(**action_kwargs)

                # FIX 1: flat field access — no "observation" nesting
                reward     = obs.get("reward", 0.0)
                done       = obs.get("done", False)
                success    = obs.get("success", False)
                inner_info = obs.get("info", "")

            except Exception as e:
                error_msg  = str(e).replace("\n", " ")
                action_str = action_str or "{}"
                reward     = -1.0
                done       = True

            rewards.append(reward)

            action_log      = action_str.replace("\n", "").replace("\r", "") if action_str else "{}"
            is_action_read_log = '"read_' in action_log
            info_prefix     = "Information:\n" if is_action_read_log else "Feedback: "

            action_history.append(
                f"Step {step_idx}: Action: {action_log} -> Reward: {reward:.2f} | {info_prefix}{inner_info}"
            )

            print(
                f"[STEP] step={step_idx} "
                f"action={action_log} "
                f"reward={reward:.2f} "
                f"done={str(done).lower()} "
                f"error={error_msg}",
                flush=True,
            )

        rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"

        # FIX 2: grade_episode takes no args and returns a dict
        grade = env_client.grade_episode()
        score = grade["score"]

        print(
            f"[END] success={str(success).lower()} "
            f"steps={step_idx} "
            f"score={score:.2f} "
            f"rewards={rewards_str}",
            flush=True,
        )


if __name__ == "__main__":
    main()