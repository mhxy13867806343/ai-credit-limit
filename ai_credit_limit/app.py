from __future__ import annotations

import sys
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
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
from .ui_utils import make_app_icon, make_provider_icon, set_dark_palette


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
        self.worker_thread: QThread | None = None
        self.worker: ScanWorker | None = None
        self.scan_running = False
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
        self.tray_manager.quit_requested.connect(QApplication.instance().quit)

        ar_cfg = load_auto_refresh_config()
        self.auto_refresh_btn.load_settings(ar_cfg["minutes"], ar_cfg["enabled"], ar_cfg.get("next_refresh_time"))

        # 启动时优先加载本地上次缓存，0.01秒显示，避免白屏等待
        cached_usages = load_cached_usage()
        if cached_usages:
            self.status_label.setText("已加载本地缓存")
            self._render_cards(cached_usages)

        self.refresh_usage()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event) -> None:
        pref_action, remember = load_close_preference()
        if remember and pref_action in ("minimize", "exit"):
            if pref_action == "minimize":
                event.ignore()
                self.hide()
            else:
                event.accept()
                QApplication.instance().quit()
            return

        box = QMessageBox(self)
        box.setWindowTitle("关闭应用提示")
        box.setText("您点击了关闭窗口按钮，请选择您希望执行的操作：")
        box.setIcon(QMessageBox.Question)

        btn_minimize = box.addButton("最小化到系统托盘", QMessageBox.AcceptRole)
        btn_exit = box.addButton("彻底退出应用", QMessageBox.DestructiveRole)
        btn_cancel = box.addButton("取消", QMessageBox.RejectRole)

        checkbox = QCheckBox("记住我的选择，以后不再提示", box)
        box.setCheckBox(checkbox)

        box.exec_()

        clicked = box.clickedButton()
        remember_choice = checkbox.isChecked()

        if clicked == btn_minimize:
            if remember_choice:
                save_close_preference("minimize", True)
            event.ignore()
            self.hide()
        elif clicked == btn_exit:
            if remember_choice:
                save_close_preference("exit", True)
            event.accept()
            QApplication.instance().quit()
        else:
            event.ignore()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_app_icon(44).pixmap(44, 44))
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title = QLabel("AI Usage Meter")
        title.setObjectName("appTitle")
        subtitle = QLabel("Codex 账号额度、本机 Token 活动，以及可选 AI 工具来源。")
        subtitle.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_usage)

        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)

        self.auto_refresh_btn = AutoRefreshButton()
        self.auto_refresh_btn.refresh_triggered.connect(self.refresh_usage)
        self.auto_refresh_btn.settings_changed.connect(self._on_auto_refresh_settings_changed)

        header.addLayout(title_box, 1)
        header.addWidget(self.status_label)
        header.addWidget(self.refresh_button)
        header.addWidget(self.settings_button)
        header.addWidget(self.auto_refresh_btn)
        layout.addLayout(header)

        self.tabs_host = QFrame()
        self.tabs_host.setObjectName("tabsHost")
        tabs_layout = QVBoxLayout(self.tabs_host)
        tabs_layout.setContentsMargins(14, 12, 14, 12)
        tabs_layout.setSpacing(0)

        self.tab_bar_widget = QWidget()
        self.tab_bar_layout = QHBoxLayout(self.tab_bar_widget)
        self.tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_bar_layout.setSpacing(8)
        tabs_layout.addWidget(self.tab_bar_widget)

        layout.addWidget(self.tabs_host)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

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
        self.status_label.setText("刷新中...")
        self.refresh_button.setEnabled(False)
        self.settings_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = ScanWorker(self.custom_apps, self.enabled_app_ids)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.failed.connect(self._on_scan_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._on_worker_thread_finished)
        self.worker_thread.start()

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
            self.tab_bar_layout.insertWidget(self.tab_bar_layout.count(), tab_button)

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
            self.stack.addWidget(page)
        self.tab_bar_layout.addStretch(1)
        self._select_tab(target_index)
        if hasattr(self, "tray_manager"):
            self.tray_manager.update_usages(usages)

    def _clear_cards(self) -> None:
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater()
        while self.tab_bar_layout.count():
            item = self.tab_bar_layout.takeAt(0)
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
        self.stack.setCurrentIndex(index)
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


from .ui_utils import hide_dock_icon_mac, make_app_icon, make_provider_icon, set_dark_palette


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    hide_dock_icon_mac()
    set_dark_palette(app)
    window = MainWindow()
    window.show()
    return app.exec_()
