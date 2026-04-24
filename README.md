# Micro SOC Gym

**Micro SOC Gym** models a real time Security Operations Center (SOC). It simulates the SOC workload to evaluate Reinforcement Learning (RL) agents. Rather than interacting with static datasets, agents interact with a real time, monolithic Docker container running the environment.

The environment runs a FastAPI backend, simulated daemons (`nginx`, `sshd`), and the orchestrated attacker scripts. Agents perform threat triage just like real analysts. They parse unstructured server log streams, map threats and execute remediation actions.

<img alt="Micro SOC Gym" src="https://img.shields.io/badge/OpenEnv-Compatible-blue.svg">


## Motivation

In modern Security Operations Centers (SOCs), human analysts are generally overwhelmed by the volume of daily alerts. Because of this workload, anything that isn't automated can slip through, leaving networks vulnerable. 

To safely automate this triage process, we need capable AI systems that are trained on such scenarios. This is why we chose to build Micro SOC Gym.

Standard LLM benchmarks test static multi-choice or simple generation capabilities. Micro SOC Gym forces the agent into a proactive role. It challenges the agent's ability to:

1. Handle **noisy data** streams (identifying key evidence amidst decoy traffic).
2. Understand constraints and **avoid overly aggressive actions** that can cause system failures.
3. Sequentially build and execute a **multi-step remediation** plan.


## Getting Started

1. Clone the repository and navigate to the project directory:
   
   ```bash
   git clone https://github.com/hariPrasathK-Dev/micro-soc-gym.git
   cd micro-soc-gym
   ```

2. Build the Docker Image:

   ```bash
   docker build -t micro-soc-gym .
   ```

3. Run the Docker container:

   ```bash
   docker run -d -p 7860:7860 micro-soc-gym
   ```

4. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate     # Windows: .\.venv\Scripts\activate
   ```

5. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Set your Hugging Face Hub Credentials:

   ```bash
   export HF_TOKEN="<YOUR_HUGGING_FACE_TOKEN>"
   ```

7. Run the Inference Script:

   ```bash
   python inference.py
   ```

You can access the **Gradio Dashboard** at `http://localhost:7860/`

## Environment

The environment is based on the standard **OpenEnv** HTTP JSON schema patterns defined through Pydantic definitions.

### Observation Space

State observations are sent continuously to the agent via the `MicroSocGymObservation` payload:

- **`reward`**: Immediate reinforcement mapping to the agent's recent action (-ve/0.0/+ve) to help it understand the effect of the action.
- **`done`**: Marks if the episode is terminated or not based on success, failure, or max-steps exhaustion.
- **`success`**: Indicates if the active threat has been fully neutralised or not.
- **`info`**: Tool output and grader feedback with context hints.

### Action Space

The `MicroSocGymAction` requires specifying exactly one `tool` per step, categorised into Investigative and Remediation tools:

**Investigative Tools:**
1. **`read_access_log()`**:  Reads `/var/log/nginx/access.log` to parse web server traffic.
2. **`read_auth_log()`**: Reads `/var/log/auth.log` to monitor system authentication events

**Remediation Tools:**
1. **`block_ip(ip_address)`**: Blocks the specified IP by explicitly adding it to `/etc/nginx/blocklist.conf`.
2. **`kill_process(pid)`**: Transmits a system-level `SIGKILL` to forcefully terminate the specified process.
3. **`delete_file(file_path)`**: Permanently deletes the specified file from the host disk layer.

### Reward and Penalty Logic

After running the episodes of each scenario over and over with different models, we discovered tricks and patterns that were used by the agent to cheat and game the system. 

After a lot of experimentation and testing, we settled on this reward structure:

