"""Tests for the aac connect wrapper, using a fake runner (no real binary)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from src.vault import Credential, VaultError, fetch


def _runner(returncode=0, stdout="", stderr=""):
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    run.calls = calls
    return run


def test_fetch_parses_credential():
    run = _runner(stdout='{"username": "alice", "password": "s3cret", "totp": "123456"}')
    cred = fetch("example.com", runner=run)
    assert cred == Credential("alice", "s3cret", "123456")


def test_fetch_builds_expected_command():
    run = _runner(stdout='{"username": "a", "password": "b"}')
    fetch("amazon.es", token="pair-tok", runner=run)
    assert run.calls[0] == [
        "aac", "connect", "--domain", "amazon.es",
        "--output", "json", "--token", "pair-tok",
    ]


def test_missing_totp_is_none():
    run = _runner(stdout='{"username": "a", "password": "b"}')
    assert fetch("example.com", runner=run).totp is None


def test_nonzero_exit_raises():
    run = _runner(returncode=1, stderr="vault locked")
    with pytest.raises(VaultError, match="vault locked"):
        fetch("example.com", runner=run)


def test_bad_json_raises():
    run = _runner(stdout="not json")
    with pytest.raises(VaultError, match="valid JSON"):
        fetch("example.com", runner=run)


def test_missing_fields_raises():
    run = _runner(stdout='{"username": "a"}')
    with pytest.raises(VaultError, match="username.*password"):
        fetch("example.com", runner=run)


def test_empty_domain_raises():
    with pytest.raises(VaultError, match="domain"):
        fetch("", runner=_runner())


def test_timeout_raises():
    def run(cmd):
        raise subprocess.TimeoutExpired(cmd, 30)

    with pytest.raises(VaultError, match="timed out"):
        fetch("example.com", runner=run)
