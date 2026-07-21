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


def _parse(stdout: str) -> Credential:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise VaultError("aac did not return valid JSON.") from exc
    if not isinstance(data, dict):
        raise VaultError("aac JSON was not an object.")
    username = data.get("username")
    password = data.get("password")
    totp = data.get("totp")
    if not username or not password:
        raise VaultError("aac JSON is missing 'username' and/or 'password'.")
    return Credential(
        username=str(username),
        password=str(password),
        totp=str(totp) if totp else None,
    )


def fetch(
    domain: str,
    *,
    token: str | None = None,
    aac_path: str | None = None,
    extra_args: Sequence[str] | None = None,
    runner: Runner | None = None,
) -> Credential:
    """Fetch a single credential for ``domain`` via ``aac connect``.

    ``token``/``extra_args`` cover the pairing model Phase 0 pins down. Pass a
    custom ``runner`` (any callable taking argv, returning something with
    ``returncode``/``stdout``/``stderr``) to test without the real binary.
    """
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

    return _parse(proc.stdout)
