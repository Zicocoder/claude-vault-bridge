# Phase 3 — orchestrator: hotkey, tray, audit log

Goal: a running program that ties the pieces together. Press the hotkey on a
login page and the full cycle fires.

    hotkey -> guess domain from focused window -> request_approval (phone)
           -> (approved) fetch credential -> fill_if_focused -> audit

Implemented in:

- [`src/main.py`](../src/main.py)
  - `handle_request(domain)` — the orchestration core: approval → fetch → fill →
    audit. Returns the decision (`approved` / `denied` / `timeout` / `error`).
    A fetch/focus/fill failure downgrades the outcome to `error`; an audit-write
    failure is logged but never crashes the flow.
  - `guess_domain_from_title(title)` — best-effort domain from the focused window
    title.
  - `trigger_from_active_window()` — what the hotkey calls.
  - `main()` — global hotkey (`keyboard`) + system-tray icon (`pystray`) with a
    **Quit** item.
- [`src/audit.py`](../src/audit.py) — `log(domain, decision, latency_ms, source)`
  appends one JSON line per event to `audit/events.jsonl` (gitignored). Records
  **only** timestamp, domain, decision, latency, and source — never the
  credential. `read_events()` reads them back.

## Run it

```powershell
.\.venv\Scripts\python.exe -m src.main
```

A tray icon appears. Focus a login page in Chrome and press **Ctrl+Alt+L** (or
your `hotkey.combo`). You get the phone prompt; approving fills the form. Every
attempt is appended to `audit/events.jsonl`. Quit from the tray menu.

## Config used this phase (`config.yaml`)

- `hotkey.combo` — global hotkey (default `ctrl+alt+l`).
- `approval.timeout_seconds` — auto-deny after N seconds.
- `fill.keystroke_delay_ms`, `fill.submit_on_fill` — passed to the filler.
- `audit.path` — JSONL log location (default `audit/events.jsonl`).

## Known limitation — domain detection

A global hotkey only sees the **window title**, which is the page title, not the
URL — so `guess_domain_from_title` is best-effort and returns `None` when the
title has nothing domain-like (you'll see a log line, and nothing is typed). The
clean fix is a Chrome-extension/native-messaging bridge that hands over the real
URL; that's a candidate for a later phase. The whitelist tier and TOTP fill are
Phase 4.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`test_main.py` covers the orchestration wiring (approved/denied/timeout, fetch
and fill errors → `error`, audit-failure resilience) and title→domain guessing,
all with collaborators monkeypatched. `test_audit.py` covers the JSONL writer,
including that no credential fields are ever written. The tray/hotkey glue in
`main()` needs a live desktop and is verified by running it.
