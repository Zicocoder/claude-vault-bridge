# Phase 2 — vault fetch + focus check + keystroke fill

Goal: turn an approved request into a filled login form. Two pieces:

- [`src/vault.py`](../src/vault.py) — `fetch(domain) -> Credential` runs
  `aac connect --domain <d> --output json`, parses the JSON, and returns a
  `Credential(username, password, totp)`. Nothing hits disk or the clipboard.
- [`src/filler.py`](../src/filler.py) — `is_target_focused(domain)` confirms
  Chrome is the foreground window **and** its title references the domain;
  `fill(credential)` types `username` + Tab + `password` via keystrokes;
  `fill_if_focused(domain, credential)` combines the two and refuses to type if
  the wrong window is focused.

Neither step prompts — they run *after* the Phase 1 approval returns `True`. The
Phase 3 orchestrator will chain: approve → `fetch` → `fill_if_focused`.

## Security properties

- **No clipboard.** JSON → local variables → keystrokes. References dropped after
  fill (Python can't scrub immutable `str` memory — see the note in `filler.py`).
- **Focus gate.** `fill_if_focused` raises `FillError` unless the foreground
  window is Chrome and the title contains the domain (or one of its labels). This
  stops the password being typed into the wrong app if focus moved.
- **Pin `aac`.** Record the version you test with (see `docs/phase-0.md` Q4).

## Configuration (`config.yaml`)

- `fill.keystroke_delay_ms` — per-character delay; raise it if fields drop
  characters (default 15).
- `fill.submit_on_fill` — press Enter after the password (default false).
- `aac` binary: found on `PATH`, or override with the `AAC_BINARY` env var.

## Live verification (needs real `aac` + Chrome — your side)

1. Complete `docs/phase-0.md` so `aac connect` returns a dummy credential.
2. Dry-run the fetch (prints the parsed username only, never the password):
   ```powershell
   .\.venv\Scripts\python.exe -c "from src.vault import fetch; print(fetch('example.com').username)"
   ```
3. Open the site's login page in Chrome, click the username field, then run a
   fill against a **dummy** account and watch it type. (The Phase 3 hotkey will
   trigger this automatically.)

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`test_vault.py` covers parsing, command construction, and every error path with a
fake runner. `test_filler.py` covers the keystroke sequence and title matching
with a fake controller — no real binary, keyboard, or window needed.
