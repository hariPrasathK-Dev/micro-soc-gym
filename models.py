# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import Literal, Optional
from openenv.core.env_server import Action, Observation, State


# Class for an action in the micro-soc-gym environment (tool and its params)
class MicroSocGymAction(Action):
    tool: Literal["block_ip", "delete_file", "kill_process", "read_access_log", "read_auth_log"]
    ip_address: Optional[str] = None
    file_path: Optional[str] = None
    pid: Optional[int] = None


class MicroSocGymObservation(Observation):
    reward: float # Reward given for a step (can be -ve/0/+ve)
    done: bool # Marks if the episode has ended or not
    success: bool # Marks if agent succeeded in neutralising threat
    info: str # Feedback or Information returned from the envrionment for a step


class MicroSocGymState(State):
    episode_id: str = "" # UUID for the current episode
    step_count: int = 0 # Number of steps taken in the episode till now
    scenario: str = "" # easy/medium/hard
    total_reward: float = 0.0 # Cumulative reward till the current step
    threat_neutralised: bool = False # Marks if the threat has been neutralised or not
    investigated: bool = False # Marks if the agent used any investigative tools (reading logs) till now
