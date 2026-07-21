# Phase 4 — whitelist tier, TOTP fill, multiple matches

Three refinements on top of the Phase 3 orchestrator.

## 1. Whitelist tier

Domains listed under `approval.whitelist` in `config.yaml` skip the phone tap
entirely — they go straight to fetch + fill — but are **still audited**, with
decision `whitelisted`. Matching is case-insensitive and covers subdomains
(`example.com` matches `login.example.com`).

```yaml
approval:
  whitelist:
    - example.com
```

Use it only for genuinely low-risk logins; the whole point of the phone gate is
the high-risk ones. Implemented as `main.is_whitelisted()` + the shared `_run`
pipeline.

## 2. TOTP fill

A second global hotkey (`hotkey.totp_combo`, default **Ctrl+Alt+T**) types a
2FA code on the second-factor page. On press it runs the same gate
(whitelist/approval) and **re-fetches** a fresh credential from aac — so the TOTP
is current and no secret is cached between the two hotkey presses — then types
just the code (+ Enter).

- `filler.fill_totp()` / `fill_totp_if_focused()` — type the code, focus-gated.
- `main.handle_totp_request()` / `trigger_totp_from_active_window()` — the flow.
- If aac returns no `totp` for the item, the outcome is audited as `error`.

## 3. Multiple-match handling

If `aac connect` returns more than one login for a domain (a JSON array, or an
object with an `items`/`matches`/`logins`/`results` array):

- `vault.fetch_all()` returns them all.
- `vault.fetch()` returns the single match, or raises `MultipleMatchesError`
  (carrying `.usernames`) when there's more than one and no hint.
- Disambiguate with a per-domain username in `config.yaml`:
  ```yaml
  vault:
    accounts:
      github.com: work@example.com
  ```
- With no hint, the orchestrator audits the attempt as `error` and logs the
  candidate usernames — it never guesses which account to type.

> Follow-up idea: surface the candidate usernames as Telegram buttons so you can
> pick the account from your phone. Left for later to keep this phase tight.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

New coverage: multiple-match parsing + disambiguation (`test_vault.py`), TOTP
keystrokes (`test_filler.py`), and whitelist/TOTP/multi-match orchestration
(`test_main.py`). 60 tests, all green, still no network/GUI/secrets.
