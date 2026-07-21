# Phase 0 — verify Agent Access on Windows

Goal: prove the foundation works and answer the design questions that shape everything after. **No project code yet — just external tools.**

## Setup

1. Create a **new, empty free Bitwarden account** for tool-controlled logins only.
   - Do NOT log in with your main account.
   - Add one dummy login (e.g. `example.com` with fake credentials).

2. Install Bitwarden CLI:
   ```powershell
   winget install Bitwarden.CLI
   bw --version
   bw login   # use the new account
   ```

3. Download the Windows Agent Access binary:
   - Grab `aac-windows-x86_64.zip` from the [latest release](https://github.com/bitwarden/agent-access/releases/latest).
   - Extract `aac.exe` to a folder on your PATH (e.g. `C:\tools\`).
   - `aac --version` should work in a fresh terminal.

## Verification

Open **two terminals**.

**Terminal 1 — provider side (holds the vault):**
```powershell
aac listen
```
When it starts, unlock the vault with `/unlock` and note the pairing token it prints.

**Terminal 2 — remote side (the "agent"):**
```powershell
aac connect --token <pairing-token> --domain example.com --output json
```

Expected output — a JSON blob with the dummy login's `username` and `password`.

## Questions to answer hands-on

Record answers in this doc as an addendum PR when done:

1. **Approval model on `aac listen`** — does it prompt interactively for each `aac connect` request, or does pairing pre-authorize? Determines exactly where our Telegram gate slots in.
2. **Tunnel routing** — inspect network activity during a `connect`: does the tunnel run fully local, or route via a Bitwarden relay? Affects our privacy note in the README.
3. **TOTP** — does `aac connect` return a `totp` field for items that have 2FA seeds? Confirms Phase 4 TOTP fill is straightforward.
4. **Version** — record the exact `aac --version` and `bw --version` used. Pin them in [`docs/versions.md`](versions.md) once Phase 1 starts.

## What NOT to do

- Do NOT install this or `bw` on a work-managed device (MDM / employer laptop).
- Do NOT put a real bank, primary email, or ID login into the tool's Bitwarden account. Ever.
