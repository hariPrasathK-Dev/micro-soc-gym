# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations
from typing import List, Tuple


# Scenario metadata
SCENARIO_META = {
    "easy": {
        "label": "Easy - HTTP 404 Flood",
        "color": "#22c55e",
        "border": "#16a34a",
        "alert": "<b>Alert Received:</b> External monitoring has detected an unusual spike in HTTP traffic and bandwidth consumption on the primary web server. Analyse and neutralise the root cause.",
    },
    "medium": {
        "label": "Medium - SSH Brute Force",
        "color": "#f97316",
        "border": "#ea580c",
        "alert": "<b>Alert Received:</b> Endpoint detection has flagged an anomalous pattern of authentication events and minor CPU spikes tied to remote access services. Analyse and neutralise the root cause.",
    },
    "hard": {
        "label": "Hard - Active Webshell C2",
        "color": "#ef4444",
        "border": "#dc2626",
        "alert": "<b>Alert Received:</b> Network monitors have detected persistent, suspicious traffic originating from within the web application itself. Analyse and neutralise the root cause.",
    },
    "": {
        "label": "No Active Episode",
        "color": "#6b7280",
        "border": "#4b5563",
        "alert": "Click the New Episode button to load a scenario. Scenarios cycle: Easy \u2192 Medium \u2192 Hard \u2192 Easy...",
    },
}

