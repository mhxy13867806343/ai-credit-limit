from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from .antigravity_account import AntigravityAccountError, fetch_antigravity_account_usage
from .claude_sessions import scan_claude_tokens
from .codex_account import CodexAccountError, fetch_codex_account_usage, locate_codex_executable
from .codex_sessions import scan_codex_tokens
from .models import AppDefinition, CreditUsage, ParsedUsage, QuotaItem, UsageStatus
from .parsers import merge_parsed_usages, parse_usage_json, parse_usage_text


MAX_SCAN_FILES = 800
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_SQL_ROWS_PER_TABLE = 200
TEXT_SUFFIXES = {".json", ".jsonl", ".log", ".txt", ".plist", ".xml"}
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
SKIPPED_DIRS = {
    "Cache",
    "GPUCache",
    "Code Cache",
    "DawnCache",
    "Crashpad",
    "blob_storage",
    "vendor_imports",
    "skills",
    "extensions",
    "archived_sessions",
    "sessions",
    "rollout_summaries",
    "plugins",
    "attachments",
    "node_modules",
    "dist",
    "build",
}
SKIPPED_FILE_NAMES = {
    "license",
    "license.md",
    "license.txt",
    "readme",
    "readme.md",
    "readme.txt",
    "changelog",
    "changelog.md",
}


def builtin_apps() -> list[AppDefinition]:
    home = Path.home()
    codex_executable = locate_codex_executable()
    codex_cli = [codex_executable] if codex_executable else _which_paths("codex")
    antigravity_cli = _which_paths("antigravity")
    claude_cli = _which_paths("claude")

    return [
        AppDefinition(
            app_id="codex",
            name="Codex",
            executable_paths=[
                Path("/Applications/ChatGPT.app"),
                Path("/Applications/Codex.app"),
                Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
                *codex_cli,
            ],
            search_paths=[
                home / ".codex",
                home / "Library" / "Application Support" / "ChatGPT",
                home / "Library" / "Application Support" / "OpenAI",
                home / "Library" / "Application Support" / "Codex",
                home / "Library" / "Logs" / "ChatGPT",
                home / "Library" / "Logs" / "Codex",
            ],
            builtin=True,
        ),
        AppDefinition(
            app_id="claude_code",
            name="Claude Code",
            executable_paths=[
                Path("/opt/homebrew/bin/claude"),
                Path("/usr/local/bin/claude"),
                Path.home() / ".local" / "bin" / "claude",
                *claude_cli,
            ],
            search_paths=[
                home / ".claude" / "projects",
            ],
            builtin=True,
        ),
        AppDefinition(
            app_id="antigravity",
            name="Antigravity",
            executable_paths=[
                Path("/Applications/Antigravity.app"),
                *antigravity_cli,
            ],
            search_paths=[
                home / ".antigravity",
                home / "Library" / "Application Support" / "Antigravity",
                home / "Library" / "Logs" / "Antigravity",
            ],
            builtin=True,
        ),
        AppDefinition(
            app_id="workbuddy",
            name="WorkBuddy",
            executable_paths=[
                Path("/Applications/WorkBuddy.app"),
                home / "Applications" / "WorkBuddy.app",
                *_which_paths("workbuddy"),
            ],
            search_paths=[
                home / ".workbuddy",
                home / "Library" / "Application Support" / "WorkBuddy",
                home / "Library" / "Application Support" / "com.workbuddy.workbuddy",
            ],
            builtin=True,
        ),
    ]


def scan_apps(
    custom_apps: list[AppDefinition] | None = None,
    enabled_app_ids: set[str] | None = None,
) -> list[CreditUsage]:
    apps = builtin_apps()
    if custom_apps:
        apps.extend(custom_apps)
    if enabled_app_ids is not None:
        apps = [app for app in apps if app.app_id in enabled_app_ids]
    return [scan_app(app) for app in apps]


