from __future__ import annotations

from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import make_custom_app
from .detectors import builtin_apps
from .models import AppDefinition


class SettingsDialog(QDialog):
    def __init__(
        self,
        custom_apps: list[AppDefinition],
        enabled_app_ids: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.custom_apps = list(custom_apps)
        self.enabled_app_ids = set(enabled_app_ids)
        self.provider_checks: dict[str, QCheckBox] = {}
        self.setWindowTitle("AI 工具展示设置")
        self.resize(440, 360)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        intro = QLabel("自动检测到的 AI 开发工具来源：")
        intro.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(intro)

        sub_tip = QLabel("勾选需要在主界面展示卡片与 Tab 标签的 AI 工具：")
        sub_tip.setStyleSheet("font-size: 12px; color: #94a3b8;")
        layout.addWidget(sub_tip)

        all_apps = [*builtin_apps(), *self.custom_apps]
        for app in all_apps:
            checkbox = QCheckBox(f"{app.name}")
            checkbox.setChecked(app.app_id in self.enabled_app_ids)
            self.provider_checks[app.app_id] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("保存")
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def result_config(self) -> tuple[list[AppDefinition], set[str]]:
        enabled = {
            app_id
            for app_id, checkbox in self.provider_checks.items()
            if checkbox.isChecked()
        }
        return self.custom_apps, enabled

    def _refresh_custom_list(self) -> None:
        self.custom_list.clear()
        for app in self.custom_apps:
            paths = ", ".join(str(path) for path in [*app.executable_paths, *app.search_paths][:2])
            item = QListWidgetItem(f"{app.name}    {paths}")
            item.setData(Qt.UserRole, app.app_id)
            self.custom_list.addItem(item)

    def _add_custom_app(self) -> None:
        existing_names = {app.name.strip().lower() for app in [*builtin_apps(), *self.custom_apps]}
        dialog = AddAppDialog(existing_names, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        app = dialog.to_app_definition()
        if not app:
            return
        self.custom_apps.append(app)
        self.enabled_app_ids.add(app.app_id)
        checkbox = QCheckBox(f"{app.name}  ·  自定义")
        checkbox.setChecked(True)
        self.provider_checks[app.app_id] = checkbox
        self.layout().insertWidget(max(1, self.layout().count() - 6), checkbox)
        self._refresh_custom_list()

    def _remove_selected_custom_app(self) -> None:
        item = self.custom_list.currentItem()
        if item is None:
            return
        app_id = item.data(Qt.UserRole)
        app = next((candidate for candidate in self.custom_apps if candidate.app_id == app_id), None)
        if not app:
            return
        reply = QMessageBox.question(
            self,
            "移除应用",
            f"确定移除“{app.name}”吗？只会删除本工具里的配置。",
        )
        if reply != QMessageBox.Yes:
            return
        self.custom_apps = [candidate for candidate in self.custom_apps if candidate.app_id != app_id]
        self.enabled_app_ids.discard(app_id)
        checkbox = self.provider_checks.pop(app_id, None)
        if checkbox:
            checkbox.setParent(None)
            checkbox.deleteLater()
        self._refresh_custom_list()


class AddAppDialog(QDialog):
    def __init__(self, existing_names: set[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加自定义应用")
        self.resize(560, 360)
        self._existing_names = existing_names or set()
        self._user_edited_name = False
        self._last_inferred_name = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("选择路径/目录后自动获取名称，也可手动修改")
        self.name_input.textEdited.connect(self._on_name_edited)
        form.addRow("应用名称", self.name_input)

        executable_row = QHBoxLayout()
        self.executable_input = QLineEdit()
        self.executable_input.setPlaceholderText("/Applications/Example.app 或命令路径，可留空")
        self.executable_input.textChanged.connect(self._auto_update_name)
        browse_executable = QPushButton("选择")
        browse_executable.clicked.connect(self._choose_executable)
        executable_row.addWidget(self.executable_input, 1)
        executable_row.addWidget(browse_executable)
        form.addRow("应用路径", executable_row)

        self.search_paths_input = QTextEdit()
        self.search_paths_input.setPlaceholderText(
            "每行一个目录或文件，例如:\n~/Library/Application Support/Example\n~/.example"
        )
        self.search_paths_input.textChanged.connect(self._auto_update_name)
        form.addRow("数据目录", self.search_paths_input)

        browse_dir = QPushButton("添加扫描目录")
        browse_dir.clicked.connect(self._choose_search_path)
        form.addRow("", browse_dir)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("添加")
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def accept(self) -> None:
        name = self.name_input.text().strip() or infer_app_name_from_paths(
            self.executable_input.text(), self.search_paths_input.toPlainText()
        )
        executable_paths = _split_lines(self.executable_input.text())
        search_paths = _split_lines(self.search_paths_input.toPlainText())

        if not name or (not executable_paths and not search_paths):
            QMessageBox.warning(self, "无法添加", "请填写应用名称，并至少提供一个可扫描目录或应用路径。")
            return

        if name.strip().lower() in self._existing_names:
            QMessageBox.warning(
                self,
                "无法添加",
                f"已存在名称为“{name}”的应用（不能与内置应用或已有自定义应用同名），请输入不同的名称！",
            )
            return

        super().accept()

    def _on_name_edited(self, text: str) -> None:
        if text.strip() != self._last_inferred_name:
            self._user_edited_name = bool(text.strip())

    def _auto_update_name(self) -> None:
        if self._user_edited_name and self.name_input.text().strip():
            return
        inferred = infer_app_name_from_paths(
            self.executable_input.text(), self.search_paths_input.toPlainText()
        )
        if inferred:
            if inferred.lower() in self._existing_names:
                inferred = f"{inferred} (自定义)"
            self._last_inferred_name = inferred
            self.name_input.setText(inferred)

    def to_app_definition(self) -> AppDefinition | None:
        executable_paths = _split_lines(self.executable_input.text())
        search_paths = _split_lines(self.search_paths_input.toPlainText())
        name = self.name_input.text().strip() or infer_app_name_from_paths(
            self.executable_input.text(), self.search_paths_input.toPlainText()
        )
        if not name or (not executable_paths and not search_paths):
            return None
        return make_custom_app(name, executable_paths, search_paths)

    def _choose_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择应用或可执行文件", "/Applications")
        if path:
            self.executable_input.setText(path)
            self._auto_update_name()

    def _choose_search_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择扫描目录", str(Path.home()))
        if not path:
            return
        existing = self.search_paths_input.toPlainText().strip()
        self.search_paths_input.setPlainText(f"{existing}\n{path}".strip())
        self._auto_update_name()


def infer_app_name_from_paths(executable_text: str, search_text: str) -> str:
    exec_paths = _split_lines(executable_text)
    if exec_paths:
        name = _infer_single_name(exec_paths[0])
        if name:
            return name

    search_paths = _split_lines(search_text)
    if search_paths:
        name = _infer_single_name(search_paths[0])
        if name:
            return name

    return ""


def _infer_single_name(path_str: str) -> str:
    if not path_str:
        return ""
    path = Path(path_str.strip())
    name = path.name
    if name.endswith(".app"):
        return name[:-4]
    if name.startswith("."):
        name = name[1:]
    if name.lower() in ("bin", "contents", "macos", "resources", "application support"):
        parent_name = path.parent.name
        if parent_name.endswith(".app"):
            return parent_name[:-4]
        if parent_name.startswith("."):
            parent_name = parent_name[1:]
        name = parent_name

    clean_name = name.replace("_", " ").replace("-", " ").strip()
    if clean_name:
        return clean_name.title()
    return ""


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]
