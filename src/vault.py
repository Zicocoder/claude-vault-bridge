"""Bitwarden Agent Access wrapper.

Subprocess-calls `aac connect --domain <d> --output json` and parses the
result. Kept separate so the SDK bindings can replace this later without
touching the rest of the app.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Credential:
    username: str
    password: str
    totp: str | None = None


def fetch(domain: str) -> Credential:
    raise NotImplementedError("Phase 2")