def scan_app(app: AppDefinition) -> CreditUsage:
    installed_paths = [path for path in app.executable_paths if _exists(path)]
    existing_search_paths = [path for path in app.search_paths if _exists(path)]
    installed = bool(installed_paths if app.executable_paths else existing_search_paths)
    running = _is_app_running(app)

    details = []
    if installed_paths:
        details.append("安装/命令: " + ", ".join(str(path) for path in installed_paths[:4]))
    if existing_search_paths:
        details.append("扫描目录: " + ", ".join(str(path) for path in existing_search_paths[:4]))

    if not installed and not running:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=False,
            running=False,
            status=UsageStatus.NOT_AVAILABLE,
            message="没有发现安装路径或可执行命令",
            removable=not app.builtin,
            details=details,
        )

    if app.app_id == "codex":
        return _scan_codex(app, installed_paths, existing_search_paths, details)
    if app.app_id == "claude_code":
        return _scan_claude_code(app, installed_paths, existing_search_paths, details)
    if app.app_id == "antigravity":
        return _scan_antigravity(app, installed_paths, existing_search_paths, details)
    if app.app_id == "workbuddy":
        return _scan_workbuddy(app, installed_paths, existing_search_paths, details)

    try:
        parsed, source = _scan_usage(existing_search_paths)
    except Exception as exc:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=installed,
            running=running,
            status=UsageStatus.ERROR,
            message=f"扫描失败: {exc}",
            removable=not app.builtin,
            details=details,
        )

    if not parsed:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=installed,
            running=running,
            status=UsageStatus.NOT_AVAILABLE,
            source=", ".join(str(path) for path in existing_search_paths[:3]) or None,
            message="已发现应用，但本地未暴露可读取的额度字段",
            removable=not app.builtin,
            details=details,
        )

    return CreditUsage(
        app_id=app.app_id,
        app_name=app.name,
        installed=installed,
        running=running,
        status=UsageStatus.FOUND,
        percent_used=parsed.percent_used,
        period_label=parsed.period_label,
        reset_label=parsed.reset_label,
        source=source,
        message="已自动读取本地额度进度",
        removable=not app.builtin,
        details=[*details, f"匹配线索: {parsed.source_hint or '结构化字段'}"],
    )


def _scan_codex(
    app: AppDefinition,
    installed_paths: list[Path],
    existing_search_paths: list[Path],
    details: list[str],
) -> CreditUsage:
    today_tokens, total_tokens, scanned_files = scan_codex_tokens()
    running = _is_app_running(app)
    installed = bool(installed_paths if app.executable_paths else existing_search_paths)
    token_detail = (
        f"今日 Tokens: {_format_tokens(today_tokens.total)} "
        f"(输入 {_format_tokens(today_tokens.input_tokens)} / "
        f"缓存 {_format_tokens(today_tokens.cached_input_tokens)} / "
        f"输出 {_format_tokens(today_tokens.output_tokens)})"
    )
    token_total_detail = f"近 90 天本机 Tokens: {_format_tokens(total_tokens.total)}，扫描 sessions 文件 {scanned_files} 个"

    try:
        account_usage = fetch_codex_account_usage()
    except CodexAccountError as exc:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=installed or running,
            running=running,
            status=UsageStatus.NOT_AVAILABLE,
            source="Codex App Server account/rateLimits/read",
            message=f"账号额度读取失败: {exc}",
            today_tokens=today_tokens,
            total_tokens=total_tokens,
            details=[*details, token_detail, token_total_detail],
        )

    primary_window = _choose_primary_window(account_usage.windows)
    plan = account_usage.plan_type.upper() if account_usage.plan_type else "账号"
    quota_items = [
        QuotaItem(
            label=_window_label(window.window_minutes),
            percent_used=window.used_percent,
            reset_label=_format_reset(window.resets_at),
        )
        for window in account_usage.windows
    ]

    return CreditUsage(
        app_id=app.app_id,
        app_name=app.name,
        installed=installed or running,
        running=running,
        status=UsageStatus.FOUND,
        percent_used=primary_window.used_percent,
        period_label=_window_label(primary_window.window_minutes),
        reset_label=_format_reset(primary_window.resets_at),
        source="Codex App Server account/rateLimits/read",
        message=f"{plan} 实时账号额度已同步",
        plan_label=plan,
        today_tokens=today_tokens,
        total_tokens=total_tokens,
        quota_items=quota_items,
        details=[*details, token_detail, token_total_detail],
    )


def _scan_claude_code(
    app: AppDefinition,
    installed_paths: list[Path],
    existing_search_paths: list[Path],
    details: list[str],
) -> CreditUsage:
    today_tokens, total_tokens, scanned_files = scan_claude_tokens()
    running = _is_app_running(app)
    installed = bool(installed_paths if app.executable_paths else existing_search_paths)

    if not installed and not running:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=False,
            running=running,
            status=UsageStatus.NOT_AVAILABLE,
            source="~/.claude/projects" if existing_search_paths else None,
            message="没有发现 Claude Code 可执行命令或安装路径（应用未安装）",
            today_tokens=today_tokens if (today_tokens and today_tokens.total) else None,
            total_tokens=total_tokens if (total_tokens and total_tokens.total) else None,
            details=details,
        )

    if not scanned_files:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=installed,
            running=running,
            status=UsageStatus.NOT_AVAILABLE,
            source="~/.claude/projects",
            message="已安装 Claude Code，但未发现近期本地会话日志",
            details=details,
        )

    return CreditUsage(
        app_id=app.app_id,
        app_name=app.name,
        installed=installed,
        running=running,
        status=UsageStatus.FOUND,
        percent_used=None,
        period_label="本机 Token",
        reset_label=None,
        source="~/.claude/projects",
        message="已读取 Claude Code 本机 Token 活动",
        plan_label="LOCAL",
        today_tokens=today_tokens,
        total_tokens=total_tokens,
        details=[
            *details,
            f"今日 Tokens: {_format_tokens(today_tokens.total)} "
            f"(输入 {_format_tokens(today_tokens.input_tokens)} / "
            f"缓存 {_format_tokens(today_tokens.cached_input_tokens)} / "
            f"输出 {_format_tokens(today_tokens.output_tokens)})",
            f"近 90 天本机 Tokens: {_format_tokens(total_tokens.total)}，扫描 projects 文件 {scanned_files} 个",
        ],
    )


