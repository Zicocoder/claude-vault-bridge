"""Tests for the orchestration core (collaborators monkeypatched)."""

from __future__ import annotations

import pytest

from src import main
from src.approval import ApprovalResult
from src.filler import FillError
from src.vault import Credential, MultipleMatchesError, VaultError


@pytest.fixture
def wiring(monkeypatch):
    """Record calls to fetch/fill/audit and control the approval result."""
    state = {
        "approval_calls": 0,
        "fetched": False,
        "filled": False,
        "totp_filled": None,
        "audited": None,
        "decision": "approved",
        "fetch_exc": None,
        "fill_exc": None,
        "totp": None,
    }

    def fake_approval(domain, timeout):
        state["approval_calls"] += 1
        return ApprovalResult(decision=state["decision"], latency_ms=1500)

    def fake_fetch(domain, *, username=None):
        state["fetched"] = True
        if state["fetch_exc"]:
            raise state["fetch_exc"]
        return Credential("user", "pass", state["totp"])

    def fake_fill(domain, cred, *, submit=False, keystroke_delay_ms=15):
        if state["fill_exc"]:
            raise state["fill_exc"]
        state["filled"] = True

    def fake_totp_fill(domain, totp, *, submit=True, keystroke_delay_ms=15):
        state["totp_filled"] = totp

    def fake_audit(domain, decision, latency_ms, source="hotkey"):
        state["audited"] = (domain, decision, latency_ms, source)

    monkeypatch.setattr(main.approval, "request_approval_detailed", fake_approval)
    monkeypatch.setattr(main.vault, "fetch", fake_fetch)
    monkeypatch.setattr(main.filler, "fill_if_focused", fake_fill)
    monkeypatch.setattr(main.filler, "fill_totp_if_focused", fake_totp_fill)
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


# --- Phase 4: whitelist tier ---

WL_CFG = {"approval": {"whitelist": ["example.com"]}}


def test_whitelisted_domain_skips_approval(wiring):
    decision = main.handle_request("example.com", cfg=WL_CFG)
    assert decision == "whitelisted"
    assert wiring["approval_calls"] == 0       # no phone prompt
    assert wiring["fetched"] and wiring["filled"]
    assert wiring["audited"] == ("example.com", "whitelisted", 0, "hotkey")


def test_whitelist_matches_subdomain(wiring):
    assert main.handle_request("login.example.com", cfg=WL_CFG) == "whitelisted"
    assert wiring["approval_calls"] == 0


def test_non_whitelisted_still_prompts(wiring):
    main.handle_request("other.com", cfg=WL_CFG)
    assert wiring["approval_calls"] == 1


@pytest.mark.parametrize(
    "domain,whitelist,expected",
    [
        ("example.com", ["example.com"], True),
        ("login.example.com", ["example.com"], True),
        ("notexample.com", ["example.com"], False),   # not a subdomain
        ("example.com", [], False),
        ("EXAMPLE.com", ["example.com"], True),        # case-insensitive
    ],
)
def test_is_whitelisted(domain, whitelist, expected):
    assert main.is_whitelisted(domain, whitelist) is expected


# --- Phase 4: TOTP ---

def test_totp_request_types_code(wiring):
    wiring["totp"] = "654321"
    decision = main.handle_totp_request("example.com", cfg={})
    assert decision == "approved"
    assert wiring["totp_filled"] == "654321"


def test_totp_request_without_totp_is_error(wiring):
    wiring["totp"] = None
    assert main.handle_totp_request("example.com", cfg={}) == "error"


# --- Phase 4: multiple matches ---

def test_multiple_matches_becomes_error(wiring):
    wiring["fetch_exc"] = MultipleMatchesError(["a@x.com", "b@x.com"])
    assert main.handle_request("x.com", cfg={}) == "error"
    assert wiring["audited"][1] == "error"


def test_username_hint_passed_to_fetch(wiring, monkeypatch):
    seen = {}

    def fake_fetch(domain, *, username=None):
        seen["username"] = username
        return Credential("work@example.com", "pass")

    monkeypatch.setattr(main.vault, "fetch", fake_fetch)
    cfg = {"vault": {"accounts": {"github.com": "work@example.com"}}}
    main.handle_request("github.com", cfg=cfg)
    assert seen["username"] == "work@example.com"


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
