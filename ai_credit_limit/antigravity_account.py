from __future__ import annotations

import base64
import json
import os
import re
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AntigravityAccountError(RuntimeError):
    pass


@dataclass(slots=True)
class AntigravityQuotaWindow:
    group: str
    label: str
    used_percent: float
    reset_label: str | None = None


@dataclass(slots=True)
class AntigravityAccountUsage:
    plan_label: str | None
    windows: list[AntigravityQuotaWindow] = field(default_factory=list)
    source: str = "Antigravity DevTools Models & Usage"


def fetch_antigravity_account_usage(timeout: float = 8.0) -> AntigravityAccountUsage:
    page = _find_antigravity_debug_page(timeout=min(1.0, timeout))
    if not page:
        raise AntigravityAccountError("未找到 Antigravity 调试页面")

    ws_url = page.get("webSocketDebuggerUrl")
    if not isinstance(ws_url, str) or not ws_url:
        raise AntigravityAccountError("Antigravity 调试页面没有 WebSocket 地址")

    text = _read_models_usage_text(page, ws_url, timeout=timeout)
    usage = parse_models_usage_text(text)
    if not usage.windows:
        raise AntigravityAccountError("Antigravity 页面没有可解析的额度百分比")
    return usage


def parse_models_usage_text(text: str) -> AntigravityAccountUsage:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    plan_label = _extract_plan(lines)
    windows: list[AntigravityQuotaWindow] = []

    group = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if line in {"Gemini Models", "Claude and GPT models"}:
            group = line
            index += 1
            continue
        if line in {"Weekly Limit", "Five Hour Limit"}:
            reset_text = None
            percent = None
            lookahead = index + 1
            while lookahead < min(len(lines), index + 6):
                candidate = lines[lookahead]
                if candidate in {"Weekly Limit", "Five Hour Limit", "Gemini Models", "Claude and GPT models"}:
                    break
                reset_text = reset_text or _extract_reset(candidate)
                percent = percent if percent is not None else _extract_percent(candidate)
                lookahead += 1
            if percent is not None:
                windows.append(
                    AntigravityQuotaWindow(
                        group=_friendly_group(group or "Model Quota"),
                        label=_friendly_label(line),
                        used_percent=percent,
                        reset_label=_friendly_reset(reset_text),
                    )
                )
            index = lookahead
            continue
        index += 1

    return AntigravityAccountUsage(plan_label=plan_label, windows=windows)


