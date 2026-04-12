# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations
from typing import List, Tuple
import gradio as gr

from models import MicroSocGymAction, MicroSocGymObservation
from server.micro_soc_gym_environment import MicroSocGymEnvironment
from server.constants import MAX_STEPS
from server.ui.components import (
    scenario_header,
    reward_chart_svg,
    stat_card,
)

_step_rewards: List[Tuple[int, float, str]] = []
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
    import os
    from server.constants import WEBROOT_PATH
    from server.utils import is_ip_blocked, check_hard_attack_process

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


# Public handlers
def handle_reset(env: MicroSocGymEnvironment):
    _reset_state()

    obs: MicroSocGymObservation = env.reset()
    state = env.state

    scenario = state.scenario
    total_reward = state.total_reward

    # Re-enable all five tool buttons for the new episode
    _btn_on = gr.update(interactive=True)

    return (
        scenario_header(scenario),
        stat_card("STEPS TAKEN", "0 / 8"),
        stat_card("TOTAL CUMULATIVE REWARD", "+0.00", "#38bdf8"),
        reward_chart_svg([]),
        "",
        "",
        _btn_on,
        _btn_on,
        _btn_on,
        _btn_on,
        _btn_on,
        gr.Textbox(value=""),
        gr.Textbox(value=""),
        gr.Textbox(value=""),
    )


def handle_step(
    env: MicroSocGymEnvironment,
    tool: str,
    ip_address: str,
    file_path: str,
    pid_str: str,
):
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
    hard_prog = ""

    # When the episode ends, disable every tool button so the user cannot
    # fire a 9th action past the 8-step budget. Reset re-enables them all.
    _btn = gr.update(interactive=not obs.done)

    steps_color = "#f87171" if step_count >= MAX_STEPS else (
        "#fb923c" if step_count >= 6 else "#38bdf8"
    )

    return (
        scenario_header(scenario),
        stat_card("STEPS TAKEN", f"{step_count} / 8", steps_color),
        stat_card("TOTAL CUMULATIVE REWARD", f"{total_reward:+.2f}", r_color),
        reward_chart_svg(_step_rewards),
        obs.info if "Logs:" in obs.info else gr.update(),
        obs.info if "Logs:" not in obs.info else "Correct investigative action! Logs read successfully.",
        _btn,
        _btn,
        _btn,
        _btn,
        _btn,
        gr.update(),
        gr.update(),
        gr.update(),
    )