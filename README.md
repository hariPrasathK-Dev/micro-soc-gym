---
title: Micro-SOC Gym
sdk: docker
app_port: 7860
---

<div align="center">
  <img alt="Micro-SOC Gym" src="https://img.shields.io/badge/OpenEnv-Compatible-blue.svg">
  <h1>Micro-SOC Gym</h1>
  <p><strong>A Real-Time, Dockerized Security Operations Center (SOC) Triage Benchmark for Reinforcement Learning Agents.</strong></p>
  <p>Built for the <b>Meta × Hugging Face × PyTorch OpenEnv Hackathon 2026</b>.</p>
</div>

---

## Table of Contents

- [1. Environment Description & Motivation](#1-environment-description--motivation)
- [2. Observation & Action Space](#2-observation--action-space)
- [3. Task Descriptions & Difficulty](#3-task-descriptions--difficulty)
- [4. Setup & Usage Instructions](#4-setup--usage-instructions)
- [5. Baseline Scores](#5-baseline-scores)
- [6. Project Architecture](#6-project-architecture)
- [7. Pre-Validation Results](#7-pre-validation-results)
- [8. Visual Workflow](#8-visual-workflow)

---

## 1. Environment Description & Motivation

### Overview

**Micro-SOC Gym** models a high-stakes, real-time Security Operations Center workload designed strictly for evaluating Reinforcement Learning (RL) agents and LLMs. Rather than interacting with static datasets or grid-world simulators, agents interface with a live, monolithic Docker container running production-grade services.

The environment provisions a FastAPI backend, simulated daemons (`nginx`, `sshd`), and orchestrated attacker scripts. Agents perform threat triage just like real analysts: by parsing unstructured server log streams, mapping threats, and executing exact remediation actions.

### Motivation

Standard LLM benchmarks test static multi-choice or simple generation capabilities. **Micro-SOC Gym** forces the agent into a proactive system administration role. It bridges the gap between cybersecurity and AI by heavily challenging an agent's ability to:

1. Handle "noisy" data streams (identifying signal amidst decoy traffic).
2. Sequentially build and execute a multi-tier remediation plan.
3. Understand precise constraints to avoid _False Positives_—where overly aggressive actions cause catastrophic system failure by blocking legitimate network infrastructure.

---

## 2. Observation & Action Space

This environment conforms to the standard **OpenEnv** HTTP JSON schema patterns via integrated Pydantic definitions.

### 2.1 Observation Space

State observations are fed continuously to the agent via the `MicroSocGymObservation` dictionary payload:

- **`logs` (String)**: A real-time 50-line stream output representing the targeted log asset (`/var/log/nginx/access.log` or `/var/log/auth.log`).
- **`reward` (Float)**: Immediate reinforcement mapping to the agent's recent action (+1.0 for success, 0.0 for penalties/noise).
- **`done` (Boolean)**: Marks terminal episode conditions (Success, Failure, or Max-Steps Exhaustion).
- **`success` (Boolean)**: Directly indicates if the active threat has been fully neutralized.
- **`info` (String)**: Grader feedback and human-readable context hints.

### 2.2 Action Space

Instead of simple directional movements, the agent manipulates an infrastructure API. The `MicroSocGymAction` requires specifying exactly one remediation `tool` per step:

1. **`block_ip(ip_address: str)`**
   - Targets network ingress. Commits the rogue IP explicitly to the target's `/etc/nginx/blocklist.conf`.
2. **`kill_process(pid: int)`**
   - Transmits a system-level `SIGKILL` to forcefully terminate unauthorized command-and-control background processes.
3. **`delete_file(file_path: str)`**
   - Permanently deletes verified malware, webshells, or backdoor executable scripts from the host disk layer.

---

## 3. Task Descriptions & Difficulty

The environment sequences through tiered adversarial scenarios via a round-robin rotation upon iteration (`/reset`). Agents must shift strategies depending on the active threat intelligence.

|  Difficulty   | Name & Mechanics                                                                                                                                                                            | Win Condition & Constraints                                                                                                                                                                                                                                          |
| :-----------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  **🟢 Easy**  | **Volumetric Network Scanning**<br>A specific host originates a high frequency of `HTTP 404` errors traversing non-existent administrative endpoints (e.g., `/admin`, `/wp-login.php`).     | **Goal:** Parse `access.log` and invoke `block_ip(IP)`.<br>**Constraint:** Minimal. Rapid detection and blocking resolves the threat.                                                                                                                                |
| **🟡 Medium** | **Identity Compromise & Subnet Decoys**<br>An attacker conducts sustained SSH credential stuffing attempts visible within `auth.log`. Legitimate admin logins intermingle.                  | **Goal:** Map the brute force IP and invoke `block_ip(IP)`.<br>**Constraint:** Extreme False-Positive penalty. Blocking the recognized admin subnet (`10.0.0.100`) triggers an immediate critical failure.                                                           |
|  **🔴 Hard**  | **Active Command and Control (C2)**<br>A persistent threat has rooted the webserver via a PHP backdoor (`backdoor.php`) and actively dispatches base64-encoded shell commands to live PIDs. | **Goal:** Execute a multi-stage kill chain.<br>**Constraint:** Agents must first sever the session via `kill_process(PID)` _and_ sequentially invoke `delete_file(FILE)`. Neither action alone will stabilize the environment. _(Requires Unix/Linux process space)_ |

---

## 4. Setup & Usage Instructions

### 4.1 Operating the Docker Monolith (Local/Deploy)

Because the environment performs system-level state management, it executes flawlessly inside an isolated Hugging Face Docker Space or a local Unix deployment.

```bash
# 1. Compile the self-contained container
docker build -t micro-soc-gym .

# 2. Deploy locally matching OpenEnv default ports
docker run -p 7860:7860 micro-soc-gym
```

**Bonus:** You can access the unified **Gradio Triage Dashboard** visually at `http://localhost:7860/` for manual testing and live-stream observation.

### 4.2 Scripted Agent Initialization

To launch a programmatically controlled AI agent test loop against your running server:

```bash
# 1. Provision virtual environment and dependencies
python -m venv .venv
source .venv/bin/activate  # (Windows: .\.venv\Scripts\activate)
pip install -r requirements.txt

# 2. Map Hugging Face Hub Credentials
export HF_TOKEN="<your_secure_hugging_face_token>"

# 3. Initiate Baseline Inference
python inference.py
```

---

## 5. Baseline Scores

Agents have a maximum horizon of **8 steps** per scenario before timeout failure. The ideal score is **+1.0 per solved scenario**, peaking at a **+3.0 cumulative total**.

| Agent Execution Model              | Scenario: Easy | Scenario: Medium | Scenario: Hard |  Final Score   |
| :--------------------------------- | :------------: | :--------------: | :------------: | :------------: |
| **Qwen/Qwen2.5-72B-Instruct**      |     `[  ]`     |      `[  ]`      |     `[  ]`     | `[   ] / 3.00` |
| **Base Baseline (Random Choices)** |     `0.00`     |      `0.00`      |     `0.00`     | `0.00 / 3.00`  |

_(Insert your evaluated baseline runs in the empty spaces above)._

---

## 6. Project Architecture

The codebase handles networking logic securely decoupled from kernel requirements via supervised orchestration.

### 6.1 System Architecture Diagram

```text
+-------------------------------------------------------------+
|                     OpenEnv Framework                       |
|  +-----------------+                 +-------------------+  |
|  |   RL Agent/LLM  |  <---JSON--->   |   inference.py    |  |
|  | (Qwen/Baseline) |                 | (OpenEnv harness) |  |
|  +-----------------+                 +-------------------+  |
+-------------------------------------------------------------+
                               | (HTTP/REST via Port 7860)
                               v
+-------------------------------------------------------------+
|                 Docker Container (Micro-SOC)                |
|                                                             |
|  +=======================================================+  |
|  |                   Supervisord (Init)                  |  |
|  +=======================================================+  |
|       |                     |                    |          |
|       v                     v                    v          |
| +-----------+       +---------------+    +---------------+  |
| |   NGINX   | <-----+   Attacker    |    |  SSH/Auth Log |  |
| | Webserver |       |   Scripts     +--->|     (Mock)    |  |
| +-----------+       +---------------+    +---------------+  |
|       |             (easy/med/hard)              |          |
|       +-------------------+----------------------+          |
|                           | (Log Streams)                   |
|                           v                                 |
|  +=======================================================+  |
|  |                 FastAPI (server/app.py)               |  |
|  |-------------------------------------------------------|  |
|  |                 Micro SOC Gym Environment             |  |
|  |                                                       |  |
|  |  +----------------+  +--------------+  +-----------+  |  |
|  |  | Log Aggregator |  | Rules/Grader |  | Telemetry |  |  |
|  |  | (access/auth)  |  |    Engine    |  | (Gradio)  |  |  |
|  |  +----------------+  +--------------+  +-----------+  |  |
|  +=======================================================+  |
+-------------------------------------------------------------+
```

### 6.2 Directory Structure

```text
micro_soc_gym/
├── openenv.yaml                      # OpenEnv space requirement configuration
├── schema.json                       # Validation schema for standard OpenEnv JSON interactions
├── Dockerfile                        # Environment runtime manifest & OS provisions
├── supervisord.conf                  # Daemon management orchestrator (Nginx, API, Attacks)
├── nginx-default                     # Nginx server configuration defaults and simulated routing
├── pyproject.toml / requirements.txt # Python dependencies map and package configuration
├── validate-submission.sh            # Local strict validation helper script
├── server/                           # OpenEnv Backend Services
│   ├── app.py                        # FastAPI endpoints and Gradio Telemetry Dashboard
│   └── micro_soc_gym_environment.py  # Primary orchestration, grader matrix, and rules engines
├── scripts/                          # Subprocess Attack Generators
│   ├── easy_attack.sh                # Volumetric target traffic creator
│   ├── medium_attack.sh              # Mock SSH Brute-Force + Decoys
│   └── hard_attack.sh                # Webshell runtime process simulation
├── inference.py                      # Automated LLM ReAct agent testing loop
├── client.py                         # Synchronous HTTP validation client
└── models.py                         # Application-layer Pydantic schema exports
```

## 7. Pre-Validation Results

Prior to deployment, the environment underwent strict automated compliance testing using the official OpenEnv validation suite. All requisite checks—including Hugging Face Space liveness, Docker container build integrity, and OpenEnv schema validation—passed successfully.

![OpenEnv Pre-Validation Success Output](pre-validation.png)

<details>
<summary><b>View Raw Validation Logs</b></summary>

```text
========================================
  OpenEnv Submission Validator
========================================
[11:21:05] Repo:     /c/Users/hp859/Desktop/Meta X Hugging_Face Hacks/micro_soc_gym
[11:21:05] Ping URL: https://harinie4466-micro-soc-gym.hf.space

[11:21:05] Step 1/3: Pinging HF Space (https://harinie4466-micro-soc-gym.hf.space/reset) ...
[11:21:11] PASSED -- HF Space is live and responds to /reset
[11:21:11] Step 2/3: Running docker build ...
[11:21:11]   Found Dockerfile in /c/Users/hp859/Desktop/Meta X Hugging_Face Hacks/micro_soc_gym
[11:21:19] PASSED -- Docker build succeeded
[11:21:19] Step 3/3: Running openenv validate ...
[11:21:33] PASSED -- openenv validate passed
[11:21:33]   [OK] micro_soc_gym: Ready for multi-mode deployment

========================================
  All 3/3 checks passed!
  Your submission is ready to submit.
========================================

```

</details>

---

## 8. Visual Workflow

The following demonstration showcases the interactive **Gradio Telemetry Dashboard** hosted on Hugging Face Spaces. It provides a visual, real-time representation of the triage environment, allowing users to manually act as the responding agent. By analyzing live log streams and manually executing remediation tools, users can intuitively understand the environment's mechanics, active threat scenarios, and the precise constraints an AI agent must navigate.

<video src="UI-workflow.mp4" controls="controls" muted="muted" style="max-width: 100%;">
  Your browser does not support the HTML5 video tag. If you cannot see the video, <a href="UI-workflow.mp4">click here to download or view it directly</a>.
</video>
