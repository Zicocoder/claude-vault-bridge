"""Tests for the orchestration core (collaborators monkeypatched)."""

from __future__ import annotations

import pytest

from src import main
from src.approval import ApprovalResult
from src.filler import FillError
from src.vault import Credential, VaultError


@pytest.fixture
def wiring(monkeypatch):
    """Record calls to fetch/fill/audit and control the approval result."""
    state = {"fetched": False, "filled": False, "audited": None, "decision": "approved", "fetch_exc": None, "fill_exc": None}

    def fake_approval(domain, timeout):
        return ApprovalResult(decision=state["decision"], latency_ms=1500)

    def fake_fetch(domain):
        state["fetched"] = True
        if state["fetch_exc"]:
            raise state["fetch_exc"]
        return Credential("user", "pass")

    def fake_fill(domain, cred, *, submit=False, keystroke_delay_ms=15):
        if state["fill_exc"]:
            raise state["fill_exc"]
        state["filled"] = True

    def fake_audit(domain, decision, latency_ms, source="hotkey"):
        state["audited"] = (domain, decision, latency_ms, source)

    monkeypatch.setattr(main.approval, "request_approval_detailed", fake_approval)
    monkeypatch.setattr(main.vault, "fetch", fake_fetch)
    monkeypatch.setattr(main.filler, "fill_if_focused", fake_fill)
    monkeypatch.setattr(main.audit, "log", fake_audit)
    return state


def test_approved_fetches_fills_and_audits(wiring):
    decision = main.handle_request("example.com", cfg={})
    assert decision == "approved"
    assert wiring["fetched"] and wiring["filled"]
    assert wiring["audited"] == ("example.com", "approved", 1500, "hotkey")


def test_denied_skips_fetch(wiring):
    wiring["decision"] = "denied"
    decision = main.handle_request("example.com", cfg={})
    assert decision == "denied"
    assert wiring["fetched"] is False
    assert wiring["audited"][1] == "denied"


def test_timeout_skips_fetch(wiring):
    wiring["decision"] = "timeout"
    assert main.handle_request("example.com", cfg={}) == "timeout"
    assert wiring["fetched"] is False


def test_fill_error_becomes_error_decision(wiring):
    wiring["fill_exc"] = FillError("wrong window")
    decision = main.handle_request("example.com", cfg={})
    assert decision == "error"
    assert wiring["audited"][1] == "error"


def test_fetch_error_becomes_error_decision(wiring):
    wiring["fetch_exc"] = VaultError("vault locked")
    assert main.handle_request("example.com", cfg={}) == "error"


def test_audit_failure_does_not_crash(wiring, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(main.audit, "log", boom)
    # Still returns the decision despite the audit write failing.
    assert main.handle_request("example.com", cfg={}) == "approved"


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Amazon.es - Sign In - Google Chrome", "amazon.es"),
        ("Log in | example.com - Google Chrome", "example.com"),
        ("accounts.google.com - Google Chrome", "accounts.google.com"),
        ("New Tab - Google Chrome", None),
        ("Bar Inc. - Google Chrome", None),
    ],
)
def test_guess_domain_from_title(title, expected):
    assert main.guess_domain_from_title(title) == expected


def test_trigger_returns_none_when_no_domain(monkeypatch):
    monkeypatch.setattr(main.filler, "active_window_title", lambda: "New Tab - Google Chrome")
    assert main.trigger_from_active_window() is None
