"""Tests for focus matching and keystroke sequencing (no real keyboard/window)."""

from __future__ import annotations

import pytest

from src.filler import FillError, fill, fill_if_focused, is_target_focused
from src.vault import Credential

TAB = object()
ENTER = object()


class FakeController:
    def __init__(self):
        self.events: list = []

    def type(self, ch):
        self.events.append(ch)

    def tap(self, key):
        self.events.append(key)


def _fill(cred, submit=False):
    kb = FakeController()
    fill(cred, submit=submit, keystroke_delay_ms=0, controller=kb, tab_key=TAB, enter_key=ENTER)
    return kb.events


def test_fill_types_username_tab_password():
    events = _fill(Credential("ab", "xy"))
    assert events == ["a", "b", TAB, "x", "y"]


def test_fill_submit_appends_enter():
    events = _fill(Credential("a", "b"), submit=True)
    assert events == ["a", TAB, "b", ENTER]


def test_fill_no_submit_has_no_enter():
    assert ENTER not in _fill(Credential("a", "b"))


@pytest.mark.parametrize(
    "domain,title,expected",
    [
        ("amazon.es", "Amazon.es - Sign In - Google Chrome", True),
        ("accounts.google.com", "Sign in - Google Accounts - Google Chrome", True),
        ("amazon.es", "Amazon.es - Sign In - Mozilla Firefox", False),   # not Chrome
        ("amazon.es", "New Tab - Google Chrome", False),                 # wrong page
        ("example.com", "example.com login - Google Chrome", True),
    ],
)
def test_title_matching(domain, title, expected):
    assert is_target_focused(domain, title=title) is expected


def test_fill_if_focused_raises_when_not_focused(monkeypatch):
    called = {"filled": False}
    monkeypatch.setattr("src.filler.fill", lambda *a, **k: called.__setitem__("filled", True))
    with pytest.raises(FillError):
        fill_if_focused("amazon.es", Credential("a", "b"), title="Bank - Google Chrome")
    assert called["filled"] is False
