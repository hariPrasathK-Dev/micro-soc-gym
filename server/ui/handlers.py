# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Gradio event handler functions for the Micro-SOC Gym UI.

All functions receive plain Python values from Gradio inputs and
return plain Python values / gr.update() objects.
State is held in module-level lists that are reset on each episode.
This is single-user / single-env — consistent with max_concurrent_envs=1.
"""

from __future__ import annotations
from typing import List, Tuple
import gradio as gr

from models import MicroSocGymAction, MicroSocGymObservation
from server.micro_soc_gym_environment import MicroSocGymEnvironment
from server.ui.components import (
    scenario_header,
    outcome_banner,
    hard_progress,
    action_history_table,
    reward_chart_svg,
    stat_card,
)

# Module-level episode state
# Each item: (step_number, per_step_reward, tool_name)
_step_rewards: List[Tuple[int, float, str]] = []
# Each item: dict with step/tool/param/reward/result/success
_action_history: List[dict] = []

#reset the environment
def _reset_state() -> None:
    global _step_rewards, _action_history
    _step_rewards = []
    _action_history = []

#get the action parameter value based on the action
def _param_str(action: MicroSocGymAction) -> str:
    if action.tool == "block_ip":
        return action.ip_address or "(none)"
    if action.tool == "delete_file":
        return action.file_path or "(none)"
    if action.tool == "kill_process":
        return str(action.pid) if action.pid is not None else "(none)"
    return ""   # investigative tools have no parameter

#check if the ip is blocked; file is deleted; process is killed fir the given environment
def _hard_progress_state(env: MicroSocGymEnvironment):
    """
    Derive the three booleans for the hard-scenario progress tracker
    directly from the environment's live state.
    """
    from server.utils import is_ip_blocked, check_hard_attack_process
    import os
    from server.constants import WEBROOT_PATH

    ip_blocked = False
    file_deleted = False
    proc_killed = False

    try:
        attacker_ip = getattr(env, "attacker_ip", None)
        if attacker_ip:
            ip_blocked = is_ip_blocked(attacker_ip)
    except Exception:
        pass

    try:
        backdoor = getattr(env, "backdoor_file_name", None)
        if backdoor:
            file_deleted = not os.path.exists(os.path.join(WEBROOT_PATH, backdoor))
    except Exception:
        pass

    try:
        proc_killed = not check_hard_attack_process()
    except Exception:
        pass

    return ip_blocked, file_deleted, proc_killed


# Public handlers: re-rendering the UI for the reset (getting the UI set for next episode of the environment)
def handle_reset(env: MicroSocGymEnvironment):
    """Called when the user clicks Reset. Returns all UI output values."""
    _reset_state()

    obs: MicroSocGymObservation = env.reset()
    state = env.state

    scenario = state.scenario
    # total_reward = state.total_reward

    return (
        scenario_header(scenario),                         # scenario_header_html
        outcome_banner(False, False, 0.0, 0),              # outcome_html
        hard_progress(False, False, False)                 # hard_progress_html
            if scenario == "hard" else "",
        stat_card("STEPS", f"0 / 8"),                      # steps_stat
        stat_card("TOTAL REWARD", "+0.00", "#38bdf8"),   # reward_stat
        action_history_table([]),                          # history_html
        reward_chart_svg([]),                              # chart_html
        obs.info,                                          # feedback_box (last action result)
        gr.update(interactive=True),                       # step_btn enable
        gr.update(interactive=True),                       # tool_dropdown
    )

# execute the action/step in the soc environment
# tracking of the reward history and the action history for the current episode takesplace
def handle_step(
    env: MicroSocGymEnvironment,
    tool: str,
    ip_address: str,
    file_path: str,
    pid_str: str,
):
    """Called when the user clicks Execute Action."""
    # Coerce Gradio's possible None values
    ip_address = (ip_address or "").strip()
    file_path = (file_path or "").strip()
    pid_str = (pid_str or "").strip()

    pid: int | None = None
    if pid_str:
        try:
            pid = int(pid_str)
        except ValueError:
            pid = None

    action = MicroSocGymAction(
        tool=tool,
        ip_address=ip_address or None,
        file_path=file_path or None,
        pid=pid,
    )

    obs: MicroSocGymObservation = env.step(action)
    state = env.state

    # Track per-step reward
    _step_rewards.append((state.step_count, obs.reward, tool))

    # Track action history
    _action_history.append({
        "step": state.step_count,
        "tool": tool,
        "param": _param_str(action),
        "reward": obs.reward,
        "result": obs.info,
        "success": obs.success,
    })

    scenario = state.scenario
    total_reward = state.total_reward
    step_count = state.step_count

    # Reward stat color
    if total_reward > 0:
        r_color = "#4ade80"
    elif total_reward < 0:
        r_color = "#f87171"
    else:
        r_color = "#38bdf8"

    # Hard scenario progress
    if scenario == "hard":
        ip_b, file_d, proc_k = _hard_progress_state(env)
        hard_prog = hard_progress(ip_b, file_d, proc_k)
    else:
        hard_prog = ""

    # Disable step button if episode is done
    step_interactive = not obs.done

    return (
        scenario_header(scenario),
        outcome_banner(obs.done, obs.success, total_reward, step_count),
        hard_prog,
        stat_card("STEPS", f"{step_count} / 8",
                  "#fb923c" if step_count >= 6 else "#38bdf8"),
        stat_card("TOTAL REWARD", f"{total_reward:+.2f}", r_color),
        action_history_table(_action_history),
        reward_chart_svg(_step_rewards),
        obs.info,
        gr.update(interactive=step_interactive),
        gr.update(interactive=True),
    )