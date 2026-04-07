# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI + Gradio application for the Micro-SOC Gym Environment.

Endpoints (OpenEnv API):
    POST /reset   — Start a new episode
    POST /step    — Execute an agent action
    GET  /state   — Episode metadata
    GET  /schema  — Action/observation schemas
    GET  /health  — Liveness probe

Gradio UI (served at /):
    Interactive SOC dashboard for judges / manual demos.
    Live log stream, action controls, reward history chart.
"""

from __future__ import annotations

import time
from typing import List, Tuple

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
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
# Singleton environment — shared between OpenEnv HTTP API and Gradio UI
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
    "easy":   "#22c55e",   # green
    "medium": "#f59e0b",   # amber
    "hard":   "#ef4444",   # red
    "":       "#6b7280",   # grey (not started)
}

SCENARIO_LABELS = {
    "easy":   "🟢 EASY — Noisy Scanner",
    "medium": "🟡 MEDIUM — Brute Force",
    "hard":   "🔴 HARD — Webshell C2",
    "":       "⬜ Not Started",
}

_reward_history: List[Tuple[int, float]] = []   # (step, cumulative_reward)
_last_feedback: str = "Press **Reset** to start a new episode."


def _scenario_badge(scenario: str) -> str:
    color = SCENARIO_COLORS.get(scenario, "#6b7280")
    label = SCENARIO_LABELS.get(scenario, scenario)
    return (
        f'<div style="display:inline-block;padding:6px 16px;border-radius:20px;'
        f'background:{color}22;border:2px solid {color};color:{color};'
        f'font-weight:700;font-size:15px;font-family:monospace;">{label}</div>'
    )


def _make_reward_plot(history: List[Tuple[int, float]]):
    """Build a simple HTML SVG sparkline for the reward curve."""
    if not history:
        return '<div style="color:#9ca3af;font-style:italic;padding:20px 0;">No reward data yet — start an episode.</div>'

    steps  = [h[0] for h in history]
    values = [h[1] for h in history]
    min_v, max_v = min(values), max(values)
    rng = max(max_v - min_v, 1.0)

    W, H = 560, 120
    pad = 12

    def sx(i):
        return pad + (i / max(len(steps) - 1, 1)) * (W - 2 * pad)

    def sy(v):
        # invert Y so higher = up
        return H - pad - ((v - min_v) / rng) * (H - 2 * pad)

    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(values))

    # colour: green if last reward positive, red if negative
    stroke = "#22c55e" if values[-1] >= 0 else "#ef4444"

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;">'
        # zero line
        f'<line x1="{pad}" y1="{sy(0):.1f}" x2="{W-pad}" y2="{sy(0):.1f}" '
        f'stroke="#334155" stroke-width="1" stroke-dasharray="4 4"/>'
        # reward polyline
        f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        # dots at each step
        + "".join(
            f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="3.5" fill="{stroke}"/>'
            for i, v in enumerate(values)
        )
        # labels
        + f'<text x="{pad}" y="{H-2}" fill="#94a3b8" font-size="10" font-family="monospace">step 0</text>'
        f'<text x="{W-pad}" y="{H-2}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="end">step {steps[-1]}</text>'
        f'<text x="{pad}" y="14" fill="#94a3b8" font-size="10" font-family="monospace">{max_v:+.1f}</text>'
        f'<text x="{pad}" y="{H-14}" fill="#94a3b8" font-size="10" font-family="monospace">{min_v:+.1f}</text>'
        f"</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# Gradio event handlers — all operate on _env_singleton directly
# ---------------------------------------------------------------------------

def handle_reset():
    """Reset the environment and return updated UI state."""
    global _reward_history, _last_feedback
    _reward_history = []

    obs: MicroSocGymObservation = _env_singleton.reset()
    state = _env_singleton.state
    _last_feedback = obs.info

    badge   = _scenario_badge(state.scenario)
    logs    = obs.logs
    steps   = str(state.step_count)
    reward  = f"{state.total_reward:+.1f}"
    fb      = obs.info
    plot    = _make_reward_plot(_reward_history)
    done_lbl = "✅ Done" if obs.done else "🔄 Running"

    return badge, logs, steps, reward, fb, plot, done_lbl, gr.update(interactive=True)


def handle_step(tool: str, ip_address: str, file_path: str, pid_str: str):
    """Execute an agent action and return updated UI state."""
    global _reward_history, _last_feedback

    pid: int | None = None
    if pid_str.strip():
        try:
            pid = int(pid_str.strip())
        except ValueError:
            pid = None

    action = MicroSocGymAction(
        tool=tool,
        ip_address=ip_address.strip() or None,
        file_path=file_path.strip() or None,
        pid=pid,
    )

    obs: MicroSocGymObservation = _env_singleton.step(action)
    state = _env_singleton.state
    _last_feedback = obs.info

    _reward_history.append((state.step_count, state.total_reward))

    badge   = _scenario_badge(state.scenario)
    logs    = obs.logs
    steps   = str(state.step_count)
    reward  = f"{state.total_reward:+.1f}"
    fb      = obs.info
    plot    = _make_reward_plot(_reward_history)

    if obs.done:
        done_lbl = "✅ Episode Done" if obs.success else "❌ Episode Over"
        step_btn = gr.update(interactive=False)
    else:
        done_lbl = "🔄 Running"
        step_btn = gr.update(interactive=True)

    return badge, logs, steps, reward, fb, plot, done_lbl, step_btn


def handle_tool_change(tool: str):
    """Show/hide the relevant parameter input when the tool dropdown changes."""
    show_ip   = gr.update(visible=(tool == "block_ip"))
    show_file = gr.update(visible=(tool == "delete_file"))
    show_pid  = gr.update(visible=(tool == "kill_process"))
    return show_ip, show_file, show_pid


# ---------------------------------------------------------------------------
# Gradio layout
# ---------------------------------------------------------------------------

CSS = """
/* ── Global reset ── */
body, .gradio-container { background: #0f172a !important; color: #e2e8f0 !important; }

/* ── Headers ── */
h1.soc-title {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 2rem; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 4px;
}
h2.soc-sub { color: #64748b; font-size: 0.95rem; font-family: monospace; margin:0 0 20px; }

/* ── Panels ── */
.panel {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 12px; padding: 20px;
}

/* ── Log area ── */
.log-box textarea {
    background: #0f172a !important; color: #86efac !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 12px !important; border: 1px solid #1e3a5f !important;
    border-radius: 8px !important;
}

/* ── Buttons ── */
.btn-reset { background: #1d4ed8 !important; color: white !important; font-weight: 700 !important; }
.btn-step  { background: #7c3aed !important; color: white !important; font-weight: 700 !important; }

/* ── Stats ── */
.stat-box { text-align: center; }
.stat-box input { font-size: 1.6rem !important; font-weight: 800 !important;
                  text-align: center !important; color: #38bdf8 !important; }

/* ── Feedback ── */
.feedback-box textarea { background: #1e293b !important; color: #fbbf24 !important;
    font-family: monospace !important; font-size: 13px !important; }
"""

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap" rel="stylesheet">
"""


def build_gradio_ui() -> gr.Blocks:
    with gr.Blocks(css=CSS, head=HEAD, title="Micro-SOC Gym") as demo:

        # ── Title ────────────────────────────────────────────────────────
        gr.HTML("""
        <div style="text-align:center;padding:32px 0 12px;">
          <h1 class="soc-title">🛡️ Micro-SOC Gym</h1>
          <p class="soc-sub">
            Reinforcement Learning Environment · Meta × HuggingFace × PyTorch OpenEnv Hackathon 2026
          </p>
        </div>
        """)

        # ── Scenario badge + status ───────────────────────────────────────
        with gr.Row():
            scenario_badge = gr.HTML(
                _scenario_badge(""),
                elem_id="scenario-badge",
            )
            episode_status = gr.Textbox(
                value="⬜ Not Started",
                label="Episode Status",
                interactive=False,
                scale=1,
            )

        # ── Main two-column layout ────────────────────────────────────────
        with gr.Row(equal_height=True):

            # Left — Live log viewer
            with gr.Column(scale=3, elem_classes="panel"):
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 8px;font-family:monospace;">📋 LIVE LOG STREAM</p>')
                log_output = gr.Textbox(
                    label="",
                    value="Press Reset to start an episode and populate logs...",
                    lines=22,
                    max_lines=22,
                    interactive=False,
                    elem_classes="log-box",
                )

            # Right — Controls + stats
            with gr.Column(scale=2, elem_classes="panel"):

                # Stats row
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">📊 EPISODE STATS</p>')
                with gr.Row():
                    steps_box = gr.Textbox(
                        value="0", label="Steps", interactive=False,
                        elem_classes="stat-box", scale=1,
                    )
                    reward_box = gr.Textbox(
                        value="+0.0", label="Total Reward", interactive=False,
                        elem_classes="stat-box", scale=1,
                    )

                gr.HTML('<hr style="border-color:#334155;margin:16px 0;">')

                # Reset button
                reset_btn = gr.Button("⟳  Reset / New Episode", elem_classes="btn-reset", size="lg")

                gr.HTML('<hr style="border-color:#334155;margin:16px 0;">')

                # Action controls
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 8px;font-family:monospace;">⚡ AGENT ACTION</p>')

                tool_dropdown = gr.Dropdown(
                    choices=["block_ip", "delete_file", "kill_process"],
                    value="block_ip",
                    label="Tool",
                    interactive=True,
                )

                ip_input = gr.Textbox(
                    label="IP Address",
                    placeholder="e.g. 10.0.0.1",
                    visible=True,
                    interactive=True,
                )
                file_input = gr.Textbox(
                    label="File Path",
                    placeholder="e.g. /var/www/html/backdoor.php",
                    visible=False,
                    interactive=True,
                )
                pid_input = gr.Textbox(
                    label="Process ID (PID)",
                    placeholder="e.g. 1234",
                    visible=False,
                    interactive=True,
                )

                step_btn = gr.Button(
                    "▶  Execute Action",
                    elem_classes="btn-step",
                    size="lg",
                    interactive=False,          # enabled after first reset
                )

                gr.HTML('<hr style="border-color:#334155;margin:16px 0;">')

                # Grader feedback
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 8px;font-family:monospace;">💬 GRADER FEEDBACK</p>')
                feedback_box = gr.Textbox(
                    value=_last_feedback,
                    label="",
                    lines=3,
                    interactive=False,
                    elem_classes="feedback-box",
                )

        # ── Reward history chart ───────────────────────────────────────────
        with gr.Row():
            with gr.Column(elem_classes="panel"):
                gr.HTML('<p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">📈 CUMULATIVE REWARD CURVE</p>')
                reward_chart = gr.HTML(_make_reward_plot([]))

        # ── Scenario reference card ────────────────────────────────────────
        with gr.Row():
            with gr.Column(elem_classes="panel"):
                gr.HTML("""
                <p style="color:#94a3b8;font-size:13px;margin:0 0 12px;font-family:monospace;">📖 SCENARIO GUIDE</p>
                <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:13px;">
                  <thead>
                    <tr style="border-bottom:1px solid #334155;">
                      <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Scenario</th>
                      <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Log Source</th>
                      <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Attacker Pattern</th>
                      <th style="text-align:left;padding:6px 12px;color:#94a3b8;">Correct Action</th>
                      <th style="text-align:right;padding:6px 12px;color:#94a3b8;">Max Reward</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style="border-bottom:1px solid #1e293b;">
                      <td style="padding:8px 12px;color:#22c55e;font-weight:700;">🟢 Easy</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">access.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">404 flood from 10.0.0.1</td>
                      <td style="padding:8px 12px;color:#38bdf8;font-family:monospace;">block_ip("10.0.0.1")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1e293b;">
                      <td style="padding:8px 12px;color:#f59e0b;font-weight:700;">🟡 Medium</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">auth.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">SSH brute force from 10.0.0.2<br><span style="color:#64748b;font-size:11px;">⚠ 10.0.0.100 is whitelisted admin</span></td>
                      <td style="padding:8px 12px;color:#38bdf8;font-family:monospace;">block_ip("10.0.0.2")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                    <tr>
                      <td style="padding:8px 12px;color:#ef4444;font-weight:700;">🔴 Hard</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">access.log</td>
                      <td style="padding:8px 12px;color:#e2e8f0;">backdoor.php C2 from 10.0.0.3</td>
                      <td style="padding:8px 12px;color:#38bdf8;font-family:monospace;">kill_process(PID)<br>delete_file("/var/www/html/backdoor.php")</td>
                      <td style="padding:8px 12px;text-align:right;color:#22c55e;">+1.0</td>
                    </tr>
                  </tbody>
                </table>
                <p style="color:#475569;font-size:11px;margin:12px 0 0;font-family:monospace;">
                  False positive: Immediate Failure &nbsp;|&nbsp; Episode cap: 8 steps
                </p>
                """)

        # ── Wiring ─────────────────────────────────────────────────────────

        _ui_outputs = [
            scenario_badge, log_output, steps_box, reward_box,
            feedback_box, reward_chart, episode_status, step_btn,
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

        tool_dropdown.change(
            fn=handle_tool_change,
            inputs=[tool_dropdown],
            outputs=[ip_input, file_input, pid_input],
        )

    return demo


# ---------------------------------------------------------------------------
# Mount Gradio onto the FastAPI app
# ---------------------------------------------------------------------------

gradio_ui = build_gradio_ui()
app = gr.mount_gradio_app(app, gradio_ui, path="/")


# ---------------------------------------------------------------------------
# Dev server entry point
# ---------------------------------------------------------------------------

def main(host: str = "0.0.0.0", port: int = 7860):
    """
    Run the server directly:
        uvicorn server.app:app --host 0.0.0.0 --port 7860
        python -m server.app
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
