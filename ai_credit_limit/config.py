from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from .models import AppDefinition, CreditUsage, QuotaItem, TokenUsage, UsageStatus


APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "AI Credit Limit"
CONFIG_FILE = APP_SUPPORT_DIR / "config.json"
CACHE_FILE = APP_SUPPORT_DIR / "cache.json"
DEFAULT_ENABLED_APP_IDS = {"codex", "antigravity", "claude_code", "workbuddy"}


def load_config() -> tuple[list[AppDefinition], set[str]]:
    payload = _load_payload()
    apps = _apps_from_payload(payload)
    enabled = payload.get("enabled_app_ids")
    if isinstance(enabled, list):
        enabled_ids = {str(item) for item in enabled}
    else:
        enabled_ids = set(DEFAULT_ENABLED_APP_IDS)
        enabled_ids.update(app.app_id for app in apps)
    return apps, enabled_ids


def load_custom_apps() -> list[AppDefinition]:
    return load_config()[0]


def load_enabled_app_ids() -> set[str]:
    return load_config()[1]


def save_config(apps: list[AppDefinition], enabled_app_ids: set[str]) -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _load_payload()  # preserve auto_refresh and any future extra fields
    payload.update({
        "enabled_app_ids": sorted(enabled_app_ids),
        "apps": [
            {
                **asdict(app),
                "executable_paths": [str(path) for path in app.executable_paths],
                "search_paths": [str(path) for path in app.search_paths],
            }
            for app in apps
            if not app.builtin
        ],
    })
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_custom_apps(apps: list[AppDefinition]) -> None:
    _apps, enabled_app_ids = load_config()
    save_config(apps, enabled_app_ids)


def load_auto_refresh_config() -> dict:
    """Return auto-refresh settings: {'minutes': int, 'enabled': bool, 'next_refresh_time': float | None}."""
    payload = _load_payload()
    ar = payload.get("auto_refresh")
    if not isinstance(ar, dict):
        return {"minutes": 30, "enabled": False, "next_refresh_time": None}
    minutes = ar.get("minutes", 30)
    enabled = ar.get("enabled", False)
    next_refresh_time = ar.get("next_refresh_time")
    if not isinstance(minutes, int) or not (5 <= minutes <= 1440):
        minutes = 30
    if not isinstance(next_refresh_time, (int, float)):
        next_refresh_time = None
    return {
        "minutes": minutes,
        "enabled": bool(enabled),
        "next_refresh_time": float(next_refresh_time) if next_refresh_time else None,
    }


def save_auto_refresh_config(minutes: int, enabled: bool, next_refresh_time: float | None = None) -> None:
    """Persist auto-refresh settings including next_refresh_time target timestamp."""
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _load_payload()
    payload["auto_refresh"] = {
        "minutes": minutes,
        "enabled": enabled,
        "next_refresh_time": next_refresh_time,
    }
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_close_preference() -> tuple[str | None, bool]:
    """Return close window preference: (action: 'minimize' | 'exit' | None, remember: bool)."""
    payload = _load_payload()
    pref = payload.get("close_preference")
    if not isinstance(pref, dict):
        return None, False
    action = pref.get("action")
    remember = bool(pref.get("remember", False))
    if action not in ("minimize", "exit"):
        action = None
    return action, remember


def save_close_preference(action: str, remember: bool) -> None:
    """Save user choice for closing window."""
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _load_payload()
    payload["close_preference"] = {
        "action": action,
        "remember": remember,
    }
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_custom_app(name: str, executable_paths: list[str], search_paths: list[str]) -> AppDefinition:
    return AppDefinition(
        app_id=f"custom-{uuid.uuid4().hex}",
        name=name.strip(),
        executable_paths=[Path(p).expanduser() for p in executable_paths if p.strip()],
        search_paths=[Path(p).expanduser() for p in search_paths if p.strip()],
        builtin=False,
    )


