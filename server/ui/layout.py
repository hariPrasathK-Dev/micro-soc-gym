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

# Stylesheet

CSS = """
/* ── Custom properties — dark mode (Gradio default) ── */
:root {
    --soc-surface:      #0f172a;
    --soc-surface-2:    #111827;
    --soc-border:       #1e293b;
    --soc-border-2:     #1f2d3d;
    --soc-text-primary: #e2e8f0;
    --soc-text-muted:   #94a3b8;
    --soc-text-faint:   #475569;
    --soc-text-dimmer:  #334155;
    --soc-code-bg:      #0a0f1a;
    --soc-chart-bg:     #080e1a;
}

/* ── Light mode overrides ── */
@media (prefers-color-scheme: light) {
    :root {
        --soc-surface:      #f8fafc;
        --soc-surface-2:    #f1f5f9;
        --soc-border:       #cbd5e1;
        --soc-border-2:     #e2e8f0;
        --soc-text-primary: #0f172a;
        --soc-text-muted:   #475569;
        --soc-text-faint:   #64748b;
        --soc-text-dimmer:  #94a3b8;
        --soc-code-bg:      #f1f5f9;
        --soc-chart-bg:     #f8fafc;
    }
}

/* Gradio also injects a data-theme attribute — cover both */
[data-theme="light"] {
    --soc-surface:      #f8fafc;
    --soc-surface-2:    #f1f5f9;
    --soc-border:       #cbd5e1;
    --soc-border-2:     #e2e8f0;
    --soc-text-primary: #0f172a;
    --soc-text-muted:   #475569;
    --soc-text-faint:   #64748b;
    --soc-text-dimmer:  #94a3b8;
    --soc-code-bg:      #f1f5f9;
    --soc-chart-bg:     #f8fafc;
}

/* ── Scenario card ── */
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
    font-size: 11px;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 12px;
    border: 1px solid;
    letter-spacing: 0.5px;
}
.soc-scenario-threat {
    font-size: 13px;
    color: var(--soc-text-primary);
    margin-top: 4px;
}
.soc-hint-line {
    margin-top: 8px;
    font-size: 12px;
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
    font-size: 12px;
    color: #fca5a5;
}

/* ── Outcome banner ── */
.soc-outcome {
    border-radius: 8px;
    padding: 12px 18px;
    font-family: monospace;
    font-size: 13px;
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
    font-size: 12px;
    margin-top: 4px;
}
.soc-outcome-success .soc-outcome-sub { color: #86efac; }
.soc-outcome-fail    .soc-outcome-sub { color: #fca5a5; }

/* ── Hard progress ── */
.soc-progress-box {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border-2);
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
}
.soc-progress-label {
    font-size: 11px;
    color: var(--soc-text-faint);
    font-family: monospace;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.soc-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-family: monospace;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid;
}
.soc-pill-done    { background: #052e16; border-color: #16a34a; color: #4ade80; }
.soc-pill-pending { background: var(--soc-surface-2); border-color: var(--soc-border); color: var(--soc-text-faint); }

/* ── Stat card ── */
.soc-stat-card {
    background: var(--soc-surface);
    border: 1px solid var(--soc-border-2);
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
}
.soc-stat-label {
    font-size: 11px;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.soc-stat-value {
    font-size: 22px;
    font-weight: 700;
    font-family: monospace;
}

/* ── Action history table ── */
.soc-hist-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
}
.soc-hist-header { border-bottom: 2px solid var(--soc-border); }
.soc-hist-th {
    text-align: left;
    padding: 6px 10px;
    color: var(--soc-text-dimmer);
    font-size: 11px;
    font-weight: 600;
}
.soc-hist-row { border-bottom: 1px solid var(--soc-border); }
.soc-hist-cell { padding: 7px 10px; }
.soc-hist-step    { color: var(--soc-text-faint); font-size: 11px; }
.soc-hist-param   { color: var(--soc-text-muted); font-size: 12px;
                    max-width: 140px; overflow: hidden;
                    text-overflow: ellipsis; white-space: nowrap; }
.soc-hist-feedback { color: var(--soc-text-faint); font-size: 11px; }
.soc-empty-state {
    color: var(--soc-text-dimmer);
    font-style: italic;
    font-family: monospace;
    font-size: 13px;
    padding: 16px 0;
    text-align: center;
}

/* ── Reward chart ── */
.soc-chart-svg {
    width: 100%;
    background: var(--soc-chart-bg);
    border-radius: 8px;
    display: block;
}
.soc-chart-baseline { stroke: var(--soc-text-faint); }
.soc-chart-grid     { stroke: var(--soc-border); }
.soc-chart-axis-text { fill: var(--soc-text-dimmer); }
.soc-chart-empty {
    height: 110px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    font-size: 12px;
}

/* ── Reference tables ── */
.soc-ref-table  { width: 100%; border-collapse: collapse; }
.soc-ref-header { border-bottom: 2px solid var(--soc-border); }
.soc-ref-th {
    text-align: left;
    padding: 6px 12px;
    color: var(--soc-text-dimmer);
    font-size: 11px;
    font-weight: 600;
}
.soc-ref-row    { border-bottom: 1px solid var(--soc-border); }
.soc-ref-desc   { padding: 7px 12px; color: var(--soc-text-muted); font-size: 12px; }
.soc-ref-cell      { padding: 8px 12px; color: var(--soc-text-muted); font-size: 12px; }
.soc-ref-cell-mono { padding: 8px 12px; color: var(--soc-text-faint); font-size: 12px; font-family: monospace; }
.soc-ref-cell-fix  { padding: 8px 12px; color: #38bdf8; font-size: 12px; font-family: monospace; }
.soc-ref-cell-note { padding: 8px 12px; color: var(--soc-text-dimmer); font-size: 11px; }

/* ── Gradio Blocks overrides ── */
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
    font-size: 11px !important;
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
    font-size: 11px !important;
    letter-spacing: 0.3px;
}
.tool-input input:focus {
    border-color: #3b82f6 !important;
    outline: none !important;
}

/* Buttons — colors are fixed (not theme-aware) because they carry semantic meaning */
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
.btn-investigate:hover  { background: #075985 !important; }
.btn-investigate:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

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
.btn-remediate:hover   { background: #4c0a8e !important; }
.btn-remediate:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

/* Section labels */
.section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    color: var(--soc-text-dimmer);
    font-family: monospace;
    margin-bottom: 10px;
    text-transform: uppercase;
}

/* code tags inside HTML components */
.soc-scenario-card code,
.soc-hint-line code {
    background: var(--soc-code-bg);
    color: #38bdf8;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 11px;
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

        # Title bar
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

        # Hard-scenario progress (hidden for easy/medium)
        hard_progress_html = gr.HTML("")

        # Episode outcome
        outcome_html = gr.HTML(outcome_banner(False, False, 0.0, 0))

        # Stats row
        with gr.Row():
            steps_stat  = gr.HTML(stat_card("STEPS", "— / 8"))
            reward_stat = gr.HTML(stat_card("TOTAL REWARD", "—"))

        # Main two-column layout
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

        # Reference tables (collapsed by default)
        with gr.Accordion("Scenario reference", open=False):
            gr.HTML(scenario_reference_html())

        with gr.Accordion("Reward reference", open=False):
            gr.HTML(reward_reference_html())

        # Shared output list
        # Order must match the return tuples in handlers.py exactly.
        # ALL five tool buttons are included so handlers can disable every
        # one of them when done=True, preventing the "9 / 8" overshoot.
        _outputs = [
            scenario_header_html,   # 0
            outcome_html,           # 1
            hard_progress_html,     # 2
            steps_stat,             # 3
            reward_stat,            # 4
            history_html,           # 5
            reward_chart_html,      # 6
            feedback_box,           # 7
            btn_access_log,         # 8  — investigative
            btn_auth_log,           # 9  — investigative
            btn_block_ip,           # 10 — remediation
            btn_delete_file,        # 11 — remediation
            btn_kill_process,       # 12 — remediation
        ]

        # Wiring

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