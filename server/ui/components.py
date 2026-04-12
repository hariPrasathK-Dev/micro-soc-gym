# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Pure HTML/SVG string generators for the Micro-SOC Gym UI.

No Gradio imports. No state. Every function takes plain data and
returns an HTML string. This makes them trivially testable and
keeps the layout file free of string-building noise.
"""

from __future__ import annotations
from typing import List, Tuple


# Scenario metadata
SCENARIO_META = {
    "easy": {
        "label": "Easy — HTTP Flood",
        "color": "#4ade80",
        "dim": "#14532d",
        "border": "#16a34a",
        "threat": "A scanner is hammering the web server with hundreds of 404 requests per second.",
        "log_hint": "Start with <code>read_access_log</code> — look for an IP making far more requests than the others.",
        "fix": "One action: <code>block_ip(&lt;attacker_ip&gt;)</code>",
        "warn": None,
    },
    "medium": {
        "label": "Medium — SSH Brute-Force",
        "color": "#fb923c",
        "dim": "#431407",
        "border": "#ea580c",
        "threat": "Repeated failed SSH login attempts are flooding the auth log from a single source.",
        "log_hint": "Use <code>read_auth_log</code> — the attacker generates far more failed attempts than anyone else.",
        "fix": "One action: <code>block_ip(&lt;attacker_ip&gt;)</code>",
        "warn": "An admin IP is mixed in the logs. Blocking it is a fatal mistake.",
    },
    "hard": {
        "label": "Hard — Webshell C2",
        "color": "#f87171",
        "dim": "#450a0a",
        "border": "#dc2626",
        "threat": "A webshell has been planted and is making C2 callbacks. A malicious process is running.",
        "log_hint": "Use <code>read_access_log</code> — find the backdoor filename and a PID in brackets.",
        "fix": "Three actions : <code>block_ip</code> + <code>delete_file</code> + <code>kill_process</code>",
        "warn": "All three must succeed. Partial neutralisation keeps done=False.",
    },
    "": {
        "label": "No Active Episode",
        "color": "#64748b",
        "dim": "#0f172a",
        "border": "#334155",
        "threat": "Press Reset to begin. Scenarios cycle: Easy → Medium → Hard → Easy…",
        "log_hint": None,
        "fix": None,
        "warn": None,
    },
}

# Reward constants mirrored from constants.py for the reference table
REWARD_TABLE = [
    ("+0.50", "Correct investigative log for the scenario", "positive"),
    ("+0.50", "Correct remediation action on the right target", "positive"),
    ("+0.25", "Correct investigative direction but wrong log file", "partial"),
    ("+0.10", "Correct tool, wrong IP / file / PID", "partial"),
    ("-0.20", "kill_process on a PID that doesn't exist", "negative"),
    ("-0.25", "Reading logs after all remediation tools used (stalling)", "negative"),
    ("-0.30", "Repeating the same log read or already-blocked action", "negative"),
    ("-0.50", "Wrong tool for the scenario", "negative"),
    ("-0.75", "Deleting a wrong file", "negative"),
    ("-1.00", "Blocking the admin IP (medium scenario)", "fatal"),
    ("-1.00", "Attempting remediation without any prior investigation → episode ends", "fatal"),
]


# Scenario header: returns scenario based warning, log, and fix UI 
def scenario_header(scenario: str) -> str:
    m = SCENARIO_META.get(scenario, SCENARIO_META[""])
    c, dim, bdr = m["color"], m["dim"], m["border"]

    warn_block = ""
    if m["warn"]:
        warn_block = (
            f'<div style="margin-top:10px;padding:8px 12px;background:#2d1515;'
            f'border-left:3px solid #ef4444;border-radius:4px;'
            f'font-size:12px;color:#fca5a5;font-family:monospace;">'
            f'⚠ {m["warn"]}</div>'
        )

    log_hint_block = ""
    if m["log_hint"]:
        log_hint_block = (
            f'<div style="margin-top:8px;font-size:12px;color:#94a3b8;">'
            f'<span style="color:#64748b;">HOW TO INVESTIGATE → </span>{m["log_hint"]}</div>'
        )

    fix_block = ""
    if m["fix"]:
        fix_block = (
            f'<div style="margin-top:6px;font-size:12px;color:#94a3b8;">'
            f'<span style="color:#64748b;">REMEDIATION → </span>{m["fix"]}</div>'
        )

    return (
        f'<div style="background:{dim};border:1px solid {bdr};border-left:4px solid {c};'
        f'border-radius:8px;padding:14px 18px;font-family:monospace;line-height:1.75;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">'
        f'<span style="background:{c}22;border:1px solid {c};color:{c};'
        f'font-size:11px;font-weight:700;padding:2px 10px;border-radius:12px;'
        f'letter-spacing:0.5px;">{m["label"].upper()}</span></div>'
        f'<div style="font-size:13px;color:#e2e8f0;margin-top:4px;">{m["threat"]}</div>'
        f'{log_hint_block}{fix_block}{warn_block}'
        f'</div>'
    )


# Outcome banner: displays the results of the episode
# Should it display just the reward for the agent or also the grader value? this thing i have no idea 
def outcome_banner(done: bool, success: bool, total_reward: float, step_count: int) -> str:
    if not done:
        return (
            '<div style="background:#111827;border:1px solid #1f2d3d;border-radius:8px;'
            'padding:12px 18px;font-family:monospace;font-size:13px;color:#475569;">'
            '● Episode running — investigate then remediate the threat.'
            '</div>'
        )
    if success:
        return (
            '<div style="background:#052e16;border:2px solid #16a34a;border-radius:8px;'
            'padding:16px 20px;font-family:monospace;">'
            '<div style="font-size:15px;font-weight:700;color:#4ade80;">✓ THREAT NEUTRALISED</div>'
            f'<div style="font-size:12px;color:#86efac;margin-top:4px;">'
            f'Completed in {step_count} steps &nbsp;·&nbsp; Total reward: {total_reward:+.2f} &nbsp;·&nbsp; '
            f'Press Reset to load the next scenario.</div>'
            '</div>'
        )
    return (
        '<div style="background:#2d0a0a;border:2px solid #dc2626;border-radius:8px;'
        'padding:16px 20px;font-family:monospace;">'
        '<div style="font-size:15px;font-weight:700;color:#f87171;">✗ EPISODE FAILED</div>'
        f'<div style="font-size:12px;color:#fca5a5;margin-top:4px;">'
        f'Ended at step {step_count} &nbsp;·&nbsp; Total reward: {total_reward:+.2f} &nbsp;·&nbsp; '
        f'Press Reset to try again.</div>'
        '</div>'
    )


# Hard scenario progress tracker: checks for all the three completed actions (block_ip; delete_file; kill_process) and 
# renders the UI visuals based on 'done' parameter
def hard_progress(ip_blocked: bool, file_deleted: bool, process_killed: bool) -> str:
    """
    Visual checklist for the three required hard-scenario actions.
    Only rendered when scenario == 'hard'.

    All three actions are required but can be completed in ANY order —
    the environment's done=True fires the moment all three conditions
    are satisfied simultaneously. There is no enforced sequence.
    """
    def pill(label: str, done: bool) -> str:
        bg = "#052e16" if done else "#1e293b"
        border = "#16a34a" if done else "#334155"
        color = "#4ade80" if done else "#475569"
        icon = "✓" if done else "○"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{bg};border:1px solid {border};color:{color};'
            f'font-size:12px;font-family:monospace;padding:5px 12px;border-radius:20px;">'
            f'{icon} {label}</span>'
        )

    return (
        '<div style="background:#111827;border:1px solid #1f2d3d;border-radius:8px;'
        'padding:12px 16px;margin-top:8px;">'
        '<div style="font-size:11px;color:#475569;font-family:monospace;'
        'letter-spacing:0.5px;margin-bottom:8px;">HARD SCENARIO PROGRESS</div>'
        '<div style="display:flex;gap:10px;flex-wrap:wrap;">'
        + pill("block_ip", ip_blocked)
        + pill("delete_file", file_deleted)
        + pill("kill_process", process_killed)
        + '</div></div>'
    )


# Action history table: returns the history of steps, tools, parameters, rewards and feedback
def action_history_table(history: list) -> str:
    if not history:
        return (
            '<div style="color:#334155;font-style:italic;font-family:monospace;'
            'font-size:13px;padding:16px 0;text-align:center;">'
            'No actions taken yet.</div>'
        )

    def reward_color(r: float) -> str:
        if r >= 0.4:
            return "#4ade80"
        if r > 0:
            return "#a3e635"
        if r > -0.3:
            return "#fb923c"
        return "#f87171"

    def tool_color(tool: str) -> str:
        if tool in ("read_access_log", "read_auth_log"):
            return "#38bdf8"  # blue — investigative
        return "#c084fc"      # purple — remediation

    rows = ""
    for entry in reversed(history):   # most recent first
        r = entry["reward"]
        rc = reward_color(r)
        tc = tool_color(entry["tool"])
        icon = "✓" if entry["success"] else ("→" if r > 0 else "✗")
        icon_color = "#4ade80" if entry["success"] else ("#fb923c" if r > 0 else "#f87171")
        result_short = entry["result"][:90] + ("…" if len(entry["result"]) > 90 else "")
        rows += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:7px 10px;color:#475569;font-size:11px;">#{entry["step"]}</td>'
            f'<td style="padding:7px 10px;">'
            f'  <span style="color:{tc};font-weight:700;font-size:12px;">{entry["tool"]}</span>'
            f'</td>'
            f'<td style="padding:7px 10px;color:#94a3b8;font-size:12px;max-width:140px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{entry["param"]}</td>'
            f'<td style="padding:7px 10px;color:{rc};font-weight:700;font-size:13px;">{r:+.2f}</td>'
            f'<td style="padding:7px 10px;color:{icon_color};font-weight:700;">{icon}</td>'
            f'<td style="padding:7px 10px;color:#64748b;font-size:11px;font-family:monospace;">'
            f'{result_short}</td>'
            f'</tr>'
        )

    return (
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-family:monospace;">'
        '<thead><tr style="border-bottom:2px solid #1e293b;">'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;">STEP</th>'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;">TOOL</th>'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;">PARAM</th>'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;">REWARD</th>'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;"></th>'
        '<th style="text-align:left;padding:6px 10px;color:#334155;font-size:11px;font-weight:600;">FEEDBACK</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


# Per-step reward bar chart (SVG): this is kind of different when compared to the progress of line chart
# Also this corresponds to only the rewards and not the grader values, idk is this fine enough
def reward_chart_svg(history: List[Tuple[int, float, str]]) -> str:
    """
    history: list of (step_number, reward_for_that_step, tool_name)
    Renders a per-step bar chart — each bar is one action's reward.
    Positive bars go up (green), negative go down (red), zero stays and is clearly differentiable
    """
    if not history:
        return (
            '<div style="height:110px;display:flex;align-items:center;justify-content:center;'
            'color:#1e293b;font-family:monospace;font-size:12px;">'
            'Reward chart will appear here as actions are taken.'
            '</div>'
        )

    W, H = 680, 140
    MID = 76          # y-coordinate of the zero baseline
    MAX_BAR = 60      # pixels for ±1.0 reward
    BAR_W = max(14, min(36, (W - 80) // len(history) - 6))
    GAP = max(4, (W - 80 - len(history) * BAR_W) // max(len(history), 1))
    start_x = 48

    def bar_color(r: float, tool: str) -> str:
        if r >= 0.4:
            return "#4ade80"
        if r > 0:
            return "#a3e635"
        if r >= -0.25:
            return "#fb923c"
        return "#f87171"

    bars = ""
    for i, (step, r, tool) in enumerate(history):
        bx = start_x + i * (BAR_W + GAP)
        h = abs(r) * MAX_BAR
        by = MID - h if r >= 0 else MID
        color = bar_color(r, tool)
        # bar
        bars += (
            f'<rect x="{bx:.0f}" y="{by:.1f}" width="{BAR_W}" height="{max(h, 2):.1f}" '
            f'rx="3" fill="{color}" opacity="0.9"/>'
        )
        # reward label above/below bar
        label_y = (by - 5) if r >= 0 else (by + h + 12)
        bars += (
            f'<text x="{bx + BAR_W/2:.0f}" y="{label_y:.0f}" '
            f'text-anchor="middle" font-size="9" fill="{color}" font-family="monospace">'
            f'{r:+.1f}</text>'
        )
        # step number below
        bars += (
            f'<text x="{bx + BAR_W/2:.0f}" y="{H - 6}" '
            f'text-anchor="middle" font-size="9" fill="#334155" font-family="monospace">'
            f'#{step}</text>'
        )

    # axes
    axis = (
        f'<line x1="40" y1="{MID}" x2="{W - 8}" y2="{MID}" '
        f'stroke="#1e293b" stroke-width="1.5"/>'
        # +0.5 gridline
        f'<line x1="40" y1="{MID - MAX_BAR * 0.5:.0f}" x2="{W - 8}" y2="{MID - MAX_BAR * 0.5:.0f}" '
        f'stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3 3"/>'
        # −0.5 gridline
        f'<line x1="40" y1="{MID + MAX_BAR * 0.5:.0f}" x2="{W - 8}" y2="{MID + MAX_BAR * 0.5:.0f}" '
        f'stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3 3"/>'
        # y labels
        f'<text x="36" y="{MID - MAX_BAR + 4}" text-anchor="end" font-size="9" fill="#334155" font-family="monospace">+1.0</text>'
        f'<text x="36" y="{MID - MAX_BAR * 0.5 + 4:.0f}" text-anchor="end" font-size="9" fill="#334155" font-family="monospace">+0.5</text>'
        f'<text x="36" y="{MID + 4}" text-anchor="end" font-size="9" fill="#475569" font-family="monospace">0</text>'
        f'<text x="36" y="{MID + MAX_BAR * 0.5 + 4:.0f}" text-anchor="end" font-size="9" fill="#334155" font-family="monospace">−0.5</text>'
        f'<text x="36" y="{MID + MAX_BAR + 4}" text-anchor="end" font-size="9" fill="#334155" font-family="monospace">−1.0</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0a0f1a;border-radius:8px;display:block;">'
        f'{axis}{bars}'
        f'</svg>'
    )


# Reward reference table
def reward_reference_html() -> str:
    color_map = {
        "positive": ("#052e16", "#16a34a", "#4ade80"),
        "partial":  ("#1c1a05", "#854f0b", "#fbbf24"),
        "negative": ("#1a0f05", "#7c2d12", "#fb923c"),
        "fatal":    ("#2d0a0a", "#991b1b", "#f87171"),
    }

    rows = ""
    for reward_str, description, kind in REWARD_TABLE:
        bg, border, text = color_map[kind]
        rows += (
            f'<tr style="border-bottom:1px solid #0f172a;">'
            f'<td style="padding:7px 12px;">'
            f'  <span style="background:{bg};border:1px solid {border};color:{text};'
            f'  font-family:monospace;font-size:12px;font-weight:700;'
            f'  padding:2px 8px;border-radius:4px;">{reward_str}</span>'
            f'</td>'
            f'<td style="padding:7px 12px;color:#94a3b8;font-size:12px;">{description}</td>'
            f'</tr>'
        )

    return (
        '<table style="width:100%;border-collapse:collapse;">'
        '<thead><tr style="border-bottom:2px solid #1e293b;">'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;font-weight:600;">REWARD</th>'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;font-weight:600;">CONDITION</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


# Scenario quick-reference
def scenario_reference_html() -> str:
    rows = [
        ("Easy", "#4ade80", "access.log", "404 flood from random attacker IP",
         "block_ip(attacker)", "1 action"),
        ("Medium", "#fb923c", "auth.log", "SSH brute-force + whitelisted admin IP mixed in",
         "block_ip(attacker)", "1 action, don't block admin"),
        ("Hard", "#f87171", "access.log", "Webshell C2 + backdoor file + rogue process",
         "block_ip + delete_file + kill_process", "3 actions, any order"),
    ]
    tbody = ""
    for label, color, log_src, pattern, fix, note in rows:
        tbody += (
            f'<tr style="border-bottom:1px solid #0f172a;">'
            f'<td style="padding:8px 12px;">'
            f'  <span style="color:{color};font-weight:700;font-family:monospace;">{label}</span>'
            f'</td>'
            f'<td style="padding:8px 12px;color:#64748b;font-size:12px;font-family:monospace;">{log_src}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;font-size:12px;">{pattern}</td>'
            f'<td style="padding:8px 12px;color:#38bdf8;font-size:12px;font-family:monospace;">{fix}</td>'
            f'<td style="padding:8px 12px;color:#475569;font-size:11px;">{note}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;">'
        '<thead><tr style="border-bottom:2px solid #1e293b;">'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;">SCENARIO</th>'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;">LOG</th>'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;">ATTACK PATTERN</th>'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;">CORRECT TOOL(S)</th>'
        '<th style="text-align:left;padding:6px 12px;color:#334155;font-size:11px;">NOTE</th>'
        '</tr></thead>'
        f'<tbody>{tbody}</tbody></table>'
    )


# Stat card
def stat_card(label: str, value: str, color: str = "#38bdf8") -> str:
    return (
        f'<div style="background:#111827;border:1px solid #1f2d3d;border-radius:8px;'
        f'padding:12px 16px;text-align:center;">'

            f'<div style="font-size:11px;color:#334155;font-family:monospace;'
            f'letter-spacing:0.5px;margin-bottom:4px;">{label}</div>'

            f'<div style="font-size:22px;font-weight:700;color:{color};'
            f'font-family:monospace;">{value}</div>'

        f'</div>'
    )