# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import Literal, Optional
from openenv.core.env_server import Action, Observation, State


class MicroSocGymAction(Action):
    """
    The structured action an RL agent can take each step.

    Three tool types:
      - block_ip:     Add an IP to Nginx blocklist (easy + medium)
      - delete_file:  Remove a file from the filesystem (hard)
      - kill_process: Send SIGKILL to a PID (hard)
    """
    tool: Literal["block_ip", "delete_file", "kill_process"]
    ip_address: Optional[str] = None    # required for block_ip
    file_path: Optional[str] = None     # required for delete_file
    pid: Optional[int] = None           # required for kill_process


class MicroSocGymObservation(Observation):
    """
    What the agent sees after each reset() or step().
    """
    logs: str                   # raw tail of access.log or auth.log
    reward: float               # reward for this step
    done: bool                  # True = episode over
    success: bool               # True = threat neutralised correctly
    info: str                   # human-readable grader feedback


class MicroSocGymState(State):
    """
    Internal episode metadata (returned by /state endpoint).
    """
    episode_id: str = ""
    step_count: int = 0
    scenario: str = ""          # "easy" | "medium" | "hard"
    total_reward: float = 0.0
    threat_neutralised: bool = False