REWARD_TABLE = [
    ("+0.50", "Correct investigative log for the scenario", "positive"),
    ("+0.50", "Correct remediation action on the right target", "positive"),
    ("+0.25", "Correct investigative direction but wrong log file", "partial"),
    ("+0.10", "Correct tool, wrong IP / PID", "partial"),
    ("\u22120.20", "kill_process on a PID that doesn't exist", "negative"),
    ("\u22120.25", "Reading logs after all remediation tools used (stalling)", "negative"),
    ("\u22120.30", "Repeating an action with no changes", "negative"),
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

    return (
        f'<div class="soc-scenario-card" style="border-color:{bdr};border-left-color:{c};">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
        f'<span class="soc-scenario-badge" style="background:{c}1a;border-color:{c};color:{c};padding:4px 8px;font-weight:700;font-size:14px;border-radius:4px;">'
        f'{m["label"].upper()}</span></div>'
        f'<div class="soc-scenario-threat" style="font-size:15px;">{m["alert"]}</div>'
        f'</div>'
    )


# Per-step reward bar chart
def reward_chart_svg(history: List[Tuple[int, float, str]]) -> str:
    if not history:
        return '<div class="soc-chart-empty">Reward chart will appear here as actions are taken.</div>'

    W, H    = 1200, 200
    MID     = 70
    MAX_BAR = 50
    BAR_W   = max(14, min(30, (W - 80) // 8 - 6))
    GAP     = max(4, (W - 80 - 8 * BAR_W) // 8)
    start_x = 60

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
            f'<text x="{bx + BAR_W/2:.0f}" y="{MID + MAX_BAR + 24}" '
            f'text-anchor="middle" font-size="10" fill="#e2e8f0" '
            f'font-family="monospace">{tool}()</text>'
        )

    axis = (
        f'<line x1="40" y1="{MID}" x2="{W - 8}" y2="{MID}" '
        f'class="soc-chart-baseline" stroke-width="1.5"/>'
        f'<line x1="40" y1="{MID - MAX_BAR * 0.5:.0f}" x2="{W - 8}" '
        f'y2="{MID - MAX_BAR * 0.5:.0f}" class="soc-chart-grid" '
        f'stroke-width="0.5" stroke-dasharray="3 3"/>'
        f'<line x1="40" y1="{MID + MAX_BAR * 0.5:.0f}" x2="{W - 8}" '
        f'y2="{MID + MAX_BAR * 0.5:.0f}" class="soc-chart-grid" '
        f'stroke-width="0.5" stroke-dasharray="3 3"/>'
        f'<text x="36" y="{MID - MAX_BAR + 4}" text-anchor="end" font-size="12" '
        f'fill="#e2e8f0" font-family="monospace">+1.0</text>'
        f'<text x="36" y="{MID - MAX_BAR*0.5 + 4:.0f}" text-anchor="end" font-size="12" '
        f'fill="#e2e8f0" font-family="monospace">+0.5</text>'
        f'<text x="36" y="{MID + 4}" text-anchor="end" font-size="12" '
        f'fill="#e2e8f0" font-family="monospace">0</text>'
        f'<text x="36" y="{MID + MAX_BAR*0.5 + 4:.0f}" text-anchor="end" font-size="12" '
        f'fill="#e2e8f0" font-family="monospace">-0.5</text>'
        f'<text x="36" y="{MID + MAX_BAR + 4}" text-anchor="end" font-size="12" '
        f'fill="#e2e8f0" font-family="monospace">-1.0</text>'
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

    def build_rows(kinds):
        r = ""
        for reward_str, description, kind in REWARD_TABLE:
            if kind not in kinds:
                continue
            bg, border, text = color_map[kind]
            r += (
                f'<tr class="soc-ref-row">'
                f'<td style="padding:7px 12px;white-space:nowrap;">'
                f'<span style="background:{bg};border:1px solid {border};color:{text};'
                f'font-family:monospace;font-size:12px;font-weight:700;'
                f'padding:2px 8px;border-radius:4px;">{reward_str}</span>'
                f'</td>'
                f'<td class="soc-ref-desc" style="width:100%;">{description}</td>'
                f'</tr>'
            )
        return r

    pos_rows = build_rows(["positive", "partial"])
    neg_rows = build_rows(["negative", "fatal"])

    def build_table(title, rows):
        return (
            '<div style="flex: 1; min-width: 0;">'
            f'<div style="font-size:12px;font-weight:700;color:var(--soc-text-primary);margin-bottom:8px;padding-left:12px;font-family:monospace;">{title}</div>'
            '<table class="soc-ref-table" style="width:100%;">'
            '<thead><tr class="soc-ref-header">'
            '<th class="soc-ref-th">VALUE</th>'
            '<th class="soc-ref-th" style="width:100%;">CONDITION</th>'
            '</tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            '</div>'
        )

    return (
        '<div style="display:flex; gap:24px; align-items:flex-start; width:100%;">'
        + build_table("REWARDS", pos_rows)
        + build_table("PENALTIES", neg_rows)
        + '</div>'
    )


# Scenario quick-reference
def scenario_reference_html() -> str:
    rows = [
        ("Easy",   "#22c55e", "access.log", "404 flood from random attacker IP",
         "block_ip(attacker)", "1 action"),
        ("Medium", "#f97316", "auth.log",   "SSH brute force with admin IP traffic mixed in",
         "block_ip(attacker)", "1 action, don't block admin"),
        ("Hard",   "#ef4444", "access.log", "A backdoor file planted by an attacker IP that runs a malicious process for an Active Webshell C2",
         "block_ip(attacker)<br>delete_file(backdoor)<br>kill_process(malicious process)", "3 actions, backdoor must be deleted before killing process"),
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
            f'<td class="soc-ref-cell-fix" style="white-space:nowrap;">{fix}</td>'
            f'<td class="soc-ref-cell-note" style="white-space:nowrap;">{note}</td>'
            f'</tr>'
        )
    return (
        '<table class="soc-ref-table">'
        '<thead><tr class="soc-ref-header">'
        '<th class="soc-ref-th">SCENARIO</th>'
        '<th class="soc-ref-th">LOG</th>'
        '<th class="soc-ref-th" style="width: 100%;">ATTACK PATTERN</th>'
        '<th class="soc-ref-th" style="white-space: nowrap;">CORRECT TOOL(S)</th>'
        '<th class="soc-ref-th" style="white-space: nowrap;">NOTE</th>'
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