def _scan_antigravity(
    app: AppDefinition,
    installed_paths: list[Path],
    existing_search_paths: list[Path],
    details: list[str],
) -> CreditUsage:
    running = _is_app_running(app)
    account_error = None
    try:
        account_usage = fetch_antigravity_account_usage()
    except AntigravityAccountError as exc:
        account_usage = None
        account_error = str(exc)

    if account_usage and account_usage.windows:
        primary_window = account_usage.windows[0]
        plan = account_usage.plan_label or "GOOGLE AI"
        quota_items = [
            QuotaItem(
                label=f"{window.group} · {window.label}",
                percent_used=window.used_percent,
                reset_label=window.reset_label,
            )
            for window in account_usage.windows
        ]
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=True,
            running=running,
            status=UsageStatus.FOUND,
            percent_used=primary_window.used_percent,
            period_label=f"{primary_window.group} · {primary_window.label}",
            reset_label=primary_window.reset_label,
            source=account_usage.source,
            message=f"{plan} 额度已从 Antigravity Models & Usage 页面同步",
            plan_label=plan,
            quota_items=quota_items,
            details=[*details],
        )

    running_note = "Antigravity 正在运行；" if running else ""
    return CreditUsage(
        app_id=app.app_id,
        app_name=app.name,
        installed=True,
        running=running,
        status=UsageStatus.NOT_AVAILABLE,
        source="Antigravity 应用状态" if running else (", ".join(str(path) for path in existing_search_paths[:3]) or None),
        message=f"{running_note}Models & Usage 是应用内账号页面，当前未能从本地调试页面读取额度字段。",
        plan_label="Google AI",
        details=[
            *details,
            f"读取结果: {account_error or '未发现额度数据'}",
            "已区分应用运行状态和额度读取状态；后续若发现本地 usage 接口/缓存字段，可直接补接入。",
        ],
    )


def _scan_workbuddy(
    app: AppDefinition,
    installed_paths: list[Path],
    existing_search_paths: list[Path],
    details: list[str],
) -> CreditUsage:
    running = _is_app_running(app)
    installed = bool(installed_paths if app.executable_paths else existing_search_paths)

    db_path = Path.home() / ".workbuddy" / "workbuddy.db"
    session_count = 0
    total_used_tokens = 0
    max_context_size = 192000
    latest_used_percent = None

    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]

            cursor.execute("SELECT used, size FROM session_usage ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row and row[1] and row[1] > 0:
                used, size = row[0], row[1]
                latest_used_percent = min(100.0, max(0.0, (used / size) * 100.0))
                max_context_size = size

            cursor.execute("SELECT SUM(used) FROM session_usage")
            sum_row = cursor.fetchone()
            if sum_row and sum_row[0]:
                total_used_tokens = sum_row[0]
            conn.close()
        except Exception as exc:
            details.append(f"数据库读取提示: {exc}")

    if not installed and not running:
        return CreditUsage(
            app_id=app.app_id,
            app_name=app.name,
            installed=False,
            running=False,
            status=UsageStatus.NOT_AVAILABLE,
            message="没有发现 WorkBuddy 安装路径（应用未安装）",
            details=details,
        )

    quota_items = []
    if latest_used_percent is not None:
        quota_items.append(
            QuotaItem(
                label="近期会话上下文",
                percent_used=latest_used_percent,
                reset_label=f"容量 {max_context_size // 1024}K Tokens",
            )
        )

    token_info = (
        TokenUsage(input_tokens=total_used_tokens)
        if total_used_tokens
        else None
    )

    return CreditUsage(
        app_id=app.app_id,
        app_name=app.name,
        installed=installed,
        running=running,
        status=UsageStatus.FOUND if latest_used_percent is not None else UsageStatus.NOT_AVAILABLE,
        percent_used=latest_used_percent,
        period_label="会话上下文",
        source="~/.workbuddy/workbuddy.db",
        message="已自动同步 WorkBuddy AI 开发者工具状态与会话使用记录",
        plan_label="TENCENT AI",
        quota_items=quota_items,
        total_tokens=token_info,
        details=[
            *details,
            f"关联 Sessions 数: {session_count} 个",
            f"已计入 Token 活动: {_format_tokens(total_used_tokens)}",
        ],
    )


def _scan_usage(search_paths: list[Path]) -> tuple[ParsedUsage | None, str | None]:
    best: ParsedUsage | None = None
    best_source: str | None = None
    scanned = 0

    for path in search_paths:
        if path.is_file():
            parsed = _parse_file(path)
            scanned += 1
            if _is_better(parsed, best):
                best = parsed
                best_source = str(path)
            continue

        for file_path in _iter_candidate_files(path):
            parsed = _parse_file(file_path)
            scanned += 1
            if _is_better(parsed, best):
                best = parsed
                best_source = str(file_path)
            if scanned >= MAX_SCAN_FILES:
                return best, best_source

    return best, best_source


def _iter_candidate_files(root: Path):
    if not root.exists():
        return

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_DIRS]
        for filename in filenames:
            if filename.lower() in SKIPPED_FILE_NAMES:
                continue
            path = Path(dirpath) / filename
            if path.suffix.lower() in TEXT_SUFFIXES | SQLITE_SUFFIXES:
                if path.suffix.lower() in {".log", ".txt", ".plist", ".xml"} and not _is_relevant_text_file(path):
                    continue
                yield path


