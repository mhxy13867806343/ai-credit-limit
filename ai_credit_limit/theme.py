from __future__ import annotations

"""Theme and QSS Stylesheet configuration for AI Credit Limit UI."""

# ─── Dark Palette Configuration ──────────────────────────────────────────────

DARK_PALETTE_COLORS = {
    "window": "#16181d",
    "window_text": "#f3f4f6",
    "base": "#1c2027",
    "alternate_base": "#22262d",
    "text": "#f3f4f6",
    "button": "#2b3038",
    "button_text": "#f3f4f6",
    "highlight": "#4f8cff",
    "highlighted_text": "#ffffff",
}


# ─── Main Window Global QSS ──────────────────────────────────────────────────

MAIN_WINDOW_STYLE = """
    QWidget#root {
        background: #14171d;
    }
    QLabel#appTitle {
        font-size: 24px;
        font-weight: bold;
        color: #f8fafc;
    }
    QLabel#muted {
        color: #94a3b8;
        font-size: 13px;
    }
    QLabel#statusLabel {
        color: #94a3b8;
        font-size: 13px;
        padding-right: 6px;
    }
    QLabel#footer {
        color: #64748b;
        font-size: 12px;
    }
    QFrame#tabsHost {
        background: #1e222b;
        border: 1px solid #2d3340;
        border-radius: 14px;
    }
    QPushButton#providerTab {
        background: #252b36;
        color: #cbd5e1;
        border: 1px solid #333b4b;
        border-radius: 10px;
        padding: 8px 14px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton#providerTab:hover {
        background: #2d3442;
        color: #ffffff;
    }
    QPushButton#providerTab:checked {
        background: #2a354d;
        color: #ffffff;
        border: 1px solid #4f8cff;
    }
    QFrame#card {
        background: #1b2028;
        border: 1px solid #2b3240;
        border-radius: 16px;
    }
    QLabel#appName {
        font-size: 20px;
        font-weight: bold;
        color: #ffffff;
    }
    QLabel#metric {
        font-size: 32px;
        font-weight: bold;
        color: #ffffff;
    }
    QLabel#metricCaption {
        font-size: 12px;
        color: #94a3b8;
    }
    QLabel#message {
        font-size: 14px;
        color: #e2e8f0;
    }
    QProgressBar {
        border: 0;
        border-radius: 6px;
        background: #2a313e;
        height: 12px;
        text-align: center;
        color: transparent;
    }
    QPushButton {
        background: #282e38;
        color: #f1f5f9;
        border: 1px solid #3b4354;
        border-radius: 10px;
        padding: 7px 15px;
        font-size: 13px;
    }
    QPushButton:hover {
        background: #343c49;
    }
    QLineEdit, QTextEdit, QListWidget {
        background: #181c24;
        color: #f8fafc;
        border: 1px solid #333b4b;
        border-radius: 10px;
        padding: 8px;
        font-size: 13px;
        selection-background-color: #4f8cff;
    }
    QCheckBox {
        color: #f8fafc;
        font-size: 14px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid #475569;
        background: #1e293b;
    }
    QCheckBox::indicator:checked {
        background: #4f8cff;
        border-color: #4f8cff;
    }
"""


# ─── Usage Card & Quota Item QSS ─────────────────────────────────────────────

QUOTA_ITEM_FRAME_STYLE = """
    QFrame#quotaItemFrame {
        background: #181c25;
        border: 1px solid #2d3444;
        border-radius: 8px;
    }
"""

METRIC_PILL_STYLE = """
    QFrame#pill {
        background: #1f242d;
        border: 1px solid #2d3440;
        border-radius: 8px;
    }
"""

PLAN_BADGE_STYLE = "background: #183225; color: #75e6a0; border-radius: 8px; padding: 5px 9px; font-weight: 700;"


def progress_bar_style_for_percent(percent: float) -> str:
    """Return dynamic linear gradient QSS style for progress bar based on percentage used."""
    if percent >= 85:
        gradient = "stop:0 #fb7185, stop:1 #f97316"
    elif percent >= 60:
        gradient = "stop:0 #fbbf24, stop:1 #8b7cff"
    else:
        gradient = "stop:0 #35d0ba, stop:1 #7c6cff"
    return (
        f"QProgressBar {{ border: 0; border-radius: 4px; background: #2b313e; height: 8px; text-align: center; color: transparent; }}"
        f"QProgressBar::chunk {{ border-radius: 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {gradient}); }}"
    )


# ─── Auto Refresh Panel QSS ──────────────────────────────────────────────────

AUTO_REFRESH_PANEL_STYLE = """
    QFrame#autoRefreshPanel {
        background: #1a1f2b;
        border: 1px solid #3c4460;
        border-radius: 12px;
    }
    QPushButton#arPreset {
        background: #252c3b;
        color: #b0bbd0;
        border: 1px solid #374050;
        border-radius: 6px;
        font-size: 12px;
        padding: 0;
    }
    QPushButton#arPreset:checked {
        background: #2e2060;
        color: #c8b8ff;
        border: 1px solid #7c6cff;
        font-weight: 700;
    }
    QPushButton#arPreset:hover {
        background: #303848;
        color: #ffffff;
    }
    QPushButton#arToggle {
        background: #1e3a26;
        color: #6ee7a0;
        border: 1px solid #2d5c3a;
        border-radius: 8px;
        font-weight: 700;
        font-size: 13px;
    }
    QPushButton#arToggle[active="stop"] {
        background: #3a1e1e;
        color: #f87171;
        border: 1px solid #5c2d2d;
    }
    QPushButton {
        background: #262c35;
        color: #c3cad7;
        border: 1px solid #404754;
        border-radius: 6px;
        padding: 4px 10px;
    }
    QPushButton:hover {
        background: #343b46;
    }
    QLineEdit {
        background: #1c2130;
        color: #e8eaf6;
        border: 1px solid #374050;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        selection-background-color: #4f8cff;
    }
"""
