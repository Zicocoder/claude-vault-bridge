"""Append-only JSON-lines audit log.

One event per line: ``{ts, domain, decision, latency_ms, source}``.
Never records the credential itself — only that a request happened and how it was
resolved.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from . import config

Decision = Literal["approved", "denied", "timeout", "whitelisted", "error"]

DEFAULT_AUDIT_PATH = "audit/events.jsonl"
_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_path(path: str | Path | None) -> Path:
    if path is not None:
        p = Path(path)
    else:
        try:
            configured = config.load().get("audit", {}).get("path", DEFAULT_AUDIT_PATH)
        except Exception:
            configured = DEFAULT_AUDIT_PATH
        p = Path(configured)
    if not p.is_absolute():
        p = config.PROJECT_ROOT / p
    return p


def log(
    domain: str,
    decision: Decision,
    latency_ms: int,
    source: str = "hotkey",
    *,
    path: str | Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Append one audit event and return the file it was written to."""
    event: dict[str, Any] = {
        "ts": timestamp or _now_iso(),
        "domain": domain,
        "decision": decision,
        "latency_ms": int(latency_ms),
        "source": source,
    }
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False)
    with _LOCK:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return target


def read_events(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read all events back (for inspection/tests). Missing file -> empty list."""
    target = _resolve_path(path)
    if not target.exists():
        return []
    events: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                events.append(json.loads(raw))
    return events
