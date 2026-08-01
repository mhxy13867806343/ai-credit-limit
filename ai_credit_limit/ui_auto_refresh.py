from __future__ import annotations

import time
from datetime import datetime
from PyQt5.QtCore import QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


from .theme import AUTO_REFRESH_PANEL_STYLE


class AutoRefreshButton(QWidget):
    """Header button with SVG-style circular progress arc for auto-refresh countdown."""

    refresh_triggered = pyqtSignal()
    settings_changed = pyqtSignal(int, bool, object)  # minutes, enabled, next_refresh_time (float|None)

    PRESETS = [5, 15, 30, 60, 180, 360, 720, 1440]
    PRESET_LABELS = ["5分", "15分", "30分", "1时", "3时", "6时", "12时", "1天"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._interval_minutes: int = 30
        self._enabled: bool = False
        self._next_refresh_time: float | None = None
        self._remaining_seconds: int = 0
        self._total_seconds: int = 0
        self._panel: AutoRefreshPanel | None = None
        self._panel_just_closed: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.setFixedSize(44, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("自动刷新设置")

    # ── public API ──────────────────────────────────────────────────────────

    def load_settings(self, minutes: int, enabled: bool, next_refresh_time: float | None = None) -> None:
        now = time.time()
        self._interval_minutes = max(5, min(1440, minutes))
        self._enabled = enabled
        self._total_seconds = self._interval_minutes * 60

        if enabled:
            if next_refresh_time and next_refresh_time > now:
                self._next_refresh_time = next_refresh_time
                self._remaining_seconds = max(1, int(next_refresh_time - now))
            else:
                self._next_refresh_time = now + self._total_seconds
                self._remaining_seconds = self._total_seconds
                self.settings_changed.emit(self._interval_minutes, self._enabled, self._next_refresh_time)
            self._timer.start()
        else:
            self._next_refresh_time = None
            self._remaining_seconds = self._total_seconds
            self._timer.stop()
        self.update()

    def get_settings(self) -> tuple[int, bool]:
        return self._interval_minutes, self._enabled

    def set_interval(self, minutes: int) -> None:
        now = time.time()
        self._interval_minutes = max(5, min(1440, minutes))
        self._total_seconds = self._interval_minutes * 60
        if self._enabled:
            self._next_refresh_time = now + self._total_seconds
            self._remaining_seconds = self._total_seconds
            self.settings_changed.emit(self._interval_minutes, self._enabled, self._next_refresh_time)
        self.update()
        if self._panel and self._panel.isVisible():
            self._panel.update_display()

    def set_enabled(self, enabled: bool) -> None:
        now = time.time()
        self._enabled = enabled
        if enabled:
            self._next_refresh_time = now + self._total_seconds
            self._remaining_seconds = self._total_seconds
            self._timer.start()
            self.settings_changed.emit(self._interval_minutes, self._enabled, self._next_refresh_time)
        else:
            self._next_refresh_time = None
            self._remaining_seconds = self._total_seconds
            self._timer.stop()
            self.settings_changed.emit(self._interval_minutes, self._enabled, None)
        self.update()
        if self._panel and self._panel.isVisible():
            self._panel.update_display()

    # ── internals ───────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if not self._enabled or not self._next_refresh_time:
            return
        now = time.time()
        remaining = int(self._next_refresh_time - now)
        if remaining <= 0:
            self._next_refresh_time = now + self._total_seconds
            self._remaining_seconds = self._total_seconds
            self.settings_changed.emit(self._interval_minutes, self._enabled, self._next_refresh_time)
            self.refresh_triggered.emit()
        else:
            self._remaining_seconds = remaining
        self.update()
        if self._panel and self._panel.isVisible():
            self._panel.update_display()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and not self._panel_just_closed:
            self._toggle_panel()

    def _toggle_panel(self) -> None:
        if self._panel is None:
            self._panel = AutoRefreshPanel(self)
        if self._panel.isVisible():
            self._panel.hide()
            return
        self._panel.update_display()
        panel_w = 310
        global_pos = self.mapToGlobal(QPoint(self.width() - panel_w, self.height() + 6))
        self._panel.move(global_pos)
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background circle
        painter.setPen(QPen(QColor("#404754"), 1))
        painter.setBrush(QColor("#262c35"))
        painter.drawEllipse(1, 1, w - 2, h - 2)

        # Countdown arc (remaining / total)
        if self._enabled and self._total_seconds > 0:
            frac = self._remaining_seconds / self._total_seconds
            span = int(360 * 16 * frac)
            pen = QPen(QColor("#7c6cff"), 3)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            margin = 4
            arc_rect = QRect(margin, margin, w - margin * 2, h - margin * 2)
            painter.drawArc(arc_rect, 90 * 16, -span)

        # Clock icon
        icon_color = QColor("#a0a8b8") if not self._enabled else QColor("#c0b0ff")
        painter.setPen(icon_color)
        font = painter.font()
        font.setPointSize(15)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "⏱")
        painter.end()


class AutoRefreshPanel(QFrame):
    """Dropdown panel for auto-refresh configuration (preset + custom + toggle)."""

    def __init__(self, button: AutoRefreshButton) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self._button = button
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("autoRefreshPanel")
        self._preset_buttons: list[QPushButton] = []
        self._build_ui()
        self._apply_panel_style()

    def hideEvent(self, event) -> None:  # type: ignore[override]
        """Prevent the button's click from immediately reopening the panel."""
        self._button._panel_just_closed = True
        QTimer.singleShot(180, lambda: setattr(self._button, "_panel_just_closed", False))
        super().hideEvent(event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        # Title
        title_lbl = QLabel("⏱  自动刷新")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #e8eaf6;")
        layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #2d3448; border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Preset grid: 2 rows × 4 columns
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        for idx, (mins, lbl) in enumerate(
            zip(AutoRefreshButton.PRESETS, AutoRefreshButton.PRESET_LABELS)
        ):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setObjectName("arPreset")
            btn.clicked.connect(lambda checked=False, m=mins: self._select_preset(m))
            self._preset_buttons.append(btn)
            grid.addWidget(btn, idx // 4, idx % 4)
        layout.addWidget(grid_widget)

        # Custom input row
        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("自定义分钟 (5–1440)")
        self._custom_input.setFixedHeight(30)
        self._custom_input.returnPressed.connect(self._apply_custom)
        ok_btn = QPushButton("确定")
        ok_btn.setFixedHeight(30)
        ok_btn.clicked.connect(self._apply_custom)
        custom_row.addWidget(self._custom_input, 1)
        custom_row.addWidget(ok_btn)
        layout.addLayout(custom_row)

        # Status / next-refresh time
        self._status_label = QLabel("自动刷新已停止")
        self._status_label.setStyleSheet("color: #9ba1ae; font-size: 12px;")
        layout.addWidget(self._status_label)

        # Start / stop toggle
        self._toggle_btn = QPushButton("启动自动刷新")
        self._toggle_btn.setFixedHeight(34)
        self._toggle_btn.setObjectName("arToggle")
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self.setFixedWidth(310)

    def _apply_panel_style(self) -> None:
        self.setStyleSheet(AUTO_REFRESH_PANEL_STYLE)

    def update_display(self) -> None:
        minutes, enabled = self._button.get_settings()
        next_time_stamp = self._button._next_refresh_time

        for btn, preset_mins in zip(self._preset_buttons, AutoRefreshButton.PRESETS):
            btn.setChecked(preset_mins == minutes)

        if enabled and next_time_stamp:
            remaining = max(0, int(next_time_stamp - time.time()))
            next_time = datetime.fromtimestamp(next_time_stamp)
            m_left = remaining // 60
            s_left = remaining % 60
            self._status_label.setText(
                f"下次刷新：{next_time:%H:%M:%S}（剩余 {m_left}:{s_left:02d}）"
            )
        else:
            self._status_label.setText("自动刷新已停止")

        if enabled:
            self._toggle_btn.setText("停止自动刷新")
            self._toggle_btn.setProperty("active", "stop")
        else:
            self._toggle_btn.setText("启动自动刷新")
            self._toggle_btn.setProperty("active", "")
        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)

    def _select_preset(self, minutes: int) -> None:
        self._button.set_interval(minutes)
        if not self._button._enabled:
            self._button.set_enabled(True)
        self.update_display()

    def _apply_custom(self) -> None:
        text = self._custom_input.text().strip()
        try:
            minutes = int(text)
        except ValueError:
            return
        if 5 <= minutes <= 1440:
            self._custom_input.clear()
            self._button.set_interval(minutes)
            if not self._button._enabled:
                self._button.set_enabled(True)
            self.update_display()

    def _toggle(self) -> None:
        _, enabled = self._button.get_settings()
        self._button.set_enabled(not enabled)
        self.update_display()
