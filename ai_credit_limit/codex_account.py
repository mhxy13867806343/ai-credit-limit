from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .models import CodexAccountUsage, RateLimitWindow


REQUEST_ID = 2601


class CodexAccountError(RuntimeError):
    pass


def fetch_codex_account_usage(timeout: float = 20.0) -> CodexAccountUsage:
    executable = locate_codex_executable()
    if not executable:
        raise CodexAccountError("未找到支持 app-server 的 Codex CLI")

    env = os.environ.copy()
    env["RUST_LOG"] = "error"
    env["PATH"] = f"{executable.parent}{os.pathsep}{env.get('PATH', '')}"

    process = subprocess.Popen(
        [str(executable), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )

    lines: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(target=_read_stdout, args=(process, lines), daemon=True)
    reader.start()

    try:
        _send_requests(process)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            wait_time = max(0.05, min(0.5, deadline - time.monotonic()))
            try:
                line = lines.get(timeout=wait_time)
            except queue.Empty:
                if process.poll() is not None:
                    raise CodexAccountError(f"Codex app-server 提前退出: {process.returncode}")
                continue

            if line is None:
                raise CodexAccountError("Codex app-server 没有返回账号额度")
            parsed = _parse_json_line(line)
            if parsed.get("id") == REQUEST_ID:
                return parse_rate_limits_response(parsed)

        raise CodexAccountError("账号额度同步超时")
    finally:
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def locate_codex_executable() -> Path | None:
    home = Path.home()
    candidates = [
        os.environ.get("CODEX_CLI_PATH"),
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        str(home / "Applications" / "ChatGPT.app" / "Contents" / "Resources" / "codex"),
        "/Applications/Codex.app/Contents/Resources/codex",
        str(home / "Applications" / "Codex.app" / "Contents" / "Resources" / "codex"),
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        str(home / ".local" / "bin" / "codex"),
        str(home / ".volta" / "bin" / "codex"),
        str(home / ".bun" / "bin" / "codex"),
        shutil.which("codex"),
    ]
    candidates.extend(_version_manager_candidates(home))

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def parse_rate_limits_response(message: dict[str, Any]) -> CodexAccountUsage:
    if error := message.get("error"):
        if isinstance(error, dict):
            raise CodexAccountError(str(error.get("message") or error))
        raise CodexAccountError(str(error))

    result = message.get("result")
    if not isinstance(result, dict):
        raise CodexAccountError("Codex 返回了无法识别的账号额度数据")

    keyed_limits = result.get("rateLimitsByLimitId")
    raw_snapshot = None
    if isinstance(keyed_limits, dict):
        raw_snapshot = keyed_limits.get("codex")
    if not isinstance(raw_snapshot, dict):
        raw_snapshot = result.get("rateLimits")
    if not isinstance(raw_snapshot, dict):
        raise CodexAccountError("没有找到 codex rateLimits")

    windows = [
        window
        for window in [
            _parse_window(raw_snapshot.get("primary"), "primary"),
            _parse_window(raw_snapshot.get("secondary"), "secondary"),
        ]
        if window is not None
    ]
    if not windows:
        raise CodexAccountError("账号额度窗口为空")

    return CodexAccountUsage(
        windows=sorted(windows, key=lambda item: item.window_minutes),
        plan_type=_string_or_none(raw_snapshot.get("planType") or raw_snapshot.get("plan_type")),
    )


def _send_requests(process: subprocess.Popen[str]) -> None:
    if not process.stdin:
        raise CodexAccountError("无法写入 Codex app-server")

    messages = [
        {
            "method": "initialize",
            "id": 0,
            "params": {
                "clientInfo": {
                    "name": "ai_credit_limit",
                    "title": "AI Credit Limit",
                    "version": "0.1.0",
                }
            },
        },
        {"method": "initialized", "params": {}},
        {"method": "account/rateLimits/read", "id": REQUEST_ID, "params": None},
    ]
    for message in messages:
        process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _read_stdout(process: subprocess.Popen[str], lines: queue.Queue[str | None]) -> None:
    if not process.stdout:
        lines.put(None)
        return
    for line in process.stdout:
        if line.strip():
            lines.put(line)
    lines.put(None)


def _parse_json_line(line: str) -> dict[str, Any]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_window(value: Any, role: str) -> RateLimitWindow | None:
    if not isinstance(value, dict):
        return None
    used_percent = _number(value.get("usedPercent") or value.get("used_percent"))
    window_minutes = _number(value.get("windowDurationMins") or value.get("window_minutes"))
    resets_at = _number(value.get("resetsAt") or value.get("resets_at"))
    if used_percent is None or window_minutes is None or resets_at is None:
        return None
    if window_minutes <= 0 or resets_at <= 0:
        return None
    return RateLimitWindow(
        role=role,
        used_percent=max(0.0, min(100.0, used_percent)),
        window_minutes=int(window_minutes),
        resets_at=resets_at,
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _version_manager_candidates(home: Path) -> list[str]:
    candidates: list[str] = []
    nvm_root = home / ".nvm" / "versions" / "node"
    if nvm_root.exists():
        for version in sorted(nvm_root.iterdir(), reverse=True):
            candidates.append(str(version / "bin" / "codex"))

    fnm_root = home / ".local" / "share" / "fnm" / "node-versions"
    if fnm_root.exists():
        for version in sorted(fnm_root.iterdir(), reverse=True):
            candidates.append(str(version / "installation" / "bin" / "codex"))

    return candidates