def _parse_file(path: Path) -> ParsedUsage | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0 or size > MAX_TEXT_BYTES:
        return None

    suffix = path.suffix.lower()
    if suffix in SQLITE_SUFFIXES:
        return _parse_sqlite(path)

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    if suffix == ".json":
        return parse_usage_json(text)
    if suffix == ".jsonl":
        return merge_parsed_usages(parse_usage_json(line) for line in text.splitlines() if line.strip())

    return parse_usage_text(text)


def _parse_sqlite(path: Path) -> ParsedUsage | None:
    uri = f"file:{path}?mode=ro"
    candidates: list[ParsedUsage] = []
    try:
        with sqlite3.connect(uri, uri=True, timeout=1) as connection:
            connection.row_factory = sqlite3.Row
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for table_row in tables[:30]:
                table = table_row["name"]
                columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                text_columns = [
                    row["name"]
                    for row in columns
                    if str(row["type"]).upper() in {"TEXT", "VARCHAR", "JSON", ""}
                ]
                if not text_columns:
                    continue
                column_sql = ", ".join(f'"{column}"' for column in text_columns[:8])
                rows = connection.execute(
                    f'SELECT {column_sql} FROM "{table}" LIMIT {MAX_SQL_ROWS_PER_TABLE}'
                ).fetchall()
                for row in rows:
                    text = "\n".join(str(value) for value in row if value is not None)
                    parsed_json = parse_usage_json(text)
                    parsed_text = parse_usage_text(text)
                    candidates.extend(item for item in [parsed_json, parsed_text] if item)
    except (sqlite3.DatabaseError, OSError):
        return None

    return merge_parsed_usages(candidates)


def _is_better(candidate: ParsedUsage | None, current: ParsedUsage | None) -> bool:
    if candidate is None:
        return False
    if current is None:
        return True
    return candidate.confidence > current.confidence


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _which_paths(binary: str) -> list[Path]:
    found = shutil.which(binary)
    return [Path(found)] if found else []


def _is_app_running(app: AppDefinition) -> bool:
    patterns = {
        "codex": [
            "/Applications/ChatGPT.app/Contents/MacOS/ChatGPT",
            "/Applications/ChatGPT.app/Contents/Resources/codex",
            "codex",
        ],
        "claude_code": [
            "claude",
        ],
        "antigravity": [
            "/Applications/Antigravity.app/Contents/MacOS/Antigravity",
            "--app_data_dir antigravity",
            "com.google.antigravity",
        ],
    }.get(app.app_id, [app.name])

    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    if result.returncode != 0:
        return False

    current_pid = str(os.getpid())
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if not parts:
            continue
        pid = parts[0]
        command = parts[1] if len(parts) > 1 else ""
        if pid == current_pid:
            continue
        command_lower = command.lower()
        if any(pattern.lower() in command_lower for pattern in patterns):
            return True
    return False


def _is_relevant_text_file(path: Path) -> bool:
    return any(
        token in path.name.lower()
        for token in ("quota", "usage", "limit", "billing", "subscription", "account", "state", "config")
    )


def _choose_primary_window(windows):
    return max(windows, key=lambda item: item.window_minutes)


def _window_label(minutes: int) -> str:
    if minutes % (24 * 60) == 0:
        days = minutes // (24 * 60)
        return f"{days} 天窗口"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} 小时窗口"
    return f"{minutes} 分钟窗口"


def _format_reset(timestamp: float) -> str:
    reset = datetime.fromtimestamp(timestamp)
    return f"{reset.month}月{reset.day}日 {reset:%H:%M}"


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)
