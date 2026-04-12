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
from server.constants import MAX_STEPS
from server.ui.components import (
    scenario_header,
    outcome_banner,
    hard_progress,
    action_history_table,
    reward_chart_svg,
    stat_card,
)

# ── Module-level episode state ────────────────────────────────────────────────
# Each item: (step_number, per_step_reward, tool_name)
_step_rewards: List[Tuple[int, float, str]] = []
# Each item: dict with step/tool/param/reward/result/success
_action_history: List[dict] = []


def _reset_state() -> None:
    global _step_rewards, _action_history
    _step_rewards = []
    _action_history = []


def _param_str(action: MicroSocGymAction) -> str:
    if action.tool == "block_ip":
        return action.ip_address or "(none)"
    if action.tool == "delete_file":
        return action.file_path or "(none)"
    if action.tool == "kill_process":
        return str(action.pid) if action.pid is not None else "(none)"
    return ""   # investigative tools have no parameter


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


# ── Public handlers ───────────────────────────────────────────────────────────

def handle_reset(env: MicroSocGymEnvironment):
    """Called when the user clicks Reset. Returns all UI output values."""
    _reset_state()

    obs: MicroSocGymObservation = env.reset()
    state = env.state

    scenario = state.scenario
    total_reward = state.total_reward

    # Re-enable all five tool buttons for the new episode
    _btn_on = gr.update(interactive=True)

    return (
        scenario_header(scenario),                      # 0  scenario_header_html
        outcome_banner(False, False, 0.0, 0),           # 1  outcome_html
        hard_progress(False, False, False)               # 2  hard_progress_html
            if scenario == "hard" else "",
        stat_card("STEPS", "0 / 8"),                    # 3  steps_stat
        stat_card("TOTAL REWARD", "+0.00", "#38bdf8"),  # 4  reward_stat
        action_history_table([]),                        # 5  history_html
        reward_chart_svg([]),                            # 6  chart_html
        obs.info,                                        # 7  feedback_box
        _btn_on,                                         # 8  btn_access_log
        _btn_on,                                         # 9  btn_auth_log
        _btn_on,                                         # 10 btn_block_ip
        _btn_on,                                         # 11 btn_delete_file
        _btn_on,                                         # 12 btn_kill_process
    )


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

    # When the episode ends, disable every tool button so the user cannot
    # fire a 9th action past the 8-step budget. Reset re-enables them all.
    _btn = gr.update(interactive=not obs.done)

    steps_color = "#f87171" if step_count >= MAX_STEPS else (
        "#fb923c" if step_count >= 6 else "#38bdf8"
    )

    return (
        scenario_header(scenario),                                        # 0
        outcome_banner(obs.done, obs.success, total_reward, step_count),  # 1
        hard_prog,                                                         # 2
        stat_card("STEPS", f"{step_count} / 8", steps_color),            # 3
        stat_card("TOTAL REWARD", f"{total_reward:+.2f}", r_color),      # 4
        action_history_table(_action_history),                            # 5
        reward_chart_svg(_step_rewards),                                  # 6
        obs.info,                                                          # 7
        _btn,                                                              # 8  btn_access_log
        _btn,                                                              # 9  btn_auth_log
        _btn,                                                              # 10 btn_block_ip
        _btn,                                                              # 11 btn_delete_file
        _btn,                                                              # 12 btn_kill_process
    )