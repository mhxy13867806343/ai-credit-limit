from __future__ import annotations

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon

from .models import CreditUsage


class SystemTrayManager(QObject):
    show_window_requested = pyqtSignal()
    hide_window_requested = pyqtSignal()
    toggle_window_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._usages: list[CreditUsage] = []
        self._current_index = 0

        # 将 QSystemTrayIcon 挂载在全局 QApplication 上，确保与主窗口完全解耦，主窗口关闭/隐藏时托盘绝不消失
        app_instance = QApplication.instance()
        self.tray_icon = QSystemTrayIcon(app_instance if app_instance else self)
        self._build_menu()

        # 5 秒自动定时轮播各个 AI 工具的额度提示
        self.carousel_timer = QTimer(self)
        self.carousel_timer.setInterval(5000)
        self.carousel_timer.timeout.connect(self._rotate_display)

        self.tray_icon.activated.connect(self._on_tray_activated)

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e222b;
                color: #f3f4f6;
                border: 1px solid #2d3444;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #4f8cff;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2d3444;
                margin: 4px 8px;
            }
        """)

        self.toggle_action = QAction("显示/隐藏主界面", self)
        self.toggle_action.triggered.connect(self.toggle_window_requested.emit)

        self.refresh_action = QAction("🔄 立即刷新配额", self)
        self.refresh_action.triggered.connect(self.refresh_requested.emit)

        self.settings_action = QAction("⚙️ AI 工具设置", self)
        self.settings_action.triggered.connect(self.settings_requested.emit)

        self.quit_action = QAction("❌ 退出应用", self)
        self.quit_action.triggered.connect(self.quit_requested.emit)

        menu.addAction(self.toggle_action)
        menu.addAction(self.refresh_action)
        menu.addAction(self.settings_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(menu)

    def show(self) -> None:
        pass

    def setup(self) -> None:
        self.tray_icon.setIcon(self._create_tray_icon("AI", "--"))
        self.tray_icon.setToolTip("AI Credit Limit - 额度监控中")
        self.tray_icon.show()
        self.carousel_timer.start()

    def update_usages(self, usages: list[CreditUsage]) -> None:
        self._usages = usages
        if not self._usages:
            self.tray_icon.setToolTip("AI Credit Limit - 暂无数据")
            self.tray_icon.setIcon(self._create_tray_icon("AI", "--"))
            return

        self._update_tooltip()
        self._update_current_display()

    def _rotate_display(self) -> None:
        if not self._usages:
            return
        self._current_index = (self._current_index + 1) % len(self._usages)
        self._update_current_display()

    def _update_current_display(self) -> None:
        if not self._usages:
            return
        index = self._current_index % len(self._usages)
        usage = self._usages[index]

        tag = usage.app_name[:2].upper()
        if usage.app_id == "codex":
            tag = "Cx"
        elif usage.app_id == "antigravity":
            tag = "Ag"
        elif usage.app_id == "claude_code":
            tag = "Cc"
        elif usage.app_id == "workbuddy":
            tag = "Wb"

        val_str = "--"
        if usage.percent_used is not None:
            rem = max(0.0, 100.0 - usage.percent_used)
            val_str = f"{rem:.0f}%"
        elif usage.running:
            val_str = "RUN"
        elif usage.installed:
            val_str = "OK"

        self.tray_icon.setIcon(self._create_tray_icon(tag, val_str))

    def _update_tooltip(self) -> None:
        lines = ["🤖 AI 工具额度汇总概览:"]
        for usage in self._usages:
            if usage.quota_items:
                q_desc = " | ".join(
                    f"{item.label}: 剩余 {100 - item.percent_used:.0f}%"
                    for item in usage.quota_items
                )
                lines.append(f"• {usage.app_name}: {q_desc}")
            elif usage.percent_used is not None:
                lines.append(f"• {usage.app_name}: 剩余 {100 - usage.percent_used:.0f}%")
            elif usage.today_tokens:
                lines.append(f"• {usage.app_name}: 今日 Token {usage.today_tokens.total}")
            elif usage.running:
                lines.append(f"• {usage.app_name}: 运行中")
            elif usage.installed:
                lines.append(f"• {usage.app_name}: 已安装")
            else:
                lines.append(f"• {usage.app_name}: 未检测到")

        self.tray_icon.setToolTip("\n".join(lines))

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_window_requested.emit()

    def _create_tray_icon(self, tag: str, value: str) -> QIcon:
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制黑底透明圆角背景
        painter.setBrush(QColor("#1e2430"))
        painter.setPen(QColor("#4f8cff"))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 7, 7)

        # 顶部 Tag (例如 Cx / Ag / Wb)
        font_tag = QFont("sans-serif", 8, QFont.Bold)
        painter.setFont(font_tag)
        painter.setPen(QColor("#4f8cff"))
        painter.drawText(0, 2, size, 14, 0x0084, tag)

        # 底部 Value (例如 96% / 22%)
        font_val = QFont("sans-serif", 9, QFont.Bold)
        painter.setFont(font_val)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(0, 14, size, 16, 0x0084, value)

        painter.end()
        return QIcon(pixmap)
