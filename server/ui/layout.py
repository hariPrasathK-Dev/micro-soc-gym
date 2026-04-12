# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations
import gradio as gr
from functools import partial

from server.micro_soc_gym_environment import MicroSocGymEnvironment
from server.ui.components import (
    scenario_header,
    reward_chart_svg,
    reward_reference_html,
    scenario_reference_html,
    stat_card,
)
from server.ui.handlers import handle_reset, handle_step


# Stylesheet
CSS = """
/* Dark mode colors (Gradio default) */
:root {
    --soc-surface:      #0f172a;
    --soc-surface-2:    #111827;
    --soc-border:       #1e293b;
    --soc-border-2:     #1f2d3d;
    --soc-text-primary: #e2e8f0;
    --soc-text-muted:   #ffffff;
    --soc-text-faint:   #ffffff;
    --soc-text-dimmer:  #ffffff;
    --soc-code-bg:      #0a0f1a;
    --soc-chart-bg:     #080e1a;
}

/* Light mode colors override */
@media (prefers-color-scheme: light) {
    :root {
        --soc-surface:      #f8fafc;
        --soc-surface-2:    #f1f5f9;
        --soc-border:       #cbd5e1;
        --soc-border-2:     #e2e8f0;
        --soc-text-primary: #0f172a;
        --soc-text-muted:   #000000;
        --soc-text-faint:   #000000;
        --soc-text-dimmer:  #000000;
        --soc-code-bg:      #f1f5f9;
        --soc-chart-bg:     #f8fafc;
    }
}

/* Data theme attribute for both modes*/
[data-theme="light"] {
    --soc-surface:      #f8fafc;
    --soc-surface-2:    #f1f5f9;
    --soc-border:       #cbd5e1;
    --soc-border-2:     #e2e8f0;
    --soc-text-primary: #0f172a;
    --soc-text-muted:   #000000;
    --soc-text-faint:   #000000;
    --soc-text-dimmer:  #000000;
    --soc-code-bg:      #f1f5f9;
    --soc-chart-bg:     #f8fafc;
}

/* Scenario card */
.soc-scenario-card {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border);
    border-left: 4px solid var(--soc-border);
    border-radius: 8px;
    padding: 14px 18px;
    font-family: monospace;
    line-height: 1.75;
}
.soc-scenario-badge {
    font-size: 14px !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    border-radius: 9999px !important; /* Pill shape */
    border: 1px solid !important;
    letter-spacing: 0.5px !important;
    display: inline-block !important;
}
.soc-scenario-threat {
    font-size: 18px !important;
    font-weight: 500 !important;
    color: var(--soc-text-primary) !important;
    margin-top: 10px !important;
    line-height: 1.4 !important;
}
.soc-hint-line {
    margin-top: 8px;
    font-size: 13px;
    color: var(--soc-text-muted);
}
.soc-hint-key {
    color: var(--soc-text-faint);
}
.soc-warn-block {
    margin-top: 10px;
    padding: 8px 12px;
    background: #2d1515;
    border-left: 3px solid #ef4444;
    border-radius: 4px;
    font-size: 13px;
    color: #fca5a5;
}

/* Outcome banner */
.soc-outcome {
    border-radius: 8px;
    padding: 12px 18px;
    font-family: monospace;
    font-size: 14px;
}
.soc-outcome-running {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border-2);
    color: var(--soc-text-faint);
}
.soc-outcome-success {
    background: #052e16;
    border: 2px solid #16a34a;
    padding: 16px 20px;
}
.soc-outcome-fail {
    background: #2d0a0a;
    border: 2px solid #dc2626;
    padding: 16px 20px;
}
.soc-outcome-title {
    font-size: 15px;
    font-weight: 700;
}
.soc-outcome-success .soc-outcome-title { color: #4ade80; }
.soc-outcome-fail    .soc-outcome-title { color: #f87171; }
.soc-outcome-sub {
    font-size: 13px;
    margin-top: 4px;
}
.soc-outcome-success .soc-outcome-sub { color: #86efac; }
.soc-outcome-fail    .soc-outcome-sub { color: #fca5a5; }

/* Hard progress */
.soc-progress-box {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border-2);
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
}
.soc-progress-label {
    font-size: 12px;
    color: var(--soc-text-faint);
    font-family: monospace;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.soc-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-family: monospace;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid;
}
.soc-pill-done    { background: #052e16; border-color: #16a34a; color: #4ade80; }
.soc-pill-pending { background: var(--soc-surface-2); border-color: var(--soc-border); color: var(--soc-text-faint); }

/* Stat card */
.soc-stat-card {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border-2);
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
}
.soc-stat-label {
    font-size: 12px;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.soc-stat-value {
    font-size: 24px;
    font-weight: 700;
    font-family: monospace;
}

/* Reward chart */
.soc-chart-svg {
    width: 100%;
    background: var(--soc-chart-bg);
    border-radius: 8px;
    display: block;
}
.soc-chart-baseline { stroke: var(--soc-text-faint); }
.soc-chart-grid     { stroke: var(--soc-border); }
.soc-chart-empty {
    height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    font-size: 13px;
}

/* Reference tables */
.soc-ref-table  { width: 100%; border-collapse: collapse; }
.soc-ref-header { border-bottom: 2px solid var(--soc-border); }
.soc-ref-th {
    text-align: left;
    padding: 6px 12px;
    color: var(--soc-text-dimmer);
    font-size: 12px;
    font-weight: 600;
}
.soc-ref-row    { border-bottom: 1px solid var(--soc-border); }
.soc-ref-desc   { padding: 7px 12px; color: var(--soc-text-muted); font-size: 13px; }
.soc-ref-cell      { padding: 8px 12px; color: var(--soc-text-muted); font-size: 13px; }
.soc-ref-cell-mono { padding: 8px 12px; color: var(--soc-text-faint); font-size: 13px; font-family: monospace; }
.soc-ref-cell-fix  { padding: 8px 12px; color: #38bdf8; font-size: 13px; font-family: monospace; }
.soc-ref-cell-note { padding: 8px 12px; color: var(--soc-text-dimmer); font-size: 12px; }

/* Gradio Blocks overrides */
.gradio-container .prose { max-width: 100% !important; }

/* Feedback box */
.feedback-box textarea {
    background: var(--soc-code-bg) !important;
    color: var(--soc-text-muted) !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 12px !important;
    border: 1px solid var(--soc-border) !important;
    border-radius: 8px !important;
    line-height: 1.7 !important;
}
.feedback-box label {
    color: var(--soc-text-dimmer) !important;
    font-size: 12px !important;
}

/* Tool inputs */
.tool-input input, .tool-input textarea {
    background: var(--soc-surface-2) !important;
    color: var(--soc-text-primary) !important;
    border: 1px solid var(--soc-border) !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}
.tool-input label {
    color: var(--soc-text-faint) !important;
    font-size: 12px !important;
    letter-spacing: 0.3px;
}
.tool-input input:focus {
    border-color: #3b82f6 !important;
    outline: none !important;
}

/* Buttons */
.btn-reset {
    background: #1d4ed8 !important;
    color: #fff !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 15px !important;
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
    font-size: 14px !important;
    font-family: monospace !important;
    transition: background 0.15s;
}
.btn-investigate:hover  { background: #075985 !important; }
.btn-investigate:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

.btn-remediate {
    background: #3b0764 !important;
    color: #c084fc !important;
    font-weight: 700 !important;
    border: 1px solid #7e22ce !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-family: monospace !important;
    transition: background 0.15s;
}
.btn-remediate:hover   { background: #4c0a8e !important; }
.btn-remediate:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

/* Section labels */
.section-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    margin-bottom: 10px;
    text-transform: uppercase;
}

.soc-scenario-card code,
.soc-hint-line code {
    background: var(--soc-code-bg);
    color: #38bdf8;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
}

/* Title styling */
@media (prefers-color-scheme: light) {
    .soc-title { color: #000000 !important; }
}
[data-theme="light"] .soc-title { color: #000000 !important; }
"""

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
"""

# Tool groups for the UI
INVESTIGATIVE_TOOLS = ["read_access_log", "read_auth_log"]
REMEDIATION_TOOLS   = ["block_ip", "delete_file", "kill_process"]
ALL_TOOLS = INVESTIGATIVE_TOOLS + REMEDIATION_TOOLS

# Builds the Gradio UI
def build_ui(env: MicroSocGymEnvironment) -> gr.Blocks:
    # Bind handlers to the env singleton
    _reset = partial(handle_reset, env)
    _step  = partial(handle_step, env)

    with gr.Blocks(css=CSS, head=HEAD, title="Micro SOC Gym") as demo:

        # Title bar
        gr.HTML("""
        <div style="padding:28px 0 4px;border-bottom:1px solid #0f172a;margin-bottom:20px;">
          <div style="display:flex;align-items:baseline;gap:14px;">
            <span class="soc-title" style="font-size:24px;font-weight:700;color:#e2e8f0;letter-spacing:-0.5px;">
              Micro SOC Gym
            </span>
            <span style="font-size:13px;color:#ffffff;font-family:monospace;">
              Meta x HuggingFace Hackathon
            </span>
          </div>
          <p style="font-size:14px;color:#ffffff;margin:6px 0 0;line-height:1.5;">
            An Reinforcement Learning (RL) environment where an agent triages security incidents across three scenarios simulating different attacks. Investigate, Identify Attack & Remediate, all within 8 steps. 
          </p>
        </div>
        """)

        # Reset + scenario header
        with gr.Row():
            with gr.Column(scale=4):
                scenario_header_html = gr.HTML(scenario_header(""))
            with gr.Column(scale=1, min_width=160):
                reset_btn = gr.Button(
                    "⟳  New Episode",
                    elem_classes="btn-reset",
                    size="lg",
                )

        # Stats row
        with gr.Row():
            steps_stat  = gr.HTML(stat_card("STEPS TAKEN", "- / 8"))
            reward_stat = gr.HTML(stat_card("TOTAL CUMULATIVE REWARD", "0.0"))

        # Main two-column layout
        with gr.Row(equal_height=False):

            # Left column - action controls
            with gr.Column(scale=1):

                # Investigative tools
                gr.HTML(
                    '<div class="section-label">1. Investigate</div>'
                    '<div style="font-size:13px;color:#ffffff;margin-bottom:10px;">'
                    'Read logs before taking any remediation action.</div>'
                )
                with gr.Row():
                    btn_access_log = gr.Button(
                        "read_access_log",
                        elem_classes="btn-investigate",
                        interactive=False,
                    )
                    btn_auth_log = gr.Button(
                        "read_auth_log",
                        elem_classes="btn-investigate",
                        interactive=False,
                    )

                gr.HTML('<div style="height:4px;"></div>')

                # Remediation tools
                gr.HTML(
                    '<div class="section-label">2. Remediate</div>'
                    '<div style="font-size:13px;color:#ffffff;margin-bottom:10px;">'
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
                        interactive=False,
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
                        interactive=False,
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
                        interactive=False,
                    )

            # Right column - log output + history
            with gr.Column(scale=1):

                # Feedback / log output area
                gr.HTML('<div class="section-label">Logs</div>')
                feedback_box = gr.Textbox(
                    value="",
                    show_label=False,
                    lines=13,
                    max_lines=13,
                    interactive=False,
                    elem_classes="feedback-box",
                )

                gr.HTML('<div style="height:10px;"></div><div class="section-label">Action feedback</div>')
                action_feedback_box = gr.Textbox(
                    value="",
                    show_label=False,
                    lines=3,
                    max_lines=3,
                    interactive=False,
                    elem_classes="feedback-box",
                )

        # Full width reward chart below tools
        with gr.Row():
            with gr.Column():
                gr.HTML('<div class="section-label">Step-wise Rewards</div>')
                reward_chart_html = gr.HTML(reward_chart_svg([]))

        # Reference tables (collapsed by default)
        with gr.Accordion("Scenario Reference", open=False):
            gr.HTML(scenario_reference_html())

        with gr.Accordion("Reward/Penalty Reference", open=False):
            gr.HTML(reward_reference_html())

        _outputs = [
            scenario_header_html,
            steps_stat,
            reward_stat,
            reward_chart_html,
            feedback_box,
            action_feedback_box,
            btn_access_log,
            btn_auth_log,
            btn_block_ip,
            btn_delete_file,
            btn_kill_process,
            ip_input,
            file_input,
            pid_input,
        ]

        # Reset
        reset_btn.click(fn=_reset, inputs=[], outputs=_outputs)

        # Investigative tools - no parameter needed
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

        # Remediation tools - each reads its own specific input
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