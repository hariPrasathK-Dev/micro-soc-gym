# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Gradio layout for the Micro-SOC Gym.

build_ui(env) → gr.Blocks

This file is purely structural — no business logic, no HTML string
generation. Those live in components.py and handlers.py respectively.
"""

from __future__ import annotations
import gradio as gr
from functools import partial

from server.micro_soc_gym_environment import MicroSocGymEnvironment
from server.ui.components import (
    scenario_header,
    outcome_banner,
    hard_progress,
    action_history_table,
    reward_chart_svg,
    reward_reference_html,
    scenario_reference_html,
    stat_card,
)
from server.ui.handlers import handle_reset, handle_step


# ── Stylesheet ────────────────────────────────────────────────────────────────

CSS = """
/* Base */
body, .gradio-container {
    background: #080e1a !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', system-ui, sans-serif !important;
}

/* Remove Gradio's default white card shadow */
.gradio-container .prose { max-width: 100% !important; }
.block { border: none !important; background: transparent !important; }

/* Section panels */
.soc-panel {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 20px 22px;
}

/* Feedback box - monospace terminal feel */
.feedback-box textarea {
    background: #0a0f1a !important;
    color: #94a3b8 !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 12px !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    line-height: 1.7 !important;
}
.feedback-box label { color: #334155 !important; font-size: 11px !important; }

/* Tool input fields */
.tool-input input, .tool-input textarea {
    background: #111827 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e293b !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}
.tool-input label { color: #475569 !important; font-size: 11px !important; letter-spacing: 0.3px; }
.tool-input input:focus { border-color: #3b82f6 !important; outline: none !important; }

/* Dropdown */
.tool-dropdown select, .tool-dropdown input {
    background: #111827 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e293b !important;
    font-family: monospace !important;
    font-size: 13px !important;
}

/* Buttons */
.btn-reset {
    background: #1d4ed8 !important;
    color: #fff !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    padding: 12px 0 !important;
    letter-spacing: 0.3px;
    transition: background 0.15s;
}
.btn-reset:hover { background: #2563eb !important; }

.btn-investigate {
    background: #0c4a6e !important;
    color: #38bdf8 !important;
    font-weight: 700 !important;
    border: 1px solid #0369a1 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-family: monospace !important;
    transition: background 0.15s;
}
.btn-investigate:hover { background: #075985 !important; }

.btn-remediate {
    background: #3b0764 !important;
    color: #c084fc !important;
    font-weight: 700 !important;
    border: 1px solid #7e22ce !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-family: monospace !important;
    transition: background 0.15s;
}
.btn-remediate:hover { background: #4c0a8e !important; }

/* Section labels */
.section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    color: #334155;
    font-family: monospace;
    margin-bottom: 10px;
    text-transform: uppercase;
}
"""

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
"""

# Tool groups for the UI
INVESTIGATIVE_TOOLS = ["read_access_log", "read_auth_log"]
REMEDIATION_TOOLS   = ["block_ip", "delete_file", "kill_process"]
ALL_TOOLS = INVESTIGATIVE_TOOLS + REMEDIATION_TOOLS


def build_ui(env: MicroSocGymEnvironment) -> gr.Blocks:
    """
    Assemble the full Gradio UI.
    `env` is the singleton environment instance — passed in so the
    layout file never imports it directly (keeps the dependency flow clean).
    """

    # Bind handlers to the env singleton
    _reset = partial(handle_reset, env)
    _step  = partial(handle_step, env)

    with gr.Blocks(css=CSS, head=HEAD, title="Micro-SOC Gym") as demo:

        # ── Title bar ──────────────────────────────────────────────────────
        gr.HTML("""
        <div style="padding:28px 0 4px;border-bottom:1px solid #0f172a;margin-bottom:20px;">
          <div style="display:flex;align-items:baseline;gap:14px;">
            <span style="font-size:20px;font-weight:700;color:#e2e8f0;letter-spacing:-0.5px;">
              Micro-SOC Gym
            </span>
            <span style="font-size:12px;color:#334155;font-family:monospace;">
              RL · Security Operations · Meta × HuggingFace Hackathon
            </span>
          </div>
          <p style="font-size:13px;color:#475569;margin:6px 0 0;line-height:1.5;">
            An RL environment where an agent triages security incidents across three
            escalating scenarios. Each episode: investigate logs → identify the threat
            → remediate with the right tool(s). 8-step budget.
          </p>
        </div>
        """)

        # ── Reset + scenario header ────────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=4):
                scenario_header_html = gr.HTML(scenario_header(""))
            with gr.Column(scale=1, min_width=160):
                reset_btn = gr.Button(
                    "⟳  New Episode",
                    elem_classes="btn-reset",
                    size="lg",
                )

        # Hard-scenario progress (hidden for easy/medium)
        hard_progress_html = gr.HTML("")

        # Episode outcome
        outcome_html = gr.HTML(outcome_banner(False, False, 0.0, 0))

        # ── Stats row ─────────────────────────────────────────────────────
        with gr.Row():
            steps_stat  = gr.HTML(stat_card("STEPS", "— / 8"))
            reward_stat = gr.HTML(stat_card("TOTAL REWARD", "—"))

        # ── Main two-column layout ─────────────────────────────────────────
        with gr.Row(equal_height=False):

            # Left column — action controls + feedback
            with gr.Column(scale=3):

                # Investigative tools
                gr.HTML(
                    '<div class="section-label">① Investigate</div>'
                    '<div style="font-size:12px;color:#334155;margin-bottom:10px;">'
                    'Read logs before taking any remediation action.</div>'
                )
                with gr.Row():
                    btn_access_log = gr.Button(
                        "read_access_log",
                        elem_classes="btn-investigate",
                    )
                    btn_auth_log = gr.Button(
                        "read_auth_log",
                        elem_classes="btn-investigate",
                    )

                gr.HTML('<div style="height:16px;"></div>')

                # Remediation tools
                gr.HTML(
                    '<div class="section-label">② Remediate</div>'
                    '<div style="font-size:12px;color:#334155;margin-bottom:10px;">'
                    'Fill in the required parameter then click the tool button.</div>'
                )

                with gr.Row():
                    ip_input = gr.Textbox(
                        label="IP ADDRESS",
                        placeholder="e.g. 203.0.113.42",
                        elem_classes="tool-input",
                        scale=2,
                    )
                    btn_block_ip = gr.Button(
                        "block_ip  →",
                        elem_classes="btn-remediate",
                        scale=1,
                    )

                with gr.Row():
                    file_input = gr.Textbox(
                        label="FILE PATH",
                        placeholder="e.g. /var/www/html/backdoor.php",
                        elem_classes="tool-input",
                        scale=2,
                    )
                    btn_delete_file = gr.Button(
                        "delete_file  →",
                        elem_classes="btn-remediate",
                        scale=1,
                    )

                with gr.Row():
                    pid_input = gr.Textbox(
                        label="PROCESS ID",
                        placeholder="e.g. 1234",
                        elem_classes="tool-input",
                        scale=2,
                    )
                    btn_kill_process = gr.Button(
                        "kill_process  →",
                        elem_classes="btn-remediate",
                        scale=1,
                    )

                gr.HTML('<div style="height:16px;"></div>')

                # Feedback / log output area
                gr.HTML('<div class="section-label">Last action result / log output</div>')
                feedback_box = gr.Textbox(
                    value="Press  ⟳ New Episode  to begin.",
                    show_label=False,
                    lines=16,
                    max_lines=24,
                    interactive=False,
                    elem_classes="feedback-box",
                )

            # Right column — history + chart
            with gr.Column(scale=2):

                gr.HTML('<div class="section-label">Per-step rewards</div>')
                reward_chart_html = gr.HTML(reward_chart_svg([]))

                gr.HTML(
                    '<div style="height:20px;"></div>'
                    '<div class="section-label">Action history</div>'
                )
                history_html = gr.HTML(action_history_table([]))

        # ── Reference tables (collapsed by default) ───────────────────────
        with gr.Accordion("Scenario reference", open=False):
            gr.HTML(scenario_reference_html())

        with gr.Accordion("Reward reference", open=False):
            gr.HTML(reward_reference_html())

        # ── Shared output list ────────────────────────────────────────────
        # Order must match the return tuples in handlers.py exactly.
        _outputs = [
            scenario_header_html,   # 0
            outcome_html,           # 1
            hard_progress_html,     # 2
            steps_stat,             # 3
            reward_stat,            # 4
            history_html,           # 5
            reward_chart_html,      # 6
            feedback_box,           # 7
            btn_block_ip,           # 8  - interactive toggle (step_btn alias)
            btn_delete_file,        # 9  - mirrored enable/disable
        ]

        # ── Wiring ────────────────────────────────────────────────────────

        # Reset
        reset_btn.click(fn=_reset, inputs=[], outputs=_outputs)

        # Investigative tools — no parameter needed
        def _make_investigate_handler(tool_name: str):
            def _handler():
                return handle_step(env, tool_name, "", "", "")
            return _handler

        btn_access_log.click(
            fn=_make_investigate_handler("read_access_log"),
            inputs=[],
            outputs=_outputs,
        )
        btn_auth_log.click(
            fn=_make_investigate_handler("read_auth_log"),
            inputs=[],
            outputs=_outputs,
        )

        # Remediation tools — each reads its own specific input
        def _make_remediate_handler(tool_name: str):
            def _handler(ip: str, fp: str, pid: str):
                return handle_step(env, tool_name, ip, fp, pid)
            return _handler

        btn_block_ip.click(
            fn=_make_remediate_handler("block_ip"),
            inputs=[ip_input, file_input, pid_input],
            outputs=_outputs,
        )
        btn_delete_file.click(
            fn=_make_remediate_handler("delete_file"),
            inputs=[ip_input, file_input, pid_input],
            outputs=_outputs,
        )
        btn_kill_process.click(
            fn=_make_remediate_handler("kill_process"),
            inputs=[ip_input, file_input, pid_input],
            outputs=_outputs,
        )

    return demo