# Phase 1 — Telegram approval bot

Goal: tap **Approve** / **Deny** on your phone to gate a credential request, with a
timeout that auto-denies. This is the human-in-the-loop gate; no vault access or
form filling happens yet (that's Phase 2).

Implemented in [`claude_vault_bridge/approval.py`](../claude_vault_bridge/approval.py):

- `request_approval(domain, timeout_seconds=60) -> bool` — sends the prompt,
  blocks until you tap a button or the timeout elapses, returns `True` only on an
  explicit **Approve**.
- `request_approval_detailed(...) -> ApprovalResult` — same, but also returns the
  decision (`approved` / `denied` / `timeout`) and latency, ready for the Phase 3
  audit log.

## One-time setup

1. **Create the bot.** In Telegram, message [@BotFather](https://t.me/BotFather),
   send `/newbot`, follow the prompts, and copy the **bot token** it gives you.

2. **Store the token in Windows Credential Manager** (never in a file):
   ```powershell
   .\.venv\Scripts\python.exe -c "import keyring; keyring.set_password('claude-vault-bridge', 'telegram_bot_token', '<BOT_TOKEN>')"
   ```

3. **Find your chat id.** Open a chat with your new bot and send it any message
   (e.g. `hi`). Then visit:
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
   and read `result[].message.chat.id`. (Alternatively, message
   [@userinfobot](https://t.me/userinfobot).)

4. **Configure.** Copy the example config and set your chat id:
   ```powershell
   Copy-Item config.example.yaml config.yaml
   ```
   In `config.yaml`, set `telegram.chat_id` to the number from step 3.
   `config.yaml` is gitignored.

## Try it

```powershell
.\.venv\Scripts\python.exe -m claude_vault_bridge.approval example.com
```

You should get a phone push with **✅ Approve / ⛔ Deny** buttons. Tapping either
edits the message to show the outcome; the command prints e.g.
`approved in 1840 ms`. Ignore it for 60s and it prints `timeout`.

## Notes

- Each prompt carries a random nonce, so tapping a button on an *old* prompt can
  never approve a *new* request.
- The bot token stays in Credential Manager; only `chat_id` and the timeout live
  in `config.yaml`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite uses a fake bot (no network, no token) to cover approve, deny, timeout,
stale-nonce, and wrong-chat rejection.
