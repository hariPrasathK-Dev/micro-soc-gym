# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("requests is required: pip install requests")


# Client for interacting with the Micro SOC Gym REST API
class MicroSocGymClient:

    # Initialse the client session with base url (docker container)
    def __init__(self, base_url: str = "http://localhost:7860", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # Health endpint to check API server status
    def health(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
    
    # Reset the environment for a new episode
    def reset(self) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/reset", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # Steps through process executing a tool action and returns its result
    def step(
        self,
        tool: str,
        ip_address: Optional[str] = None,
        file_path: Optional[str] = None,
        pid: Optional[int] = None,
    ) -> Dict[str, Any]:
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

    # Retrieve the current state of the environment
    def state(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/state", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # Grade the completed episode and returns the state with score between (0, 1)
    def grade_episode(self) -> Dict[str, Any]:
        resp = self.session.get(
            f"{self.base_url}/grade_episode",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # Close the session
    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()