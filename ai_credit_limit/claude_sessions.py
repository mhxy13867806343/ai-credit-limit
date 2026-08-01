from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import TokenUsage


MAX_LINE_BYTES = 512_000


def scan_claude_tokens(projects_dir: Path | None = None, days: int = 90) -> tuple[TokenUsage, TokenUsage, int]:
    root = projects_dir or Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return TokenUsage(), TokenUsage(), 0

    now = datetime.now().astimezone()
    today_key = now.strftime("%Y-%m-%d")
    cutoff = now - timedelta(days=max(days, 1) + 7)
    daily: dict[str, TokenUsage] = {}
    file_count = 0

    for file_path in root.rglob("*.jsonl"):
        try:
            if datetime.fromtimestamp(file_path.stat().st_mtime).astimezone() < cutoff:
                continue
        except OSError:
            continue
        file_count += 1
        for event_time, usage in _iter_usage_events(file_path):
            if event_time < cutoff:
                continue
            key = event_time.strftime("%Y-%m-%d")
            _add_usage(daily.setdefault(key, TokenUsage()), usage)

    today = daily.get(today_key, TokenUsage())
    total = TokenUsage()
    for usage in daily.values():
        _add_usage(total, usage)
    return today, total, file_count


def _iter_usage_events(path: Path):
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                if b'"usage"' not in raw_line or len(raw_line) > MAX_LINE_BYTES:
                    continue
                event = _parse_usage_event(raw_line)
                if event:
                    yield event
    except OSError:
        return


def _parse_usage_event(raw_line: bytes) -> tuple[datetime, TokenUsage] | None:
    try:
        root = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(root, dict):
        return None
    message = root.get("message")
    usage = message.get("usage") if isinstance(message, dict) else None
    event_time = _parse_timestamp(root.get("timestamp"))
    if not event_time or not isinstance(usage, dict):
        return None
    return event_time, TokenUsage(
        input_tokens=_int(usage.get("input_tokens")),
        cached_input_tokens=_int(usage.get("cache_read_input_tokens")) + _int(usage.get("cache_creation_input_tokens")),
        output_tokens=_int(usage.get("output_tokens")),
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _add_usage(target: TokenUsage, addition: TokenUsage) -> None:
    target.input_tokens += addition.input_tokens
    target.cached_input_tokens += addition.cached_input_tokens
    target.output_tokens += addition.output_tokens


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0
