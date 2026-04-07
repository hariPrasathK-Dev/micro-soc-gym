# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Micro-SOC Gym – runnable demo client.

Connects to a running Micro-SOC Gym server and cycles through all three
threat scenarios, printing each observation to the terminal.

Usage (against local Docker container on port 7860):
    python client.py
    python client.py --url http://localhost:7860
    python client.py --url https://<your-space>.hf.space

Dependencies:
    pip install requests
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("requests is required: pip install requests")


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

class MicroSocGymClient:
    """
    Thin HTTP client for the Micro-SOC Gym environment API.

    The server exposes three endpoints:
        POST /reset  → start a new episode, returns MicroSocGymObservation
        POST /step   → execute one action,   returns MicroSocGymObservation
        GET  /state  → episode metadata,     returns MicroSocGymState
    """

    def __init__(self, base_url: str = "http://localhost:7860", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """GET /health — confirm the server is up."""
        resp = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def reset(self) -> Dict[str, Any]:
        """POST /reset — start a new episode."""
        resp = self.session.post(f"{self.base_url}/reset", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def step(
        self,
        tool: str,
        ip_address: Optional[str] = None,
        file_path: Optional[str] = None,
        pid: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        POST /step — execute one agent action.

        Args:
            tool:       One of "block_ip", "delete_file", "kill_process"
            ip_address: Required for block_ip
            file_path:  Required for delete_file
            pid:        Required for kill_process
        """
        payload: Dict[str, Any] = {"tool": tool}
        if ip_address is not None:
            payload["ip_address"] = ip_address
        if file_path is not None:
            payload["file_path"] = file_path
        if pid is not None:
            payload["pid"] = pid

        resp = self.session.post(
            f"{self.base_url}/step",
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def state(self) -> Dict[str, Any]:
        """GET /state — current episode metadata."""
        resp = self.session.get(f"{self.base_url}/state", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------

def _banner(text: str) -> None:
    width = 72
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def _print_obs(obs: Dict[str, Any]) -> None:
    reward = obs.get("reward", 0.0)
    done   = obs.get("done", False)
    success = obs.get("success", False)
    info   = obs.get("info", "")
    logs   = obs.get("logs", "")

    print(f"  reward={reward:+.1f}  done={done}  success={success}")
    print(f"  info  : {info}")
    print()
    if logs:
        print("  ── logs (tail) ──────────────────────────────────────")
        for line in logs.splitlines()[-10:]:          # show last 10 lines
            print(f"  {line}")
        print()


# ---------------------------------------------------------------------------
# Scenario demos — each returns final total_reward
# ---------------------------------------------------------------------------

def run_easy(client: MicroSocGymClient) -> float:
    _banner("SCENARIO 1 / EASY — Noisy Scanner")
    print("  Expected action: block_ip('10.0.0.1')")

    obs = client.reset()
    _print_obs(obs)

    # Optimal agent: one correct action
    print("  → Sending: block_ip(10.0.0.1)")
    obs = client.step(tool="block_ip", ip_address="10.0.0.1")
    _print_obs(obs)

    state = client.state()
    total = state.get("total_reward", 0.0)
    print(f"  Episode total reward: {total:+.1f}")
    return total


def run_medium(client: MicroSocGymClient) -> float:
    _banner("SCENARIO 2 / MEDIUM — Stealthy Brute Force")
    print("  Expected action: block_ip('10.0.0.2'), NOT 10.0.0.100 (whitelisted admin)")

    obs = client.reset()
    # Wait a bit extra — medium writes every 4s
    print("  (waiting 5s for auth.log to populate…)")
    time.sleep(5)
    obs = client.reset()   # fresh logs now populated
    _print_obs(obs)

    # Demo false positive first, then the correct action
    print("  → Sending: block_ip(10.0.0.100)  [intentional false positive demo]")
    obs = client.step(tool="block_ip", ip_address="10.0.0.100")
    _print_obs(obs)

    print("  → Sending: block_ip(10.0.0.2)  [correct attacker]")
    obs = client.step(tool="block_ip", ip_address="10.0.0.2")
    _print_obs(obs)

    state = client.state()
    total = state.get("total_reward", 0.0)
    print(f"  Episode total reward: {total:+.1f}")
    return total


def run_hard(client: MicroSocGymClient) -> float:
    _banner("SCENARIO 3 / HARD — Active Webshell C2")
    print("  Expected actions: kill_process(<pid>)  +  delete_file('/var/www/html/backdoor.php')")

    obs = client.reset()
    _print_obs(obs)

    if "disabled" in obs.get("info", "").lower():
        print("  [SKIP] Hard scenario disabled in this environment (likely Windows dev mode).")
        return 0.0

    # In the hard scenario the logs show the attacker PID via the process list.
    # For the client demo we ask the /state endpoint; a real RL agent would
    # parse the log or enumerate /proc to find the hard_attack process.
    import re
    logs = obs.get("logs", "")
    pid_hint = None

    # Try to extract a PID from a log line mentioning backdoor.php
    # Real agent would do this via observation parsing
    pids_in_logs = re.findall(r"\[(\d+)\]", logs)
    if pids_in_logs:
        pid_hint = int(pids_in_logs[0])
        print(f"  → Extracted PID hint from logs: {pid_hint}")

    if pid_hint:
        print(f"  → Sending: kill_process({pid_hint})")
        obs = client.step(tool="kill_process", pid=pid_hint)
        _print_obs(obs)
    else:
        print("  → No PID found in logs — skipping kill_process (hard scenario requires Linux /proc)")

    print("  → Sending: delete_file('/var/www/html/backdoor.php')")
    obs = client.step(tool="delete_file", file_path="/var/www/html/backdoor.php")
    _print_obs(obs)

    state = client.state()
    total = state.get("total_reward", 0.0)
    print(f"  Episode total reward: {total:+.1f}")
    return total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Micro-SOC Gym demo client")
    parser.add_argument(
        "--url",
        default="http://localhost:7860",
        help="Base URL of the running Micro-SOC Gym server (default: http://localhost:7860)",
    )
    args = parser.parse_args()

    print(f"\n🔐 Micro-SOC Gym — Demo Client")
    print(f"   Server: {args.url}\n")

    with MicroSocGymClient(base_url=args.url) as client:
        # Health check
        try:
            h = client.health()
            print(f"   Health: {h}")
        except Exception as e:
            print(f"   ❌ Could not reach server: {e}", file=sys.stderr)
            sys.exit(1)

        rewards = []

        rewards.append(run_easy(client))
        rewards.append(run_medium(client))
        rewards.append(run_hard(client))

        _banner("SUMMARY")
        labels = ["Easy", "Medium", "Hard"]
        for label, r in zip(labels, rewards):
            print(f"  {label:8s}  total reward: {r:+.1f}")
        print(f"\n  Grand total: {sum(rewards):+.1f}")
        print()


if __name__ == "__main__":
    main()
