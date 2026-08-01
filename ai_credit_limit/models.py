from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class UsageStatus(str, Enum):
    FOUND = "found"
    NOT_AVAILABLE = "not_available"
    ERROR = "error"


@dataclass(slots=True)
class QuotaItem:
    label: str
    percent_used: float
    reset_label: str | None = None


@dataclass(slots=True)
class CreditUsage:
    app_id: str
    app_name: str
    installed: bool
    status: UsageStatus
    running: bool = False
    percent_used: float | None = None
    period_label: str | None = None
    reset_label: str | None = None
    source: str | None = None
    message: str | None = None
    plan_label: str | None = None
    today_tokens: TokenUsage | None = None
    total_tokens: TokenUsage | None = None
    removable: bool = False
    quota_items: list[QuotaItem] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RateLimitWindow:
    role: str
    used_percent: float
    window_minutes: int
    resets_at: float


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens


@dataclass(slots=True)
class CodexAccountUsage:
    windows: list[RateLimitWindow]
    plan_type: str | None = None
    source: str = "账号实时"


@dataclass(slots=True)
class AppDefinition:
    app_id: str
    name: str
    executable_paths: list[Path] = field(default_factory=list)
    search_paths: list[Path] = field(default_factory=list)
    builtin: bool = False


@dataclass(slots=True)
class ParsedUsage:
    percent_used: float | None = None
    period_label: str | None = None
    reset_label: str | None = None
    confidence: int = 0
    source_hint: str | None = None
