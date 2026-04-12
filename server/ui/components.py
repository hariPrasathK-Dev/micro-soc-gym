# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Pure HTML/SVG string generators for the Micro-SOC Gym UI.

No Gradio imports. No state. Every function takes plain data and
returns an HTML string.

All surface/text colors are expressed as CSS custom properties defined
in layout.py's CSS block so they flip correctly between Gradio's dark
and light themes. Semantic accent colors (green/orange/red) are kept
as hex because they carry fixed meaning regardless of theme.
"""

from __future__ import annotations
from typing import List, Tuple


# Scenario metadata

SCENARIO_META = {
    "easy": {
        "label": "Easy — HTTP Flood",
        "color": "#22c55e",
        "border": "#16a34a",
        "threat": "A scanner is hammering the web server with hundreds of 404 requests per second.",
        "log_hint": "Start with <code>read_access_log</code> — look for an IP making far more requests than the others.",
        "fix": "One action: <code>block_ip(&lt;attacker_ip&gt;)</code>",
        "warn": None,
    },
    "medium": {
        "label": "Medium — SSH Brute-Force",
        "color": "#f97316",
        "border": "#ea580c",
        "threat": "Repeated failed SSH login attempts are flooding the auth log from a single source.",
        "log_hint": "Use <code>read_auth_log</code> — the attacker generates far more failed attempts than anyone else.",
        "fix": "One action: <code>block_ip(&lt;attacker_ip&gt;)</code>",
        "warn": "An admin IP is mixed in the logs. Blocking it is a fatal mistake.",
    },
    "hard": {
        "label": "Hard — Webshell C2",
        "color": "#ef4444",
        "border": "#dc2626",
        "threat": "A webshell has been planted and is making C2 callbacks. A malicious process is running.",
        "log_hint": "Use <code>read_access_log</code> — find the backdoor filename and a PID in brackets.",
        "fix": "Three actions (any order): <code>block_ip</code> + <code>delete_file</code> + <code>kill_process</code>",
        "warn": "All three must succeed. Partial neutralisation keeps done=False.",
    },
    "": {
        "label": "No Active Episode",
        "color": "#6b7280",
        "border": "#4b5563",
        "threat": "Press Reset to begin. Scenarios cycle: Easy \u2192 Medium \u2192 Hard \u2192 Easy\u2026",
        "log_hint": None,
        "fix": None,
        "warn": None,
    },
}

REWARD_TABLE = [
    ("+0.50", "Correct investigative log for the scenario", "positive"),
    ("+0.50", "Correct remediation action on the right target", "positive"),
    ("+0.25", "Correct investigative direction but wrong log file", "partial"),
    ("+0.10", "Correct tool, wrong IP / file / PID", "partial"),
    ("\u22120.20", "kill_process on a PID that doesn't exist", "negative"),
    ("\u22120.25", "Reading logs after all remediation tools used (stalling)", "negative"),
    ("\u22120.30", "Repeating the same log read or already-blocked action", "negative"),
    ("\u22120.50", "Wrong tool for the scenario", "negative"),
    ("\u22120.75", "Deleting a wrong file", "negative"),
    ("\u22121.00", "Blocking the admin IP (medium scenario)", "fatal"),
    ("\u22121.00", "Attempting remediation without any prior investigation \u2192 episode ends", "fatal"),
]


# Scenario header

def scenario_header(scenario: str) -> str:
    m   = SCENARIO_META.get(scenario, SCENARIO_META[""])
    c   = m["color"]
    bdr = m["border"]

    warn_block = ""
    if m["warn"]:
        warn_block = (
            f'<div class="soc-warn-block">'
            f'\u26a0 {m["warn"]}</div>'
        )

    log_hint_block = ""
    if m["log_hint"]:
        log_hint_block = (
            f'<div class="soc-hint-line">'
            f'<span class="soc-hint-key">HOW TO INVESTIGATE \u2192 </span>{m["log_hint"]}</div>'
        )

    fix_block = ""
    if m["fix"]:
        fix_block = (
            f'<div class="soc-hint-line">'
            f'<span class="soc-hint-key">REMEDIATION \u2192 </span>{m["fix"]}</div>'
        )

    return (
        f'<div class="soc-scenario-card" style="border-color:{bdr};border-left-color:{c};">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
        f'<span class="soc-scenario-badge" style="background:{c}1a;border-color:{c};color:{c};">'
        f'{m["label"].upper()}</span></div>'
        f'<div class="soc-scenario-threat">{m["threat"]}</div>'
        f'{log_hint_block}{fix_block}{warn_block}'
        f'</div>'
    )


# Outcome banner

def outcome_banner(done: bool, success: bool, total_reward: float, step_count: int) -> str:
    if not done:
        return (
            '<div class="soc-outcome soc-outcome-running">'
            '\u25cf Episode running \u2014 investigate then remediate the threat.'
            '</div>'
        )
    if success:
        return (
            '<div class="soc-outcome soc-outcome-success">'
            '<div class="soc-outcome-title">\u2713 THREAT NEUTRALISED</div>'
            f'<div class="soc-outcome-sub">'
            f'Completed in {step_count} steps &nbsp;\u00b7&nbsp; '
            f'Total reward: {total_reward:+.2f} &nbsp;\u00b7&nbsp; '
            f'Press Reset to load the next scenario.</div>'
            '</div>'
        )
    return (
        '<div class="soc-outcome soc-outcome-fail">'
        '<div class="soc-outcome-title">\u2717 EPISODE FAILED</div>'
        f'<div class="soc-outcome-sub">'
        f'Ended at step {step_count} &nbsp;\u00b7&nbsp; '
        f'Total reward: {total_reward:+.2f} &nbsp;\u00b7&nbsp; '
        f'Press Reset to try again.</div>'
        '</div>'
    )


# Hard scenario progress tracker

def hard_progress(ip_blocked: bool, file_deleted: bool, process_killed: bool) -> str:
    """
    Visual checklist for the three required hard-scenario actions.
    All three can be completed in any order - no enforced sequence.
    Only rendered when scenario == 'hard'.
    """
    def pill(label: str, done: bool) -> str:
        cls = "soc-pill soc-pill-done" if done else "soc-pill soc-pill-pending"
        icon = "\u2713" if done else "\u25cb"
        return f'<span class="{cls}">{icon} {label}</span>'

    return (
        '<div class="soc-progress-box">'
        '<div class="soc-progress-label">HARD SCENARIO PROGRESS</div>'
        '<div style="display:flex;gap:10px;flex-wrap:wrap;">'
        + pill("block_ip", ip_blocked)
        + pill("delete_file", file_deleted)
        + pill("kill_process", process_killed)
        + '</div></div>'
    )


# Action history table

def action_history_table(history: list) -> str:
    if not history:
        return '<div class="soc-empty-state">No actions taken yet.</div>'

    def reward_color(r: float) -> str:
        if r >= 0.4:  return "#22c55e"
        if r > 0:     return "#84cc16"
        if r > -0.3:  return "#f97316"
        return "#ef4444"

    def tool_color(tool: str) -> str:
        return "#38bdf8" if tool in ("read_access_log", "read_auth_log") else "#c084fc"

    rows = ""
    for entry in reversed(history):
        r   = entry["reward"]
        rc  = reward_color(r)
        tc  = tool_color(entry["tool"])
        icon = "\u2713" if entry["success"] else ("\u2192" if r > 0 else "\u2717")
        ic  = "#22c55e" if entry["success"] else ("#f97316" if r > 0 else "#ef4444")
        result_short = entry["result"][:90] + ("\u2026" if len(entry["result"]) > 90 else "")

        rows += (
            f'<tr class="soc-hist-row">'
            f'<td class="soc-hist-cell soc-hist-step">#{entry["step"]}</td>'
            f'<td class="soc-hist-cell">'
            f'<span style="color:{tc};font-weight:700;font-size:12px;">{entry["tool"]}</span>'
            f'</td>'
            f'<td class="soc-hist-cell soc-hist-param">{entry["param"]}</td>'
            f'<td class="soc-hist-cell" style="color:{rc};font-weight:700;font-size:13px;">{r:+.2f}</td>'
            f'<td class="soc-hist-cell" style="color:{ic};font-weight:700;">{icon}</td>'
            f'<td class="soc-hist-cell soc-hist-feedback">{result_short}</td>'
            f'</tr>'
        )

    return (
        '<div style="overflow-x:auto;">'
        '<table class="soc-hist-table">'
        '<thead><tr class="soc-hist-header">'
        '<th class="soc-hist-th">STEP</th>'
        '<th class="soc-hist-th">TOOL</th>'
        '<th class="soc-hist-th">PARAM</th>'
        '<th class="soc-hist-th">REWARD</th>'
        '<th class="soc-hist-th"></th>'
        '<th class="soc-hist-th">FEEDBACK</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


# Per-step reward bar chart (SVG)

def reward_chart_svg(history: List[Tuple[int, float, str]]) -> str:
    """
    history: list of (step_number, reward_for_that_step, tool_name)
    Renders a per-step bar chart. Positive bars go up (green), negative down (red).
    Axis lines and labels use CSS classes so they are visible on both themes.
    """
    if not history:
        return '<div class="soc-chart-empty">Reward chart will appear here as actions are taken.</div>'

    W, H    = 680, 148
    MID     = 80
    MAX_BAR = 60
    BAR_W   = max(14, min(40, (W - 80) // len(history) - 6))
    GAP     = max(4, (W - 80 - len(history) * BAR_W) // max(len(history), 1))
    start_x = 48

    def bar_color(r: float) -> str:
        if r >= 0.4:   return "#22c55e"
        if r > 0:      return "#84cc16"
        if r >= -0.25: return "#f97316"
        return "#ef4444"

    bars = ""
    for i, (step, r, tool) in enumerate(history):
        bx    = start_x + i * (BAR_W + GAP)
        h     = abs(r) * MAX_BAR
        by    = MID - h if r >= 0 else MID
        color = bar_color(r)

        bars += (
            f'<rect x="{bx:.0f}" y="{by:.1f}" width="{BAR_W}" '
            f'height="{max(h, 2):.1f}" rx="3" fill="{color}" opacity="0.92"/>'
        )
        label_y = (by - 5) if r >= 0 else (by + h + 12)
        bars += (
            f'<text x="{bx + BAR_W/2:.0f}" y="{label_y:.0f}" '
            f'text-anchor="middle" font-size="9" fill="{color}" '
            f'font-family="monospace" font-weight="700">{r:+.1f}</text>'
        )
        bars += (
            f'<text x="{bx + BAR_W/2:.0f}" y="{H - 5}" '
            f'text-anchor="middle" font-size="9" '
            f'class="soc-chart-axis-text" font-family="monospace">#{step}</text>'
        )

    axis = (
        f'<line x1="40" y1="{MID}" x2="{W - 8}" y2="{MID}" '
        f'class="soc-chart-baseline" stroke-width="1.5"/>'
        f'<line x1="40" y1="{MID - MAX_BAR * 0.5:.0f}" x2="{W-8}" '
        f'y2="{MID - MAX_BAR * 0.5:.0f}" class="soc-chart-grid" '
        f'stroke-width="0.5" stroke-dasharray="3 3"/>'
        f'<line x1="40" y1="{MID + MAX_BAR * 0.5:.0f}" x2="{W-8}" '
        f'y2="{MID + MAX_BAR * 0.5:.0f}" class="soc-chart-grid" '
        f'stroke-width="0.5" stroke-dasharray="3 3"/>'
        f'<text x="36" y="{MID - MAX_BAR + 4}" text-anchor="end" font-size="9" '
        f'class="soc-chart-axis-text" font-family="monospace">+1.0</text>'
        f'<text x="36" y="{MID - MAX_BAR*0.5 + 4:.0f}" text-anchor="end" font-size="9" '
        f'class="soc-chart-axis-text" font-family="monospace">+0.5</text>'
        f'<text x="36" y="{MID + 4}" text-anchor="end" font-size="9" '
        f'class="soc-chart-axis-text" font-family="monospace">0</text>'
        f'<text x="36" y="{MID + MAX_BAR*0.5 + 4:.0f}" text-anchor="end" font-size="9" '
        f'class="soc-chart-axis-text" font-family="monospace">-0.5</text>'
        f'<text x="36" y="{MID + MAX_BAR + 4}" text-anchor="end" font-size="9" '
        f'class="soc-chart-axis-text" font-family="monospace">-1.0</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'class="soc-chart-svg">'
        f'{axis}{bars}'
        f'</svg>'
    )


# Reward reference table

def reward_reference_html() -> str:
    color_map = {
        "positive": ("#14532d", "#16a34a", "#4ade80"),
        "partial":  ("#713f12", "#ca8a04", "#fde047"),
        "negative": ("#7c2d12", "#c2410c", "#fb923c"),
        "fatal":    ("#7f1d1d", "#b91c1c", "#fca5a5"),
    }

    rows = ""
    for reward_str, description, kind in REWARD_TABLE:
        bg, border, text = color_map[kind]
        rows += (
            f'<tr class="soc-ref-row">'
            f'<td style="padding:7px 12px;">'
            f'<span style="background:{bg};border:1px solid {border};color:{text};'
            f'font-family:monospace;font-size:12px;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;white-space:nowrap;">{reward_str}</span>'
            f'</td>'
            f'<td class="soc-ref-desc">{description}</td>'
            f'</tr>'
        )

    return (
        '<table class="soc-ref-table">'
        '<thead><tr class="soc-ref-header">'
        '<th class="soc-ref-th">REWARD</th>'
        '<th class="soc-ref-th">CONDITION</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


# Scenario quick-reference

def scenario_reference_html() -> str:
    rows = [
        ("Easy",   "#22c55e", "access.log", "404 flood from random attacker IP",
         "block_ip(attacker)", "1 action"),
        ("Medium", "#f97316", "auth.log",   "SSH brute-force + whitelisted admin IP mixed in",
         "block_ip(attacker)", "1 action, don't block admin"),
        ("Hard",   "#ef4444", "access.log", "Webshell C2 + backdoor file + rogue process",
         "block_ip + delete_file + kill_process", "3 actions, any order"),
    ]
    tbody = ""
    for label, color, log_src, pattern, fix, note in rows:
        tbody += (
            f'<tr class="soc-ref-row">'
            f'<td style="padding:8px 12px;">'
            f'<span style="color:{color};font-weight:700;font-family:monospace;">{label}</span>'
            f'</td>'
            f'<td class="soc-ref-cell-mono">{log_src}</td>'
            f'<td class="soc-ref-cell">{pattern}</td>'
            f'<td class="soc-ref-cell-fix">{fix}</td>'
            f'<td class="soc-ref-cell-note">{note}</td>'
            f'</tr>'
        )
    return (
        '<table class="soc-ref-table">'
        '<thead><tr class="soc-ref-header">'
        '<th class="soc-ref-th">SCENARIO</th>'
        '<th class="soc-ref-th">LOG</th>'
        '<th class="soc-ref-th">ATTACK PATTERN</th>'
        '<th class="soc-ref-th">CORRECT TOOL(S)</th>'
        '<th class="soc-ref-th">NOTE</th>'
        '</tr></thead>'
        f'<tbody>{tbody}</tbody></table>'
    )


# Stat card

def stat_card(label: str, value: str, color: str = "#38bdf8") -> str:
    return (
        f'<div class="soc-stat-card">'
        f'<div class="soc-stat-label">{label}</div>'
        f'<div class="soc-stat-value" style="color:{color};">{value}</div>'
        f'</div>'
    )