|   Value   | Name                                           | Note                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| :-------: | :--------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **0.50**  | `CORRECT_ACTION_REWARD`                        | Given if the agent executes the correct tool with correct target.                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **0.25**  | `CORRECT_INVESTIGATIVE_DIRECTION_REWARD`       | Partial reward for choosing the wrong logfile, but still a reward as the agent did make the correct decision to investigate.                                                                                                                                                                                                                                                                                                                                                                                     |
| **0.10**  | `CORRECT_TOOL_WRONG_TARGET_REWARD`             | Given when the tool choice is correct for the scenario but the wrong target is provided. For example, blocking the wrong IP or killing the wrong process PID.                                                                                                                                                                                                                                                                                                                                                    |
| **-0.20** | `PROCESS_KILL_FAIL_PENALTY`                    | Given when the process kill fails to execute. This usually happens if the process is already dead or the PID is wrong.                                                                                                                                                                                                                                                                                                                                                                                           |
| **-0.25** | `ACTION_TO_STALL_PENALTY`                      | Given when the agent tries reading logfiles after executing all possible remediation actions.<br><br>Introduced when we saw the agent re-execute investigative tools after trying out all the remediation tools at least once. This is basically the agent stalling as it already has the information it needs, but is executing the remediation actions incorrectly.                                                                                                                                            |
| **-0.30** | `UNWARRANTED_ACTION_REPEAT_PENALTY`            | Given when the agent unnecessarily repeats actions to game the system.<br><br>Introduced when we saw the agent read the same logs consecutively to keep gaining rewards. When a simple penalty on consecutive repeat was implemented, the agent started reading logfiles in an alternate pattern (like `read_access_log`, `read_auth_log`, `read_access_log`...). Agents could also re-block the same IP again and again, to gain rewards. <br><br>This penalty prevents the agent from exploiting such actions. |
| **-0.50** | `WRONG_TOOL_PENALTY`                           | Given when the agent chooses the wrong tool for the given scenario.                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **-0.75** | `WRONG_FILE_DELETION_PENALTY`                  | Given when the agent deletes the wrong file. Data is still recoverable so it isn't completely fatal, but it is a severe mistake.                                                                                                                                                                                                                                                                                                                                                                                 |
| **-1.00** | `ADMIN_IP_BLOCK_PENALTY`                       | Given when the admin IP is blocked. This is a FATAL penalty, as the system is compromised.                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **-1.00** | `NON_INVESTIGATIVE_REMEDIATION_ACTION_PENALTY` | Given when the agent executes a remediation action without ever investigating the alert. This means that the agent will just try to guess through the whole episode without looking at any logs.                                                                                                                                                                                                                                                                                                                 |

### Forced Termination Conditions

The episode is forced to terminate immediately if any of the following conditions are met:

| Condition                              | Explanation                                                                                                                                                                                      |
| :------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Max Steps Exhausted**                | If the agent has used all the allotted steps without resolving the threat, then the episode ends with no success.                                                                                |
| **Non Investigative Remediation**      | The agent attempts a remediation action without ever reading a log. If the agent's strategy from step one is to blindly guess, then there is point in continuing the episode.                    |
| **Cumulative Penalty Below Threshold** | If the agent's total reward drops below a set threshold (Default: `-3.0`). This indicates that the agent has gone fully down the wrong path and further steps would not help resolve the threat. |

### Tasks

| Difficulty | Name & Mechanics                                                                                                                                                               | Win Condition                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| :--------: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  **Easy**  | **Directory Brute Forcing**<br>A single IP generates a massive amount of `HTTP 404` errors by brute forcing hidden admin pages                                                 | Find the malicious IP in `access.log` and call `block_ip(Attacker_IP)` to block it.                                                                                                                                                                                                                                                                                                                                                                         |
| **Medium** | **SSH Brute Force**<br>An attacker brute forces the server with failed SSH login attempts but legitimate admin traffic happens simultaneously.                                 | Identify the attacker's IP and call `block_ip(Attacker_IP)`.<br><br>However, if the agent accidentally blocks the legitimate admin subnet, it triggers a very high _False Positive_  penalty.                                                                                                                                                                                                                                                               |
|  **Hard**  | **Active C2 Backdoor**<br>An attacker IP drops a malicious file (backdoor) on the webserver. Base64-encoded commands are actively sent from the backdoor to running processes. | Identify the backdoor file and delete it using `delete_file(BACKDOOR_FILE)`. Find the malicious process and kill it using `kill_process(PROCESS)`. Find the attacker IP and block it using `block_ip(Attacker_IP)`.<br><br>The agent must first remove the payload using `delete_file(FILE)` to prevent re-spawn of the malicious process. Only then, it must kill the running mailcious process. Executing any one or two action will not stop the attack. |


## System Architecture

