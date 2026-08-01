from __future__ import annotations

import sys
from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __app_name__, __version__
from .config import (
    load_auto_refresh_config,
    load_cached_usage,
    load_close_preference,
    load_config,
    save_auto_refresh_config,
    save_cached_usage,
    save_close_preference,
    save_config,
)
from .detectors import builtin_apps, scan_apps
from .models import AppDefinition, CreditUsage
from .theme import MAIN_WINDOW_STYLE
from .ui_auto_refresh import AutoRefreshButton
from .ui_dialogs import SettingsDialog
from .ui_tray import SystemTrayManager
from .ui_usage_card import UsageCard
from .ui_utils import force_mac_activate, make_app_icon, make_provider_icon, set_dark_palette

SINGLE_INSTANCE_SERVER_NAME = "com.aicreditlimit.single_instance_ipc"


class SingleInstanceHelper(QObject):
    wake_up_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.server: QLocalServer | None = None

    def try_wake_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
        if socket.waitForConnected(600):
            socket.write(b"WAKEUP")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return True
        return False

    def listen(self) -> None:
        QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
        self.server = QLocalServer(self)
        self.server.listen(SINGLE_INSTANCE_SERVER_NAME)
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        if self.server:
            client = self.server.nextPendingConnection()
            if client:
                client.readAll()
                self.wake_up_requested.emit()
                client.disconnectFromServer()


class ScanWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, custom_apps: list[AppDefinition], enabled_app_ids: set[str]) -> None:
        super().__init__()
        self._custom_apps = custom_apps
        self._enabled_app_ids = enabled_app_ids

    def run(self) -> None:
        try:
            self.finished.emit(scan_apps(self._custom_apps, self._enabled_app_ids))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.custom_apps, self.enabled_app_ids = load_config()
        self._active_threads: set[QThread] = set()
        self.scan_running = False
        self.is_force_quitting = False
        self.cards: list[UsageCard] = []
        self.current_usages: list[CreditUsage] = []
        self.visible_usages: list[CreditUsage] = []
        self.tab_buttons: list[QPushButton] = []
        self.selected_app_id: str | None = None

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.setWindowIcon(make_app_icon())
        self.setMinimumSize(540, 480)
        self.resize(960, 700)
        self._build_ui()

        # 系统托盘与菜单栏轮播组件
        self.tray_manager = SystemTrayManager(self)
        self.tray_manager.setup()
        self.tray_manager.toggle_window_requested.connect(self.toggle_visibility)
        self.tray_manager.refresh_requested.connect(self.refresh_usage)
        self.tray_manager.settings_requested.connect(self.open_settings)
        self.tray_manager.quit_requested.connect(self.confirm_quit)

        ar_cfg = load_auto_refresh_config()
        self.auto_refresh_btn.load_settings(ar_cfg["minutes"], ar_cfg["enabled"], ar_cfg.get("next_refresh_time"))

        # 启动时优先加载本地上次缓存，0.01秒显示，避免白屏等待
        cached_usages = load_cached_usage()
        if cached_usages:
            self.status_label.setText("已加载本地缓存")
            self._render_cards(cached_usages)

        self.refresh_usage()

    def wake_up(self) -> None:
        """Forcefully raise, restore, and focus the main window when triggered from single-instance launch or tray."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        force_mac_activate()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.wake_up()

    def closeEvent(self, event) -> None:
        # 点击主窗口关闭按钮 (X) 时，仅隐藏主界面，保证右上角菜单栏托盘保持后台常驻监控与轮播
        event.ignore()
        self.hide()
        if hasattr(self, "tray_manager") and self.tray_manager and self.tray_manager.tray_icon:
            self.tray_manager.tray_icon.show()

    def confirm_quit(self) -> None:
        reply = QMessageBox.question(
            self,
            "彻底退出确认",
            "确定要彻底退出应用吗？\n\n彻底退出后，右上角菜单栏将停止轮播与额度监控。\n若仅需隐藏主界面并保持右上角监控，请直接点击“取消”或窗口关闭按钮 (X)。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.is_force_quitting = True
            QApplication.instance().quit()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)

        header_left = QHBoxLayout()
        header_left.setSpacing(12)

        app_icon = QLabel()
        app_icon.setPixmap(make_app_icon().pixmap(42, 42))
        header_left.addWidget(app_icon)

        header_title_layout = QVBoxLayout()
        header_title_layout.setSpacing(2)
        title_label = QLabel("AI Usage Meter")
        title_label.setObjectName("headerTitle")
        sub_label = QLabel("Codex 账号额度、本机 Token 活动，以及可选 AI 工具来源。")
        sub_label.setObjectName("headerSubtitle")
        header_title_layout.addWidget(title_label)
        header_title_layout.addWidget(sub_label)
        header_left.addLayout(header_title_layout)

        header_layout.addLayout(header_left)
        header_layout.addStretch()

        header_right = QHBoxLayout()
        header_right.setSpacing(10)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setObjectName("refreshBtn")
        self.refresh_button.clicked.connect(self.refresh_usage)

        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("settingsBtn")
        self.settings_button.clicked.connect(self.open_settings)

        self.auto_refresh_btn = AutoRefreshButton(self)
        self.auto_refresh_btn.settings_changed.connect(self._on_auto_refresh_settings_changed)
        self.auto_refresh_btn.refresh_triggered.connect(self.refresh_usage)

        header_right.addWidget(self.status_label)
        header_right.addWidget(self.refresh_button)
        header_right.addWidget(self.settings_button)
        header_right.addWidget(self.auto_refresh_btn)
        header_layout.addLayout(header_right)

        layout.addWidget(header)

        tabs_card = QFrame()
        tabs_card.setObjectName("tabsCard")
        self.tabs_layout = QHBoxLayout(tabs_card)
        self.tabs_layout.setContentsMargins(12, 10, 12, 10)
        self.tabs_layout.setSpacing(8)
        layout.addWidget(tabs_card)

        self.cards_area = QScrollArea()
        self.cards_area.setWidgetResizable(True)
        self.cards_area.setFrameShape(QFrame.NoFrame)

        self.stack_widget = QStackedWidget()
        self.cards_area.setWidget(self.stack_widget)
        layout.addWidget(self.cards_area)

        footer = QLabel("Codex 额度来自本机 App Server；Token 活动来自本机会话日志。Antigravity 目前未发现可复用的本地额度接口。")
        footer.setObjectName("footer")
        layout.addWidget(footer)

        self.setCentralWidget(root)
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(MAIN_WINDOW_STYLE)

    def refresh_usage(self) -> None:
        if self.scan_running:
            return
        self.scan_running = True
        self.status_label.setText("")
        self.refresh_button.setText("刷新中...")
        self.refresh_button.setEnabled(False)
        self.settings_button.setEnabled(False)

        worker_thread = QThread(self)
        worker = ScanWorker(self.custom_apps, self.enabled_app_ids)
        worker.moveToThread(worker_thread)
        self._active_threads.add(worker_thread)

        def _cleanup():
            if worker_thread in self._active_threads:
                self._active_threads.remove(worker_thread)
            self._on_worker_thread_finished()

        worker_thread.started.connect(worker.run)
        worker.finished.connect(self._on_scan_finished)
        worker.failed.connect(self._on_scan_failed)
        worker.finished.connect(worker_thread.quit)
        worker.failed.connect(worker_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker_thread.finished.connect(worker_thread.deleteLater)
        worker_thread.finished.connect(_cleanup)
        worker_thread.start()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.custom_apps, self.enabled_app_ids, self)
        if dialog.exec_() != SettingsDialog.Accepted:
            return
        self.custom_apps, self.enabled_app_ids = dialog.result_config()
        save_config(self.custom_apps, self.enabled_app_ids)
        shown_ids = {usage.app_id for usage in self.current_usages}
        active_ids = self._active_app_ids()
        filtered_usages = [
            usage
            for usage in self.current_usages
            if usage.app_id in active_ids and usage.app_id in self.enabled_app_ids
        ]
        needs_scan = bool((self.enabled_app_ids & active_ids) - shown_ids)
        if needs_scan:
            self.refresh_usage()
            return
        self.status_label.setText("设置已保存")
        self._render_cards(filtered_usages)

    def remove_custom_app(self, app_id: str) -> None:
        app = next((item for item in self.custom_apps if item.app_id == app_id), None)
        if not app:
            return
        reply = QMessageBox.question(
            self,
            "移除应用",
            f"确定移除“{app.name}”吗？只会删除本工具里的配置，不会卸载真实应用。",
        )
        if reply != QMessageBox.Yes:
            return
        self.custom_apps = [item for item in self.custom_apps if item.app_id != app_id]
        self.enabled_app_ids.discard(app_id)
        save_config(self.custom_apps, self.enabled_app_ids)
        self.status_label.setText("已移除")
        self._render_cards([usage for usage in self.current_usages if usage.app_id != app_id])

    def _on_scan_finished(self, usages: list[CreditUsage]) -> None:
        self.status_label.setText("已更新")
        self.refresh_button.setText("刷新")
        self.refresh_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        save_cached_usage(usages)
        self._render_cards(usages)

    def _on_scan_failed(self, message: str) -> None:
        self.status_label.setText("刷新受阻")
        self.refresh_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        QMessageBox.warning(self, "扫描提醒", f"部分刷新请求受阻:\n{message}\n\n已保留当前卡片与缓存展示。")

    def _on_worker_thread_finished(self) -> None:
        self.scan_running = False
        self.worker_thread = None
        self.worker = None

    def _on_auto_refresh_settings_changed(self, minutes: int, enabled: bool, next_refresh_time: float | None = None) -> None:
        save_auto_refresh_config(minutes, enabled, next_refresh_time)

    def _render_cards(self, usages: list[CreditUsage], remember: bool = True) -> None:
        self.visible_usages = list(usages)
        if remember:
            self.current_usages = list(usages)
        self._clear_cards()
        target_index = 0
        for index, usage in enumerate(usages):
            if usage.app_id == self.selected_app_id:
                target_index = index

            tab_button = QPushButton(self._tab_title(usage))
            tab_button.setObjectName("providerTab")
            tab_button.setCheckable(True)
            tab_button.setIcon(make_provider_icon(usage.app_name, usage.app_id, 18))
            tab_button.clicked.connect(lambda checked=False, idx=index: self._select_tab(idx))
            self.tab_buttons.append(tab_button)
            self.tabs_layout.insertWidget(self.tabs_layout.count(), tab_button)

            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            host = QWidget()
            host_layout = QVBoxLayout(host)
            host_layout.setContentsMargins(0, 0, 0, 0)
            host_layout.setSpacing(12)
            card = UsageCard(usage)
            card.remove_requested.connect(self.remove_custom_app)
            self.cards.append(card)
            host_layout.addWidget(card)
            host_layout.addStretch(1)
            scroll.setWidget(host)
            page_layout.addWidget(scroll)
            self.stack_widget.addWidget(page)
        self.tabs_layout.addStretch(1)
        self._select_tab(target_index)
        if hasattr(self, "tray_manager"):
            self.tray_manager.update_usages(usages)

    def _clear_cards(self) -> None:
        while self.stack_widget.count():
            page = self.stack_widget.widget(0)
            self.stack_widget.removeWidget(page)
            page.deleteLater()
        while self.tabs_layout.count():
            item = self.tabs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.tab_buttons.clear()
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()

    def _select_tab(self, index: int) -> None:
        if not self.tab_buttons:
            return
        index = max(0, min(index, len(self.tab_buttons) - 1))
        self.stack_widget.setCurrentIndex(index)
        for button_index, button in enumerate(self.tab_buttons):
            button.setChecked(button_index == index)
        if index < len(self.visible_usages):
            self.selected_app_id = self.visible_usages[index].app_id

    def _active_app_ids(self) -> set[str]:
        return {app.app_id for app in [*builtin_apps(), *self.custom_apps]}

    def _tab_title(self, usage: CreditUsage) -> str:
        if usage.app_id == "loading":
            return "扫描中"
        if usage.quota_items:
            parts = []
            for item in usage.quota_items:
                rem = max(0.0, 100.0 - item.percent_used)
                lbl = item.label
                if "5 小时" in lbl or "5小时" in lbl or "5-Hour" in lbl or "5h" in lbl.lower():
                    parts.append(f"5h: {rem:.0f}%")
                elif "周" in lbl or "Weekly" in lbl:
                    parts.append(f"周: {rem:.0f}%")
                elif "窗口" in lbl:
                    parts.append(f"{lbl}: {rem:.0f}%")
            if parts:
                return f"{usage.app_name} · " + " | ".join(parts[:2])

        if usage.percent_used is not None:
            return f"{usage.app_name} · {100 - usage.percent_used:.0f}%"
        if usage.running:
            return f"{usage.app_name} · 运行中"
        if usage.installed:
            return f"{usage.app_name} · 已安装"
        return f"{usage.app_name} · 未发现"


from .ui_utils import make_app_icon, make_provider_icon, set_dark_palette


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    set_dark_palette(app)

    helper = SingleInstanceHelper(app)
    if helper.try_wake_existing_instance():
        return 0

    window = MainWindow()
    helper.wake_up_requested.connect(window.wake_up)
    helper.listen()

    window.wake_up()
    return app.exec_()
