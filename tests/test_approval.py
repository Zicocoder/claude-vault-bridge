"""Tests for the Telegram approval state machine.

These use a fake Bot so no network or real token is needed. The fake reads the
nonce out of the inline keyboard the code sends, then feeds back a matching (or
deliberately mismatched) button tap through get_updates.
"""

from __future__ import annotations

from types import SimpleNamespace

from claude_vault_bridge.approval import request_approval_detailed

CHAT_ID = 4242


def _make_update(update_id: int, data: str, chat_id: int = CHAT_ID) -> SimpleNamespace:
    async def answer(*_args, **_kwargs):
        return None

    callback_query = SimpleNamespace(
        data=data,
        message=SimpleNamespace(chat_id=chat_id),
        answer=answer,
    )
    return SimpleNamespace(update_id=update_id, callback_query=callback_query)


class FakeBot:
    """Minimal async stand-in for telegram.Bot used by _await_decision."""

    def __init__(self, tap: str | None = None, *, tap_chat_id: int = CHAT_ID):
        # tap: "approve" | "deny" | "stale" | None (no response -> timeout)
        self.tap = tap
        self.tap_chat_id = tap_chat_id
        self.captured_data: dict[str, str] = {}
        self.edits: list[str] = []
        self._delivered = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        buttons = reply_markup.inline_keyboard[0]
        self.captured_data = {b.text.split()[-1].lower(): b.callback_data for b in buttons}
        return SimpleNamespace(message_id=1)

    async def get_updates(self, offset=None, timeout=0, allowed_updates=None):
        if self.tap is None or self._delivered:
            return []
        self._delivered = True
        if self.tap == "approve":
            data = self.captured_data["approve"]
        elif self.tap == "deny":
            data = self.captured_data["deny"]
        else:  # stale: right shape, wrong nonce
            data = "approve:STALE-NONCE"
        return [_make_update(10, data, chat_id=self.tap_chat_id)]

    async def edit_message_text(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append(text)


def _run(tap, *, timeout=2, **kw):
    bot = FakeBot(tap, **kw)
    result = request_approval_detailed(
        "example.com", timeout_seconds=timeout, chat_id=CHAT_ID, bot=bot
    )
    return bot, result


def test_approve_tap_returns_approved():
    bot, result = _run("approve")
    assert result.approved is True
    assert result.decision == "approved"
    assert any("Approved" in e for e in bot.edits)


def test_deny_tap_returns_denied():
    _bot, result = _run("deny")
    assert result.approved is False
    assert result.decision == "denied"


def test_no_response_times_out():
    bot, result = _run(None, timeout=1)
    assert result.decision == "timeout"
    assert result.approved is False
    assert any("Timed out" in e for e in bot.edits)


def test_stale_nonce_is_ignored():
    # A tap carrying a different nonce must not approve this request.
    _bot, result = _run("stale", timeout=1)
    assert result.decision == "timeout"


def test_tap_from_wrong_chat_is_ignored():
    _bot, result = _run("approve", timeout=1, tap_chat_id=9999)
    assert result.decision == "timeout"
