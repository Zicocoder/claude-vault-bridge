"""Phone-tap approval via Telegram inline buttons.

Sends an Approve / Deny message to your phone and blocks until you tap a button
or the request times out. Returns ``True`` only on an explicit Approve tap.

Design notes
------------
* The bot token is read from Windows Credential Manager (keyring service
  ``claude-vault-bridge``, entry ``telegram_bot_token``) — never from disk.
* The target ``chat_id`` and default ``timeout_seconds`` come from ``config.yaml``.
* Each request embeds a random nonce in the button callback data, so a stale tap
  on an earlier prompt can never approve a newer request.
* Uses ``Bot.get_updates`` long-polling rather than the full Application
  dispatcher, so the call is a self-contained synchronous one-shot suitable for
  the hotkey path (Phase 3).
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal

import keyring
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from . import config

KEYRING_SERVICE = "claude-vault-bridge"
KEYRING_TOKEN_ENTRY = "telegram_bot_token"

Decision = Literal["approved", "denied", "timeout"]


@dataclass(frozen=True)
class ApprovalResult:
    """Outcome of one approval prompt, including how long the user took."""

    decision: Decision
    latency_ms: int

    @property
    def approved(self) -> bool:
        return self.decision == "approved"


class ApprovalConfigError(RuntimeError):
    """The bot token or chat id needed to send an approval prompt is missing."""


def load_bot_token() -> str:
    """Fetch the Telegram bot token from Windows Credential Manager."""
    token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_ENTRY)
    if not token:
        raise ApprovalConfigError(
            "Telegram bot token not found in Windows Credential Manager. "
            "Store it once with:\n"
            f'    py -c "import keyring; keyring.set_password('
            f"'{KEYRING_SERVICE}', '{KEYRING_TOKEN_ENTRY}', '<BOT_TOKEN>')\""
        )
    return token


def _load_chat_id() -> int:
    cfg = config.load()
    try:
        chat_id = cfg["telegram"]["chat_id"]
    except (KeyError, TypeError) as exc:
        raise ApprovalConfigError("telegram.chat_id is missing from config.yaml.") from exc
    if not chat_id:
        raise ApprovalConfigError(
            "telegram.chat_id is 0/empty in config.yaml — set it to your chat id "
            "(message your bot, then check https://api.telegram.org/bot<TOKEN>/getUpdates)."
        )
    return int(chat_id)


def _default_timeout() -> int:
    try:
        return int(config.load().get("approval", {}).get("timeout_seconds", 60))
    except Exception:
        return 60


async def _await_decision(
    bot: Any,
    chat_id: int,
    domain: str,
    timeout_seconds: int,
    *,
    poll_interval: int = 5,
) -> ApprovalResult:
    """Send the prompt and long-poll for a matching button tap until the deadline."""
    nonce = secrets.token_urlsafe(8)
    approve_data = f"approve:{nonce}"
    deny_data = f"deny:{nonce}"
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Approve", callback_data=approve_data),
            InlineKeyboardButton("⛔ Deny", callback_data=deny_data),
        ]]
    )
    text = f"\U0001f510 Login requested: *{domain}*\nApprove within {timeout_seconds}s."
    message = await bot.send_message(
        chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown"
    )

    start = time.monotonic()
    deadline = start + timeout_seconds
    offset: int | None = None
    decision: Decision = "timeout"

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        long_poll = max(0, min(poll_interval, int(remaining)))
        try:
            updates = await bot.get_updates(
                offset=offset, timeout=long_poll, allowed_updates=["callback_query"]
            )
        except TelegramError:
            # Transient network hiccup — keep retrying until the deadline.
            await asyncio.sleep(1)
            continue

        matched = False
        for update in updates:
            offset = update.update_id + 1
            cq = update.callback_query
            if cq is None or cq.data not in (approve_data, deny_data):
                continue
            if cq.message is None or cq.message.chat_id != chat_id:
                continue
            decision = "approved" if cq.data == approve_data else "denied"
            try:
                await cq.answer("Approved ✅" if decision == "approved" else "Denied ⛔")
            except TelegramError:
                pass
            matched = True
            break
        if matched:
            break

    latency_ms = int((time.monotonic() - start) * 1000)
    final_text = {
        "approved": f"✅ Approved: *{domain}*",
        "denied": f"⛔ Denied: *{domain}*",
        "timeout": f"⏱ Timed out (no response): *{domain}*",
    }[decision]
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text=final_text,
            parse_mode="Markdown",
        )
    except TelegramError:
        pass

    return ApprovalResult(decision=decision, latency_ms=latency_ms)


def request_approval_detailed(
    domain: str,
    timeout_seconds: int | None = None,
    *,
    chat_id: int | None = None,
    token: str | None = None,
    bot: Any | None = None,
) -> ApprovalResult:
    """Prompt for approval and return the full result (decision + latency).

    Args mirror :func:`request_approval` but expose the seams needed for testing
    and for the Phase 3 orchestrator (inject ``bot``/``chat_id`` to bypass the
    keyring + config lookups).
    """
    if timeout_seconds is None:
        timeout_seconds = _default_timeout()
    if bot is None:
        bot = Bot(token=token or load_bot_token())
    if chat_id is None:
        chat_id = _load_chat_id()

    async def _run() -> ApprovalResult:
        async with bot:
            return await _await_decision(bot, chat_id, domain, timeout_seconds)

    return asyncio.run(_run())


def request_approval(domain: str, timeout_seconds: int = 60) -> bool:
    """Prompt for approval; return ``True`` only on an explicit Approve tap."""
    return request_approval_detailed(domain, timeout_seconds).approved


if __name__ == "__main__":  # manual end-to-end check once token + chat_id are set
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    result = request_approval_detailed(target)
    print(f"{result.decision} in {result.latency_ms} ms")
