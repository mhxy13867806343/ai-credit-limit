from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from .models import ParsedUsage


PERCENT_KEYS = {
    "percent",
    "percentage",
    "usage_percent",
    "used_percent",
    "percent_used",
    "quota_percent",
    "usagePercent",
    "usedPercent",
    "percentUsed",
}

USED_KEYS = {"used", "usage", "current", "consumed"}
LIMIT_KEYS = {"limit", "total", "quota", "max"}
RESET_KEYS = {
    "reset",
    "reset_at",
    "resetAt",
    "resets_at",
    "resetsAt",
    "next_reset",
    "nextReset",
    "renew_at",
    "renewAt",
}
PERIOD_KEYS = {"period", "window", "interval", "cycle"}

PERCENT_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*%")
CHINESE_RESET_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})(?:[T\s]\d{2}:\d{2}(?::\d{2})?)?\b")
WEEK_RE = re.compile(r"(?:1\s*周|一\s*周|weekly|week)", re.IGNORECASE)
MONTH_RE = re.compile(r"(?:1\s*月|一个月|monthly|month)", re.IGNORECASE)
USAGE_CONTEXT_RE = re.compile(
    r"(quota|usage|limit|额度|用量|使用|进度|剩余|重置|reset)",
    re.IGNORECASE,
)
MIN_TEXT_CONFIDENCE = 50


def parse_usage_text(text: str) -> ParsedUsage | None:
    if not text.strip():
        return None

    best = ParsedUsage(confidence=0)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        percent_match = PERCENT_RE.search(line)
        if not percent_match:
            continue

        value = _safe_percent(percent_match.group(1))
        if value is None:
            continue

        context = "\n".join(lines[max(0, index - 2) : min(len(lines), index + 3)])
        confidence = 10
        if USAGE_CONTEXT_RE.search(context):
            confidence += 50
        if WEEK_RE.search(context) or MONTH_RE.search(context):
            confidence += 10
        if _reset_from_text(context):
            confidence += 15

        candidate = ParsedUsage(
            percent_used=value,
            period_label=_period_from_text(context),
            reset_label=_reset_from_text(context),
            confidence=confidence,
            source_hint=line,
        )
        if candidate.confidence > best.confidence:
            best = candidate

    if best.percent_used is not None and best.confidence >= MIN_TEXT_CONFIDENCE:
        if not best.period_label:
            best.period_label = _period_from_text(text)
        if not best.reset_label:
            best.reset_label = _reset_from_text(text)
        return best

    return None


def parse_usage_json(text: str) -> ParsedUsage | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parse_usage_object(payload)


def parse_usage_object(payload: Any) -> ParsedUsage | None:
    candidates = list(_walk_json(payload))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)


def merge_parsed_usages(usages: Iterable[ParsedUsage]) -> ParsedUsage | None:
    valid = [usage for usage in usages if usage and usage.percent_used is not None]
    if not valid:
        return None
    return max(valid, key=lambda item: item.confidence)


def _walk_json(value: Any, path: str = "$") -> Iterable[ParsedUsage]:
    if isinstance(value, dict):
        direct = _parse_json_dict(value, path)
        if direct:
            yield direct
        for key, child in value.items():
            yield from _walk_json(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]")
    elif isinstance(value, str) and _is_usage_path(path):
        parsed = parse_usage_text(value)
        if parsed:
            parsed.confidence = max(10, parsed.confidence - 10)
            parsed.source_hint = path
            yield parsed


def _parse_json_dict(raw: dict[str, Any], path: str) -> ParsedUsage | None:
    lowered = {str(key): value for key, value in raw.items()}
    percent = None
    confidence = 0

    for key, value in lowered.items():
        if key in PERCENT_KEYS or key.lower() in {item.lower() for item in PERCENT_KEYS}:
            percent = _number_to_percent(value)
            if percent is not None:
                confidence += 70
                break

    if percent is None:
        used = _first_number(lowered, USED_KEYS)
        limit = _first_number(lowered, LIMIT_KEYS)
        if used is not None and limit and limit > 0:
            percent = max(0.0, min(100.0, (used / limit) * 100.0))
            confidence += 55

    if percent is None:
        return None

    period = _first_string(lowered, PERIOD_KEYS)
    reset = _first_string(lowered, RESET_KEYS)
    if period:
        confidence += 10
    if reset:
        confidence += 10

    return ParsedUsage(
        percent_used=percent,
        period_label=_friendly_period(period) if period else None,
        reset_label=_friendly_reset(reset) if reset else None,
        confidence=confidence,
        source_hint=path,
    )


def _safe_percent(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    if 0 <= value <= 100:
        return value
    return None


def _number_to_percent(value: Any) -> float | None:
    if isinstance(value, str):
        match = PERCENT_RE.search(value)
        if match:
            return _safe_percent(match.group(1))
        try:
            value = float(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if 0 <= number <= 1:
            return number * 100.0
        if 0 <= number <= 100:
            return number
    return None


def _first_number(raw: dict[str, Any], keys: set[str]) -> float | None:
    for key, value in raw.items():
        if key in keys or key.lower() in keys:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    continue
    return None


def _first_string(raw: dict[str, Any], keys: set[str]) -> str | None:
    for key, value in raw.items():
        if key in keys or key.lower() in {item.lower() for item in keys}:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _period_from_text(text: str) -> str | None:
    if WEEK_RE.search(text):
        return "1 周"
    if MONTH_RE.search(text):
        return "1 月"
    return None


def _reset_from_text(text: str) -> str | None:
    chinese_match = CHINESE_RESET_RE.search(text)
    if chinese_match:
        return f"{int(chinese_match.group(1))}月{int(chinese_match.group(2))}日"

    iso_match = ISO_DATE_RE.search(text)
    if iso_match:
        return iso_match.group(1)

    return None


def _friendly_period(value: str) -> str:
    lowered = value.lower()
    if "week" in lowered or "周" in value:
        return "1 周"
    if "month" in lowered or "月" in value:
        return "1 月"
    return value


def _friendly_reset(value: str) -> str:
    return _reset_from_text(value) or value


def _is_usage_path(path: str) -> bool:
    return bool(re.search(r"(quota|usage|limit|reset|billing|subscription|额度|用量|重置)", path, re.IGNORECASE))