def _find_antigravity_debug_page(timeout: float) -> dict[str, Any] | None:
    """Find any DevTools page that we can navigate to the Models screen.

    We accept ANY page from the Antigravity process — we'll navigate to the
    Models & Usage URL afterwards.  The key check is: does the port respond to
    /json/list with a page that has a webSocketDebuggerUrl?
    """
    for port in _candidate_debug_ports():
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/list", timeout=timeout
            ) as response:
                pages = json.loads(response.read().decode("utf-8", errors="replace"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            continue
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            ws = str(page.get("webSocketDebuggerUrl") or "")
            page_type = str(page.get("type") or "")
            url = str(page.get("url") or "")
            # Accept any real page (not a worker/service-worker) that has a ws URL
            if ws and page_type == "page" and url:
                return page
        # Fallback: accept even worker pages if nothing else
        for page in pages:
            if isinstance(page, dict) and page.get("webSocketDebuggerUrl"):
                return page
    return None


def _candidate_debug_ports() -> list[int]:
    """Return candidate Chrome DevTools ports for Antigravity.

    Priority order:
    1. Port from DevToolsActivePort file (written by Electron/Chromium when
       launched with --remote-debugging-port=0)
    2. Ports found via lsof for 'Antigravi' processes
    3. Fallback: 49539
    """
    ports: list[int] = []

    # 1. Read DevToolsActivePort file (most reliable for --remote-debugging-port=0)
    user_data_dir = Path.home() / "Library" / "Application Support" / "Antigravity"
    active_port_file = user_data_dir / "DevToolsActivePort"
    if active_port_file.exists():
        try:
            first_line = active_port_file.read_text(encoding="utf-8").splitlines()[0].strip()
            port = int(first_line)
            if 1024 <= port <= 65535:
                ports.append(port)
        except (OSError, ValueError, IndexError):
            pass

    # 2. lsof scan for any Antigravity-related listening port
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        result = None

    if result and result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Antigravi" not in line:
                continue
            match = re.search(r"127\.0\.0\.1:(\d+)", line)
            if match:
                ports.append(int(match.group(1)))

    return _dedupe([*ports, 49539])


def _read_models_usage_text(page: dict[str, Any], ws_url: str, timeout: float) -> str:
    original_url = str(page.get("url") or "")
    models_url = _models_usage_url(original_url)
    should_restore = bool(original_url and models_url != original_url)

    with _WebSocketClient(ws_url, timeout=timeout) as client:
        client.call("Runtime.enable")
        client.call("Page.enable")
        if models_url != original_url:
            client.call("Page.navigate", {"url": models_url})
        try:
            value = _wait_for_models_text(client, timeout)
        finally:
            if should_restore:
                client.call("Page.navigate", {"url": original_url})
    if not isinstance(value, str) or not value.strip():
        raise AntigravityAccountError("Antigravity 页面文本为空")
    return value


def _models_usage_url(url: str) -> str:
    """Return the URL for the Models & Usage settings screen.

    We always navigate to the root of the language-server with the settings
    params, regardless of the current page URL.  Appending settingsOpen/
    settingsScreen to an arbitrary page URL doesn't work; the SPA only
    honours them when loaded from the root.
    """
    # Try to reuse the same host:port from the current page URL
    if url:
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme and parsed.hostname and parsed.port:
                base = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                return f"{base}/?settingsOpen=true&settingsScreen=Models"
        except Exception:
            pass
    # Fallback: default language-server port
    return "https://127.0.0.1:49548/?settingsOpen=true&settingsScreen=Models"



def _wait_for_models_text(client: "_WebSocketClient", timeout: float) -> str:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        result = client.call(
            "Runtime.evaluate",
            {
                "expression": "document.body ? document.body.innerText : ''",
                "returnByValue": True,
            },
        )
        value = result.get("result", {}).get("result", {}).get("value")
        if isinstance(value, str) and value.strip():
            last_text = value
            has_percent = bool(re.search(r"\d{1,3}(?:\.\d+)?%", value))
            has_keywords = any(
                kw in value
                for kw in ("Models & Usage", "Weekly Limit", "Five Hour Limit")
            )
            if has_percent and has_keywords:
                return value
        time.sleep(0.25)
    return last_text


def _extract_plan(lines: list[str]) -> str | None:
    for line in lines:
        if line.startswith("Your Plan:"):
            return line.split(":", 1)[1].strip().upper()
    return None


def _extract_percent(text: str) -> float | None:
    match = re.fullmatch(r"(\d{1,3}(?:\.\d+)?)%", text.strip())
    if not match:
        return None
    value = float(match.group(1))
    if 0 <= value <= 100:
        return value
    return None


def _extract_reset(text: str) -> str | None:
    match = re.search(r"fully refresh in ([^.]+)", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _friendly_group(value: str) -> str:
    return {
        "Gemini Models": "Gemini 模型",
        "Claude and GPT models": "Claude 与 GPT 模型",
        "Model Quota": "模型额度",
    }.get(value, value)


def _friendly_label(value: str) -> str:
    return {
        "Weekly Limit": "周额度",
        "Five Hour Limit": "5 小时额度",
    }.get(value, value)


def _friendly_reset(value: str | None) -> str | None:
    if not value:
        return None
    days = _first_int(r"(\d+)\s*days?", value)
    hours = _first_int(r"(\d+)\s*hours?", value)
    minutes = _first_int(r"(\d+)\s*minutes?", value)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    return "".join(parts) + "后" if parts else value


def _first_int(pattern: str, value: str) -> int | None:
    match = re.search(pattern, value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _dedupe(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class _WebSocketClient:
    def __init__(self, url: str, timeout: float) -> None:
        self.url = url
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.request_id = 0

    def __enter__(self) -> "_WebSocketClient":
        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme != "ws" or not parsed.hostname or not parsed.port:
            raise AntigravityAccountError(f"无法连接 WebSocket: {self.url}")
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._recv_until(sock, b"\r\n\r\n")
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            sock.close()
            raise AntigravityAccountError("Antigravity WebSocket 握手失败")
        self.sock = sock
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        self._send_json({"id": request_id, "method": method, "params": params or {}})
        while True:
            message = self._recv_json()
            if message.get("id") == request_id:
                return message

    def _send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.extend([0x80 | 126, *struct.pack("!H", length)])
        else:
            header.extend([0x80 | 127, *struct.pack("!Q", length)])
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        assert self.sock is not None
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_json(self) -> dict[str, Any]:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                value = json.loads(payload.decode("utf-8", errors="replace"))
                return value if isinstance(value, dict) else {}
            if opcode == 0x8:
                raise AntigravityAccountError("Antigravity WebSocket 已关闭")

    def _recv_frame(self) -> tuple[int, bytes]:
        assert self.sock is not None
        header = self._recv_exact(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, length: int) -> bytes:
        assert self.sock is not None
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.sock.recv(length - len(chunks))
            if not chunk:
                raise AntigravityAccountError("Antigravity WebSocket 连接中断")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _recv_until(sock: socket.socket, marker: bytes) -> bytes:
        chunks = bytearray()
        while marker not in chunks:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.extend(chunk)
        return bytes(chunks)
