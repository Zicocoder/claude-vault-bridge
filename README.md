# Claude Vault Bridge

A Windows companion tool for [Bitwarden Agent Access](https://github.com/bitwarden/agent-access) that adds two missing pieces for using Claude in Chrome with a password vault:

- **Phone-tap approval** — approve credential requests from your phone (Telegram) instead of being at the PC
- **Browser login filling** — fetches the credential from `aac connect` and types it into the focused Chrome login form

> Status: **early / pre-alpha**. Nothing to install yet. This repo currently holds the design, structure, and Phase 0 verification steps.

---

## Why this exists

Bitwarden's Agent Access ships an end-to-end encrypted CLI + protocol that hands a single credential to an agent for a single domain, with human approval — vault never exposed. It's designed for CLI/dev-agent use (env-var injection), and approval happens interactively on the same machine as the vault.

This project adds the last mile for browser use:

1. Move approval to a phone tap over Telegram, so you can approve without switching context
2. Fill the credential into a Chrome login form instead of injecting it as an env var
3. Optional whitelist for low-risk sites (skip the phone tap, still logged)

---

## Architecture

```
[aac listen]  ─ provider side, wraps `bw` CLI (dedicated Bitwarden account)
     ▲ Noise-encrypted tunnel
     │
[Bridge — Python, system tray]
     │ hotkey pressed / login wall detected
     ▼
[Telegram bot → phone push]
   "Login requested: amazon.es — Approve / Deny"
     │
  Approve ──► aac connect --domain amazon.es --output json
     │              │ returns { username, password, totp }
     │              ▼
     │        [Focus check → keystroke fill → wipe memory]
     │
  Deny / 60s timeout ──► nothing filled, logged
```

---

## Security model

Non-negotiable rules the code enforces:

1. **Dedicated Bitwarden account** — only logins the tool may ever use. Banking, primary email, government/ID: **never** in this account.
2. Telegram bot token + Bitwarden master password → **Windows Credential Manager**, never in files.
3. **No clipboard.** JSON → variables → keystrokes → wipe.
4. **Focus check** before typing: Chrome focused **and** window title matches the requested domain.
5. **Audit log** (JSON lines): timestamp, domain, decision, latency.
6. **Idle lock** on the vault after N minutes.
7. Agent Access is early preview — **pin the `aac` version** you test with.

Not a security product. Convenience tool with reasonable hygiene. Read the code before running it.

---

## Roadmap

- **Phase 0** — verify Agent Access on Windows end-to-end (see [`docs/phase-0.md`](docs/phase-0.md))
- **Phase 1** — Telegram approval bot with inline buttons and timeout
- **Phase 2** — `aac connect` wrapper + focus check + keystroke fill
- **Phase 3** — global hotkey, tray app, audit log, config
- **Phase 4** — whitelist tier, TOTP fill, multiple-match handling
- **Phase 5** — polish, demo GIF, release, distribution

---

## Requirements (planned)

- Windows 10/11 x64
- Python 3.12+
- [Bitwarden CLI (`bw`)](https://bitwarden.com/help/cli/)
- [Agent Access (`aac`)](https://github.com/bitwarden/agent-access/releases)
- Telegram account (for the approval bot)

---

## License

MIT — see [`LICENSE`](LICENSE).