```text
+-------------------------------------------------------------+
|                     OpenEnv Framework                       |
|  +-----------------+                 +-------------------+  |
|  |     RL Agent    |  <---JSON--->   |   inference.py    |  |
|  |      (Qwen)     |                 | (OpenEnv harness) |  |
|  +-----------------+                 +-------------------+  |
+-------------------------------------------------------------+
                               |
                               | (HTTP/REST via Port 7860)
                               v
+-------------------------------------------------------------+
|                       Docker Container                      |
|                                                             |
|  +=======================================================+  |
|  |                   Supervisord (Init)                  |  |
|  +=======================================================+  |
|       |                     |                    |          |
|       v                     v                    v          |
| +-----------+       +---------------+    +---------------+  |
| |   NGINX   | <-----+    Attacker   |    |  SSH/Auth Log |  |
| | Webserver |       |    Scripts    +--->|     (Mock)    |  |
| +-----------+       +---------------+    +---------------+  |
|       |              (easy/med/hard)             |          |
|       +-------------------+----------------------+          |
|                           | (Log Streams)                   |
|                           v                                 |
|  +=======================================================+  |
|  |                 FastAPI (server/app.py)               |  |
|  |-------------------------------------------------------|  |
|  |                Micro SOC Gym Environment              |  |
|  |                                                       |  |
|  |  +----------------+  +--------------+  +-----------+  |  |
|  |  | Log Aggregator |  | Rules/Grader |  |   Gradio  |  |  |
|  |  | (access/auth)  |  |    Engine    |  | Dashboard |  |  |
|  |  +----------------+  +--------------+  +-----------+  |  |
|  +=======================================================+  |
+-------------------------------------------------------------+
```

## Project Structure

```text
micro_soc_gym/
├── .github/
│   └── workflows/
│       └── sync-to-hf.yml            # GitHub Actions workflow to sync repo to Hugging Face Space
├── media/                            # Static assets for documentation
├── scripts/                          # Script files to generate attacks
├── server/                           # OpenEnv Backend Services
│   ├── ui/                           # Gradio UI components
│   ├── __init__.py                   # Package initializer
│   ├── app.py                        # FastAPI endpoints and Gradio Telemetry Dashboard
│   ├── constants.py                  # Shared constant values and definitions
│   ├── micro_soc_gym_environment.py  # Builds the OpenEnv environment, Grading and Reward logic
│   └── utils.py                      # Reusable utilities and helper functions
├── __init__.py                       # Package initializer
├── client.py                         # Synchronous HTTP validation client
├── Dockerfile                        # Environment runtime manifest & OS provisions
├── inference.py                      # Automated LLM ReAct agent testing loop
├── LICENSE                           # MIT License File
├── models.py                         # Application-layer Pydantic schema exports
├── nginx-default                     # Nginx server configuration defaults and simulated routing
├── openenv.yaml                      # OpenEnv space requirement configuration
├── pyproject.toml                    # Python package configuration
├── README.md                         # Documentation
├── requirements.txt                  # Python dependencies
├── schema.json                       # Validation schema for standard OpenEnv JSON interactions
├── supervisord.conf                  # Daemon management orchestrator (Nginx, API, Attacks)
├── uv.lock                           # Locked dependency versions (uv)
└── validate-submission.sh            # Local strict validation helper script
```


## Inference Results

The environment tests models across the different scenarios. Below is an evaluation run using the `Qwen/Qwen2.5-72B-Instruct` model via our inference script.

![Inference Results for Qwen 72B model](/media/inference.png)

It shows the agent successfully read the environment state and called the correct tools. It **achieves the maximum score** of `0.99` in each scenario, resolving all the threats.

## Gradio Dashboard

To help understand the environment, we built an interactive Gradio Dashboard. The dashboard is available at `http://localhost:7860/` when the docker container is run. 

It lets the user manually play the role of an agent. They can read logs, execute actions, and see how the environment scores them. This lets the user understand the mechanics, constraints, and underlying reward logic that the Agent has to learn.

https://github.com/user-attachments/assets/80c28b86-2f0f-4ad8-a383-8d50048c1a43


## Pre-Validation Results

Before deploying, we ran the environment through the Pre-Validation Script. **Everything passed**, including the Docker build, Hugging Face Space liveness, and schema checks.

![OpenEnv Pre-Validation Success Output](/media/pre-validation.png)


## The Team

| Name            | GitHub ID                                               |
| --------------- | ------------------------------------------------------- |
| Adithya Menon R | [adithya-menon-r](https://github.com/adithya-menon-r)   |
| Harinie C B     | [harinie-4466](https://github.com/harinie-4466)         |
| Hari Prasath K  | [hariPrasathK-Dev](https://github.com/hariPrasathK-Dev) |


## License

This project is licensed under the [MIT LICENSE](LICENSE).
