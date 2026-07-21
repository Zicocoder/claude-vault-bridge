"""Bitwarden Agent Access wrapper.

Subprocess-calls ``aac connect --domain <d> --output json`` and parses the
result into a :class:`Credential`. Kept separate so the SDK bindings can replace
this later without touching the rest of the app.

The credential never touches disk or the clipboard: it lives only in the returned
dataclass, which the filler consumes and drops.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

DEFAULT_AAC_BINARY = "aac"
_TIMEOUT_SECONDS = 30

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class Credential:
    username: str
    password: str
    totp: str | None = None


class VaultError(RuntimeError):
    """Raised when the aac invocation or its output could not be used."""


class MultipleMatchesError(VaultError):
    """aac returned more than one login and no username was given to pick one."""

    def __init__(self, usernames: Sequence[str]):
        self.usernames = list(usernames)
        joined = ", ".join(self.usernames) or "<none>"
        super().__init__(f"multiple logins matched ({joined}); pass a username to disambiguate.")


def _resolve_binary(aac_path: str | None) -> str:
    candidate = aac_path or os.environ.get("AAC_BINARY") or DEFAULT_AAC_BINARY
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    if os.path.isfile(candidate):
        return candidate
    raise VaultError(
        f"aac binary not found ({candidate!r}). Download it per docs/phase-0.md, "
        "put aac(.exe) on your PATH, or set the AAC_BINARY environment variable."
    )


def _default_runner(cmd: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(  # noqa: S603 - args are built from a fixed template
        list(cmd), capture_output=True, text=True, timeout=_TIMEOUT_SECONDS
    )


def _credential_from(obj: Any) -> Credential:
    if not isinstance(obj, dict):
        raise VaultError("aac login entry was not a JSON object.")
    username = obj.get("username")
    password = obj.get("password")
    totp = obj.get("totp")
    if not username or not password:
        raise VaultError("aac login is missing 'username' and/or 'password'.")
    return Credential(
        username=str(username),
        password=str(password),
        totp=str(totp) if totp else None,
    )


# Keys aac might use to wrap a list of matches inside an object.
_LIST_KEYS = ("items", "matches", "logins", "results")


def _parse_all(stdout: str) -> list[Credential]:
    """Parse aac output into one or more credentials (single object or a list)."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise VaultError("aac did not return valid JSON.") from exc
    if isinstance(data, list):
        return [_credential_from(item) for item in data]
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return [_credential_from(item) for item in value]
        return [_credential_from(data)]
    raise VaultError("aac JSON was not an object or array.")


def fetch_all(
    domain: str,
    *,
    token: str | None = None,
    aac_path: str | None = None,
    extra_args: Sequence[str] | None = None,
    runner: Runner | None = None,
) -> list[Credential]:
    """Fetch every credential aac returns for ``domain`` (may be more than one)."""
    if not domain or not isinstance(domain, str):
        raise VaultError("domain must be a non-empty string.")

    if runner is None:
        binary = _resolve_binary(aac_path)
        runner = _default_runner
    else:
        binary = aac_path or DEFAULT_AAC_BINARY

    cmd: list[str] = [binary, "connect", "--domain", domain, "--output", "json"]
    if token:
        cmd += ["--token", token]
    if extra_args:
        cmd += list(extra_args)

    try:
        proc = runner(cmd)
    except FileNotFoundError as exc:
        raise VaultError(f"Could not execute aac binary: {binary!r}.") from exc
    except subprocess.TimeoutExpired as exc:
        raise VaultError("aac connect timed out.") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or "no stderr"
        raise VaultError(f"aac connect failed (exit {proc.returncode}): {detail}")

    matches = _parse_all(proc.stdout)
    if not matches:
        raise VaultError(f"aac returned no logins for {domain!r}.")
    return matches


def fetch(
    domain: str,
    *,
    username: str | None = None,
    token: str | None = None,
    aac_path: str | None = None,
    extra_args: Sequence[str] | None = None,
    runner: Runner | None = None,
) -> Credential:
    """Fetch a single credential for ``domain`` via ``aac connect``.

    If aac returns multiple logins, pass ``username`` to pick one; otherwise a
    :class:`MultipleMatchesError` (carrying ``.usernames``) is raised. ``token``/
    ``extra_args`` cover the pairing model Phase 0 pins down. Pass a custom
    ``runner`` (argv -> object with ``returncode``/``stdout``/``stderr``) to test
    without the real binary.
    """
    matches = fetch_all(
        domain, token=token, aac_path=aac_path, extra_args=extra_args, runner=runner
    )
    if username is not None:
        chosen = [c for c in matches if c.username == username]
        if not chosen:
            raise VaultError(f"no login with username {username!r} for {domain!r}.")
        return chosen[0]
    if len(matches) > 1:
        raise MultipleMatchesError([c.username for c in matches])
    return matches[0]
