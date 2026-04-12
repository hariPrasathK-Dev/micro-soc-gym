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


class MicroSocGymClient:

    def __init__(self, base_url: str = "http://localhost:7860", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def health(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def reset(self) -> Dict[str, Any]:
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
        # Payload is the action fields directly — FastAPI deserialises
        # the body straight into MicroSocGymAction, no wrapper key needed.
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
        resp = self.session.get(f"{self.base_url}/state", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def grade_episode(self) -> Dict[str, Any]:
        # No parameters — the server reads scenario from its own state.
        # Returns the full grading dict: episode_id, scenario, score,
        # total_reward, steps_taken, threat_neutralised.
        resp = self.session.get(
            f"{self.base_url}/grade_episode",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()