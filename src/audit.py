"""Append-only JSON-lines audit log.

One event per line: {ts, domain, decision, latency_ms, source}.
Never records the credential itself.
"""

from typing import Literal

Decision = Literal["approved", "denied", "timeout", "whitelisted", "error"]


def log(domain: str, decision: Decision, latency_ms: int, source: str = "hotkey") -> None:
    raise NotImplementedError("Phase 3")
