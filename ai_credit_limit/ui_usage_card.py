from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .models import CreditUsage, QuotaItem, UsageStatus
from .theme import (
    METRIC_PILL_STYLE,
    PLAN_BADGE_STYLE,
    QUOTA_ITEM_FRAME_STYLE,
    progress_bar_style_for_percent,
)
from .ui_utils import format_tokens, make_provider_icon


class UsageCard(QFrame):
    remove_requested = pyqtSignal(str)

    def __init__(self, usage: CreditUsage) -> None:
        super().__init__()
        self.usage = usage
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_provider_icon(self.usage.app_name, self.usage.app_id, 44).pixmap(44, 44))
        top.addWidget(logo)

        name_box = QVBoxLayout()
        name = QLabel(self.usage.app_name)
        name.setObjectName("appName")
        meta = QLabel(self._meta_text())
        meta.setObjectName("muted")
        meta.setWordWrap(True)
        name_box.addWidget(name)
        name_box.addWidget(meta)

        top.addLayout(name_box, 1)
        if self.usage.plan_label:
            plan = QLabel(self.usage.plan_label)
            plan.setObjectName("muted")
            plan.setAlignment(Qt.AlignCenter)
            plan.setStyleSheet(PLAN_BADGE_STYLE)
            top.addWidget(plan)
        if self.usage.removable:
            remove_button = QPushButton("移除")
            remove_button.clicked.connect(lambda: self.remove_requested.emit(self.usage.app_id))
            top.addWidget(remove_button)
        metric_box = QVBoxLayout()
        metric = QLabel(self._metric_text())
        metric.setObjectName("metric")
        metric.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        metric_caption = QLabel(self._metric_caption())
        metric_caption.setObjectName("metricCaption")
        metric_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        metric_box.addWidget(metric)
        metric_box.addWidget(metric_caption)
        top.addLayout(metric_box)
        layout.addLayout(top)

        if self.usage.quota_items:
            quota_box = QVBoxLayout()
            quota_box.setSpacing(8)
            for item in self.usage.quota_items:
                quota_box.addWidget(self._build_quota_item_widget(item))
            layout.addLayout(quota_box)
        else:
            progress = QProgressBar()
            progress.setRange(0, 100)
            if self.usage.percent_used is None:
                progress.setValue(0)
                progress.setStyleSheet("QProgressBar::chunk { background: #59606d; }")
            else:
                progress.setValue(round(self.usage.percent_used))
                progress.setStyleSheet(self._progress_style())
            layout.addWidget(progress)

        if self.usage.today_tokens or self.usage.total_tokens:
            metrics = QHBoxLayout()
            metrics.setSpacing(10)
            if self.usage.today_tokens:
                metrics.addWidget(self._metric_pill("今日 Tokens", format_tokens(self.usage.today_tokens.total)))
                metrics.addWidget(self._metric_pill("输入", format_tokens(self.usage.today_tokens.input_tokens)))
                metrics.addWidget(self._metric_pill("缓存", format_tokens(self.usage.today_tokens.cached_input_tokens)))
                metrics.addWidget(self._metric_pill("输出", format_tokens(self.usage.today_tokens.output_tokens)))
            if self.usage.total_tokens:
                metrics.addWidget(self._metric_pill("近 90 天", format_tokens(self.usage.total_tokens.total)))
            layout.addLayout(metrics)

        message = QLabel(self.usage.message or "")
        message.setObjectName("message")
        message.setWordWrap(True)
        layout.addWidget(message)

        if self.usage.details or self.usage.source:
            details = QLabel(self._details_text())
            details.setObjectName("muted")
            details.setWordWrap(True)
            layout.addWidget(details)

    def _build_quota_item_widget(self, item: QuotaItem) -> QWidget:
        container = QFrame()
        container.setObjectName("quotaItemFrame")
        container.setStyleSheet(QUOTA_ITEM_FRAME_STYLE)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        lbl_title = QLabel(item.label)
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        header_layout.addWidget(lbl_title)

        header_layout.addStretch(1)

        remaining = max(0.0, 100.0 - item.percent_used)
        reset_str = f" · 重置 {item.reset_label}" if item.reset_label else ""
        lbl_info = QLabel(f"已用 {item.percent_used:.0f}% (剩余 {remaining:.0f}%){reset_str}")
        lbl_info.setStyleSheet("font-size: 12px; color: #a4abb8;")
        header_layout.addWidget(lbl_info)

        layout.addLayout(header_layout)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(round(item.percent_used))
        progress.setFixedHeight(8)
        progress.setStyleSheet(progress_bar_style_for_percent(item.percent_used))
        layout.addWidget(progress)

        return container

    def _metric_text(self) -> str:
        if self.usage.percent_used is None:
            if self.usage.today_tokens and self.usage.today_tokens.total:
                return format_tokens(self.usage.today_tokens.total)
            if self.usage.running:
                return "运行中"
            if self.usage.installed:
                return "已安装"
            return "未发现"
        remaining = max(0.0, 100.0 - self.usage.percent_used)
        return f"{remaining:.0f}%"

    def _metric_caption(self) -> str:
        if self.usage.percent_used is None:
            if self.usage.today_tokens:
                return "本机数据"
            if self.usage.running:
                return "额度未接入"
            if self.usage.installed:
                return "暂无外部额度"
            return "未检测到"
        return f"剩余 · 已用 {self.usage.percent_used:.0f}%"

    def _meta_text(self) -> str:
        state = "运行中" if self.usage.running else ("已安装" if self.usage.installed else "未发现")
        if self.usage.percent_used is not None or self.usage.today_tokens:
            period = self.usage.period_label or "本机 Token"
        elif self.usage.status == UsageStatus.ERROR:
            period = "读取异常"
        else:
            period = "额度未接入"
        reset = self.usage.reset_label or "无重置时间"
        return f"{state} · {period} · {reset}"

    def _details_text(self) -> str:
        parts = []
        if self.usage.source:
            parts.append(f"来源: {self.usage.source}")
        for detail in self.usage.details:
            if detail.startswith(("安装/命令:", "扫描目录:")) and not self.usage.removable:
                continue
            parts.append(detail)
        return "\n".join(parts[:6])

    def _progress_style(self) -> str:
        percent = self.usage.percent_used or 0
        return progress_bar_style_for_percent(percent)

    def _metric_pill(self, label: str, value: str) -> QWidget:
        container = QFrame()
        container.setObjectName("pill")
        container.setStyleSheet(METRIC_PILL_STYLE)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 11px; color: #9ba1ae;")
        val = QLabel(value)
        val.setStyleSheet("font-size: 13px; font-weight: bold; color: #f3f4f6;")

        layout.addWidget(lbl)
        layout.addWidget(val)
        return container
