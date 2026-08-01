from __future__ import annotations

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import QApplication


def make_app_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#7c6cff"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, size, size, int(size * 0.22), int(size * 0.22))
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(max(12, int(size * 0.34)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "AI")
    painter.end()
    return QIcon(pixmap)


def make_provider_icon(name: str, app_id: str, size: int = 44) -> QIcon:
    colors = {
        "codex": "#10b981",
        "claude_code": "#f97316",
        "antigravity": "#4f8cff",
        "workbuddy": "#00c853",
    }
    initials = {
        "codex": "Cx",
        "claude_code": "Cc",
        "antigravity": "Ag",
        "workbuddy": "Wb",
    }
    color = colors.get(app_id, "#7c6cff")
    text = initials.get(app_id, "".join(part[:1] for part in name.split()[:2]).upper() or "AI")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 12, 12)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(12)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, text[:2])
    painter.end()
    return QIcon(pixmap)


def format_tokens(value: int) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


from .theme import DARK_PALETTE_COLORS


def set_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(DARK_PALETTE_COLORS["window"]))
    palette.setColor(QPalette.WindowText, QColor(DARK_PALETTE_COLORS["window_text"]))
    palette.setColor(QPalette.Base, QColor(DARK_PALETTE_COLORS["base"]))
    palette.setColor(QPalette.AlternateBase, QColor(DARK_PALETTE_COLORS["alternate_base"]))
    palette.setColor(QPalette.Text, QColor(DARK_PALETTE_COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(DARK_PALETTE_COLORS["button"]))
    palette.setColor(QPalette.ButtonText, QColor(DARK_PALETTE_COLORS["button_text"]))
    palette.setColor(QPalette.Highlight, QColor(DARK_PALETTE_COLORS["highlight"]))
    palette.setColor(QPalette.HighlightedText, QColor(DARK_PALETTE_COLORS["highlighted_text"]))
    app.setPalette(palette)


def hide_dock_icon_mac() -> None:
    """Hide macOS Dock icon so the app operates solely as a Menu Bar Status Bar accessory app."""
    import ctypes
    import platform

    if platform.system() != "Darwin":
        return
    try:
        objc = ctypes.cdll.LoadLibrary("libobjc.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p

        NSApplication = objc.objc_getClass(b"NSApplication")
        sharedApplication = objc.sel_registerName(b"sharedApplication")
        setActivationPolicy = objc.sel_registerName(b"setActivationPolicy:")

        app_ptr = objc.objc_msgSend(NSApplication, sharedApplication)
        # 1 = NSApplicationActivationPolicyAccessory (不在 Dock 栏占位，做纯 Menu Bar 菜单栏应用)
        objc.objc_msgSend(app_ptr, setActivationPolicy, ctypes.c_long(1))
    except Exception:
        pass
