# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI + Gradio application for the Micro-SOC Gym Environment.

Endpoints (OpenEnv API):
    POST /reset   - Start a new episode
    POST /step    - Execute an agent action
    GET  /state   - Episode metadata
    GET  /schema  - Action/observation schemas
    GET  /health  - Liveness probe

Gradio UI (served at /):
    Interactive SOC dashboard for judges / manual demos.
    Live log stream, action controls, reward history chart.
"""

from __future__ import annotations
from typing import List, Tuple

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError(
        "openenv is required. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    import gradio as gr
except ImportError as e:
    raise ImportError(
        "gradio is required for the web UI. Add 'gradio' to dependencies."
    ) from e

from models import MicroSocGymAction, MicroSocGymObservation
from server.micro_soc_gym_environment import MicroSocGymEnvironment

# ---------------------------------------------------------------------------
# Singleton environment - shared between OpenEnv HTTP API and Gradio UI
# ---------------------------------------------------------------------------

_env_singleton = MicroSocGymEnvironment()

# Factory always returns the SAME instance so episode state persists
app = create_app(
    lambda: _env_singleton,
    MicroSocGymAction,
    MicroSocGymObservation,
    env_name="micro_soc_gym",
    max_concurrent_envs=1,
)


# ---------------------------------------------------------------------------
# Gradio UI helpers
# ---------------------------------------------------------------------------

SCENARIO_COLORS = {
    "easy":   "#22c55e",
    "medium": "#f59e0b",
    "hard":   "#ef4444",
    "":       "#6b7280",
}

SCENARIO_LABELS = {
    "easy":   "EASY - Noisy Scanner",
    "medium": "MEDIUM - Brute Force",
    "hard":   "HARD - Webshell C2",
    "":       "⬜ Not Started",
}

SCENARIO_DESCRIPTIONS = {
    "easy": (
        "<b>What is happening:</b> An attacker is flooding the server with "
        "hundreds of 404 requests (a port/path scanner).<br>"
        "<b>What to do:</b> Block their IP using <code>block_ip</code>.<br>"
        "<b>Correct action:</b> <code style='color:#38bdf8'>block_ip(\"&lt;attacker_ip&gt;\")</code><br>"
        "<b>Warning:</b> Do NOT block legitimate traffic."
    ),
    "medium": (
        "<b>What is happening:</b> An attacker is brute-forcing SSH logins. "
        "You will see repeated failed auth attempts in <code>auth.log</code>.<br>"
        "<b>What to do:</b> Block the attacker's IP, NOT the admin IP.<br>"
        "<b>Correct action:</b> <code style='color:#38bdf8'>block_ip(\"&lt;attacker_ip&gt;\")</code><br>"
        "<b>Warning:</b> A random IP is a whitelisted admin - blocking them = instant failure."
    ),
    "hard": (
        "<b>What is happening:</b> A webshell (e.g., <code>backdoor.php</code>) has been planted and is making "
        "C2 callbacks. A malicious process is running on the server.<br>"
        "<b>What to do:</b> Two actions required: kill the process AND delete the backdoor file.<br>"
        "<b>Correct actions:</b> <code style='color:#38bdf8'>kill_process(PID)</code> then "
        "<code style='color:#38bdf8'>delete_file(\"/var/www/html/&lt;backdoor_name&gt;\")</code><br>"
        "<b>Tip:</b> Look for a PID in brackets <code>[1234]</code> in the log lines."
    ),
    "": (
        "Click <b>⟳ Reset / New Episode</b> to start. Each reset loads the next scenario in order: "
        "Easy → Medium → Hard → Easy... The environment will generate fresh attack logs for you to analyse."
    ),
}

_reward_history: List[Tuple[int, float]] = []
_action_history: List[dict] = []  # list of {step, tool, param, reward, result, success}
_last_feedback: str = "Press Reset to start a new episode."


def _scenario_badge(scenario: str) -> str:
    color = SCENARIO_COLORS.get(scenario, "#6b7280")
    label = SCENARIO_LABELS.get(scenario, scenario)
    return (
        f'<div style="display:inline-block;padding:6px 16px;border-radius:20px;'
        f'background:{color}22;border:2px solid {color};color:{color};'
        f'font-weight:700;font-size:15px;font-family:monospace;">{label}</div>'
    )


def _scenario_info_html(scenario: str) -> str:
    color = SCENARIO_COLORS.get(scenario, "#6b7280")
    label = SCENARIO_LABELS.get(scenario, "Not Started")
    desc  = SCENARIO_DESCRIPTIONS.get(scenario, "")
    return (
        f'<div style="background:#1e293b;border:1px solid {color}44;border-left:4px solid {color};'
        f'border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;line-height:1.7;color:#e2e8f0;">'
        f'<div style="color:{color};font-weight:800;font-size:14px;margin-bottom:8px;">{label}</div>'
        f'{desc}</div>'
    )


def _action_history_html(history: list) -> str:
    if not history:
        return (
            '<div style="color:#475569;font-style:italic;font-family:monospace;font-size:13px;'
            'padding:12px;">No actions yet. Execute an action below.</div>'
        )
    rows = ""
    for entry in history:
        icon = "✅" if entry["success"] else ("⚠️" if entry["reward"] > 0 else "❌")
        r_color = "#22c55e" if entry["reward"] > 0 else "#ef4444"
        rows += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:6px 10px;color:#64748b;">#{entry["step"]}</td>'
            f'<td style="padding:6px 10px;color:#38bdf8;font-weight:700;">{entry["tool"]}</td>'
            f'<td style="padding:6px 10px;color:#cbd5e1;">{entry["param"]}</td>'
            f'<td style="padding:6px 10px;color:{r_color};font-weight:700;">{entry["reward"]:+.1f}</td>'
            f'<td style="padding:6px 10px;">{icon} {entry["result"]}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:12px;">'
        '<thead><tr style="border-bottom:2px solid #334155;">'
        '<th style="text-align:left;padding:6px 10px;color:#64748b;">Step</th>'
        '<th style="text-align:left;padding:6px 10px;color:#64748b;">Tool</th>'
        '<th style="text-align:left;padding:6px 10px;color:#64748b;">Parameter</th>'
        '<th style="text-align:left;padding:6px 10px;color:#64748b;">Reward</th>'
        '<th style="text-align:left;padding:6px 10px;color:#64748b;">Result</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _outcome_banner_html(done: bool, success: bool, total_reward: float) -> str:
    if not done:
        steps_left = "Episode in progress. Execute actions to neutralise the threat."
        return (
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
            f'padding:12px 18px;font-family:monospace;font-size:13px;color:#94a3b8;">'
            f'🔄 {steps_left}</div>'
        )
    if success:
        return (
            '<div style="background:#14532d;border:2px solid #22c55e;border-radius:8px;'
            'padding:16px 20px;font-family:monospace;font-size:15px;font-weight:700;color:#86efac;">'
            f'THREAT NEUTRALISED. Episode complete! Total reward: {total_reward:+.1f}<br>'
            '<span style="font-size:12px;font-weight:400;color:#4ade80;">'
            'Click ⟳ Reset to start the next scenario.</span></div>'
        )
    else:
        return (
            '<div style="background:#450a0a;border:2px solid #ef4444;border-radius:8px;'
            'padding:16px 20px;font-family:monospace;font-size:15px;font-weight:700;color:#fca5a5;">'
            f'EPISODE FAILED. Total reward: {total_reward:+.1f}<br>'
            '<span style="font-size:12px;font-weight:400;color:#f87171;">'
            'A false positive or timeout ended the episode. Click ⟳ Reset to try again.</span></div>'
        )


def _make_reward_plot(history: List[Tuple[int, float]]):
    if not history:
        return '<div style="color:#9ca3af;font-style:italic;padding:20px 0;">No reward data yet. Start an episode.</div>'

    steps  = [h[0] for h in history]
    values = [h[1] for h in history]
    min_v, max_v = min(values), max(values)
    rng = max(max_v - min_v, 1.0)

    W, H = 560, 120
    pad = 12

    def sx(i):
        return pad + (i / max(len(steps) - 1, 1)) * (W - 2 * pad)

    def sy(v):
        return H - pad - ((v - min_v) / rng) * (H - 2 * pad)

    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(values))
    stroke = "#22c55e" if values[-1] >= 0 else "#ef4444"

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;">'
        f'<line x1="{pad}" y1="{sy(0):.1f}" x2="{W-pad}" y2="{sy(0):.1f}" '
        f'stroke="#334155" stroke-width="1" stroke-dasharray="4 4"/>'
        f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        + "".join(
            f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="3.5" fill="{stroke}"/>'
            for i, v in enumerate(values)
        )
        + f'<text x="{pad}" y="{H-2}" fill="#94a3b8" font-size="10" font-family="monospace">step 0</text>'
        f'<text x="{W-pad}" y="{H-2}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="end">step {steps[-1]}</text>'
        f'<text x="{pad}" y="14" fill="#94a3b8" font-size="10" font-family="monospace">{max_v:+.1f}</text>'
        f'<text x="{pad}" y="{H-14}" fill="#94a3b8" font-size="10" font-family="monospace">{min_v:+.1f}</text>'
        f"</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# Gradio event handlers - all operate on _env_singleton directly
# ---------------------------------------------------------------------------

def handle_reset():
    global _reward_history, _action_history, _last_feedback
    _reward_history = []
    _action_history = []

    obs: MicroSocGymObservation = _env_singleton.reset()
    state = _env_singleton.state
    _last_feedback = obs.info

    badge        = _scenario_badge(state.scenario)
    scenario_info = _scenario_info_html(state.scenario)
    logs         = obs.logs
    steps        = f"{state.step_count} / 8"
    reward       = f"{state.total_reward:+.1f}"
    action_hist  = _action_history_html(_action_history)
    outcome      = _outcome_banner_html(obs.done, obs.success, state.total_reward)
    plot         = _make_reward_plot(_reward_history)

    return badge, scenario_info, logs, steps, reward, action_hist, outcome, plot, gr.update(interactive=True)


def handle_step(tool: str, ip_address: str, file_path: str, pid_str: str):
    global _reward_history, _action_history, _last_feedback

    # Gradio passes None for hidden/empty textboxes - coerce to str first
    ip_address = (ip_address or "").strip()
    file_path  = (file_path  or "").strip()
    pid_str    = (pid_str    or "").strip()

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

    obs: MicroSocGymObservation = _env_singleton.step(action)
    state = _env_singleton.state
    _last_feedback = obs.info

    _reward_history.append((state.step_count, state.total_reward))

    # Build a human-readable parameter string for the history table
    if tool == "block_ip":
        param_str = ip_address.strip() or "(none)"
    elif tool == "delete_file":
        param_str = (action.file_path or "(none)")
    elif tool == "kill_process":
        param_str = str(pid) if pid is not None else "(none)"
    else:
        param_str = ""

    _action_history.append({
        "step":    state.step_count,
        "tool":    tool,
        "param":   param_str,
        "reward":  obs.reward,
        "result":  obs.info[:80] + ("..." if len(obs.info) > 80 else ""),
        "success": obs.success,
    })

    badge        = _scenario_badge(state.scenario)
    scenario_info = _scenario_info_html(state.scenario)
    logs         = obs.logs
    steps        = f"{state.step_count} / 8"
    reward       = f"{state.total_reward:+.1f}"
    action_hist  = _action_history_html(_action_history)
    outcome      = _outcome_banner_html(obs.done, obs.success, state.total_reward)
    plot         = _make_reward_plot(_reward_history)

    step_btn = gr.update(interactive=not obs.done)

    return badge, scenario_info, logs, steps, reward, action_hist, outcome, plot, step_btn


# ---------------------------------------------------------------------------
# Gradio layout
# ---------------------------------------------------------------------------

CSS = """
body, .gradio-container { background: #0f172a !important; color: #e2e8f0 !important; }
h1.soc-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 4px;
}
.panel { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
.log-box textarea {
    background: #0f172a !important; color: #86efac !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important; border: 1px solid #1e3a5f !important;
    border-radius: 8px !important;
}
.btn-reset { background: #1d4ed8 !important; color: white !important; font-weight: 700 !important; }
.btn-step  { background: #7c3aed !important; color: white !important; font-weight: 700 !important; }
.stat-box { text-align: center; }
.stat-box input { font-size: 1.4rem !important; font-weight: 800 !important;
                  text-align: center !important; color: #38bdf8 !important; }
"""

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap" rel="stylesheet">
"""


def build_gradio_ui() -> gr.Blocks:
    with gr.Blocks(css=CSS, head=HEAD, title="Micro-SOC Gym") as demo:

        # Title
        gr.HTML("""
        <div style="text-align:center;padding:32px 0 12px;">
          <h1 class="soc-title">Micro-SOC Gym</h1>
          <p style="color:#64748b;font-size:0.95rem;font-family:monospace;margin:0 0 20px;">
            RL environment simulating a Security Operations Center (SOC) Triage Engine.
          </p>
        </div>
        """)

        # Top row: scenario badge + reset button
        with gr.Row():
            with gr.Column(scale=3):
                scenario_badge = gr.HTML(_scenario_badge(""))
            with gr.Column(scale=1):
                reset_btn = gr.Button("⟳  Reset / New Episode", elem_classes="btn-reset", size="lg")

        # Scenario info panel (what is the threat + what action to take)
        scenario_info = gr.HTML(_scenario_info_html(""))

        # Main two-column layout
        with gr.Row():

            # Left - log viewer
            with gr.Column(scale=3, elem_classes="panel"):
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 8px;font-family:monospace;">'
                        'LOG STREAM '
                        '<span style="color:#475569;font-weight:400;">- The raw log file the agent must analyse</span></p>')
                log_output = gr.Textbox(
                    show_label=False,
                    container=False,
                    value="Press Reset / New Episode to start...",
                    lines=31,
                    max_lines=31,
                    interactive=False,
                    elem_classes="log-box",
                )

            # Right - Controls + stats
            with gr.Column(scale=2, elem_classes="panel"):

                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">EPISODE STATS</p>')
                with gr.Row():
                    steps_box = gr.Textbox(
                        value="0 / 8",
                        label="Steps (max 8)",
                        interactive=False,
                        elem_classes="stat-box",
                        scale=1,
                    )
                    reward_box = gr.Textbox(
                        value="+0.0",
                        label="Total Reward",
                        interactive=False,
                        elem_classes="stat-box",
                        scale=1,
                    )

                gr.HTML('<hr style="border-color:#334155;margin:16px 0;">')
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 8px;font-family:monospace;">AGENT ACTION</p>')

                tool_dropdown = gr.Dropdown(
                    choices=["block_ip", "delete_file", "kill_process"],
                    value="block_ip",
                    label="Tool",
                    interactive=True,
                )
                ip_input = gr.Textbox(
                    label="IP Address  (for block_ip)",
                    placeholder="e.g. 192.168.1.5",
                    interactive=True,
                )
                file_input = gr.Textbox(
                    label="File Path  (for delete_file)",
                    placeholder="e.g. /var/www/html/backdoor.php",
                    interactive=True,
                )
                pid_input = gr.Textbox(
                    label="Process ID  (for kill_process)",
                    placeholder="e.g. 1234",
                    interactive=True,
                )

                step_btn = gr.Button(
                    "▶  Execute Action",
                    elem_classes="btn-step",
                    size="lg",
                    interactive=False,
                )

        # Episode outcome banner
        outcome_banner = gr.HTML(_outcome_banner_html(False, False, 0.0))

        # Action history
        with gr.Row():
            with gr.Column(elem_classes="panel"):
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 10px;font-family:monospace;">'
                        'ACTION HISTORY '
                        '<span style="color:#475569;font-weight:400;">- Every action the agent took this episode</span></p>')
                action_history_html = gr.HTML(_action_history_html([]))

        # Reward curve
        with gr.Row():
            with gr.Column(elem_classes="panel"):
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">CUMULATIVE REWARD CURVE</p>')
                reward_chart = gr.HTML(_make_reward_plot([]))

        # Scenario reference table
        with gr.Row():
            with gr.Column(elem_classes="panel"):
                gr.HTML("""
                <p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">SCENARIO REFERENCE</p>
                <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:13px;">
                  <thead><tr style="border-bottom:1px solid #334155;">
                    <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Scenario</th>
                    <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Log Source</th>
                    <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Attacker Pattern</th>
                    <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Correct Action</th>
                    <th style="text-align:right;padding:6px 12px;color:#94a3b8;">Max Reward</th>
                  </tr></thead>
                  <tbody>
                    <tr style="border-bottom:1px solid #1e293b;">
                      <td style="padding:8px 12px;color:#22c55e;font-weight:700;">Easy</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">access.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">404 flood from random attacker IP</td>
                      <td style="padding:8px 12px;color:#38bdf8;">block_ip("&lt;attacker_ip&gt;")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1e293b;">
                      <td style="padding:8px 12px;color:#f59e0b;font-weight:700;">Medium</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">auth.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">SSH brute-force from random attacker IP<br><span style="color:#64748b;font-size:11px;">Whitelisted IPs are mixed in - do NOT block</span></td>
                      <td style="padding:8px 12px;color:#38bdf8;">block_ip("&lt;attacker_ip&gt;")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                    <tr>
                      <td style="padding:8px 12px;color:#ef4444;font-weight:700;">Hard</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">access.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">random backdoor C2 file from random IP</td>
                      <td style="padding:8px 12px;color:#38bdf8;">kill_process(PID)<br>delete_file("&lt;backdoor_name&gt;")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                  </tbody>
                </table>
                <p style="color:#475569;font-size:11px;margin:12px 0 0;font-family:monospace;">
                  False positive (blocking whitelisted IP) = Immediate failure &nbsp;|&nbsp; Episode cap: 8 steps
                </p>
                """)

        # Wiring
        _ui_outputs = [
            scenario_badge, scenario_info, log_output, steps_box, reward_box,
            action_history_html, outcome_banner, reward_chart, step_btn,
        ]

        reset_btn.click(
            fn=handle_reset,
            inputs=[],
            outputs=_ui_outputs,
        )

        step_btn.click(
            fn=handle_step,
            inputs=[tool_dropdown, ip_input, file_input, pid_input],
            outputs=_ui_outputs,
        )



    return demo


# Mount Gradio onto the FastAPI app
gradio_ui = build_gradio_ui()
app = gr.mount_gradio_app(app, gradio_ui, path="/")


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