def _load_payload() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _apps_from_payload(payload: dict) -> list[AppDefinition]:
    apps: list[AppDefinition] = []
    for raw_app in payload.get("apps", []):
        if not isinstance(raw_app, dict):
            continue
        name = str(raw_app.get("name", "")).strip()
        if not name:
            continue

        app_id = str(raw_app.get("app_id") or f"custom-{uuid.uuid4().hex}")
        executable_paths = [Path(p).expanduser() for p in raw_app.get("executable_paths", []) if p]
        search_paths = [Path(p).expanduser() for p in raw_app.get("search_paths", []) if p]
        apps.append(
            AppDefinition(
                app_id=app_id,
                name=name,
                executable_paths=executable_paths,
                search_paths=search_paths,
                builtin=False,
            )
        )
    return apps


def save_cached_usage(usages: list[CreditUsage]) -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for u in usages:
        item = {
            "app_id": u.app_id,
            "app_name": u.app_name,
            "installed": u.installed,
            "status": u.status.value if u.status else "not_available",
            "running": u.running,
            "percent_used": u.percent_used,
            "period_label": u.period_label,
            "reset_label": u.reset_label,
            "source": u.source,
            "message": u.message,
            "plan_label": u.plan_label,
            "removable": u.removable,
            "details": u.details,
            "quota_items": [
                {
                    "label": q.label,
                    "percent_used": q.percent_used,
                    "reset_label": q.reset_label,
                }
                for q in u.quota_items
            ],
        }
        if u.today_tokens:
            item["today_tokens"] = {
                "input_tokens": u.today_tokens.input_tokens,
                "cached_input_tokens": u.today_tokens.cached_input_tokens,
                "output_tokens": u.today_tokens.output_tokens,
            }
        if u.total_tokens:
            item["total_tokens"] = {
                "input_tokens": u.total_tokens.input_tokens,
                "cached_input_tokens": u.total_tokens.cached_input_tokens,
                "output_tokens": u.total_tokens.output_tokens,
            }
        items.append(item)
    try:
        CACHE_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_cached_usage() -> list[CreditUsage]:
    if not CACHE_FILE.exists():
        return []
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        usages = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            today = item.get("today_tokens")
            today_tokens = (
                TokenUsage(
                    input_tokens=today.get("input_tokens", 0),
                    cached_input_tokens=today.get("cached_input_tokens", 0),
                    output_tokens=today.get("output_tokens", 0),
                )
                if isinstance(today, dict)
                else None
            )
            total = item.get("total_tokens")
            total_tokens = (
                TokenUsage(
                    input_tokens=total.get("input_tokens", 0),
                    cached_input_tokens=total.get("cached_input_tokens", 0),
                    output_tokens=total.get("output_tokens", 0),
                )
                if isinstance(total, dict)
                else None
            )
            quota_items = [
                QuotaItem(
                    label=str(q.get("label", "")),
                    percent_used=float(q.get("percent_used", 0)),
                    reset_label=q.get("reset_label"),
                )
                for q in item.get("quota_items", [])
                if isinstance(q, dict)
            ]
            status_val = item.get("status", "not_available")
            try:
                status = UsageStatus(status_val)
            except ValueError:
                status = UsageStatus.NOT_AVAILABLE

            usages.append(
                CreditUsage(
                    app_id=str(item.get("app_id", "")),
                    app_name=str(item.get("app_name", "")),
                    installed=bool(item.get("installed", False)),
                    status=status,
                    running=bool(item.get("running", False)),
                    percent_used=item.get("percent_used"),
                    period_label=item.get("period_label"),
                    reset_label=item.get("reset_label"),
                    source=item.get("source"),
                    message=item.get("message"),
                    plan_label=item.get("plan_label"),
                    today_tokens=today_tokens,
                    total_tokens=total_tokens,
                    removable=bool(item.get("removable", False)),
                    quota_items=quota_items,
                    details=[str(d) for d in item.get("details", []) if isinstance(d, str)],
                )
            )
        return usages
    except Exception:
        return []

