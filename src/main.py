"""Entry point: system tray app, global hotkey, orchestration.

Wires together approval (Telegram), vault (aac connect), filler (keystroke),
and audit (JSONL log):

    hotkey -> guess domain from focused window -> request_approval
           -> (approved) fetch credential -> fill_if_focused -> audit

The orchestration core (:func:`handle_request`, :func:`guess_domain_from_title`)
is import-light and unit-tested. The tray + global-hotkey glue in :func:`main`
imports its GUI deps lazily and needs a live desktop to exercise.
"""

from __future__ import annotations

import logging
import re
import threading

from . import approval, audit, config, filler, vault

_LOG = logging.getLogger("claude_vault_bridge")

# Domain-like token: one or more dot-separated labels then a 2+ letter TLD.
_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})\b", re.IGNORECASE
)


def _safe_config() -> dict:
    try:
        return config.load()
    except Exception as exc:  # missing/invalid config -> run on defaults
        _LOG.warning("config not loaded (%s); using defaults", exc)
        return {}


def guess_domain_from_title(title: str) -> str | None:
    """Best-effort domain from a window title, e.g. 'Amazon.es - Sign In - ...'.

    Known limitation: a bare window title often lacks the domain (it's the page
    title, not the URL). Returns ``None`` when nothing domain-like is present;
    a future Chrome-extension integration can supply the real URL instead.
    """
    for marker in filler.CHROME_MARKERS:
        title = title.replace(marker, " ")
    match = _DOMAIN_RE.search(title)
    return match.group(1).lower() if match else None


def _fill_settings(cfg: dict) -> tuple[int, bool]:
    fill_cfg = cfg.get("fill", {}) if isinstance(cfg, dict) else {}
    return (
        int(fill_cfg.get("keystroke_delay_ms", 15)),
        bool(fill_cfg.get("submit_on_fill", False)),
    )


def is_whitelisted(domain: str, whitelist) -> bool:
    """True if ``domain`` equals or is a subdomain of any whitelist entry."""
    d = domain.lower().strip()
    for entry in whitelist or []:
        e = str(entry).lower().strip()
        if e and (d == e or d.endswith("." + e)):
            return True
    return False


def _username_hint(domain: str, cfg: dict) -> str | None:
    """Optional per-domain username to disambiguate multiple logins (config)."""
    accounts = cfg.get("vault", {}).get("accounts", {}) if isinstance(cfg, dict) else {}
    hint = accounts.get(domain) if isinstance(accounts, dict) else None
    return str(hint) if hint else None


def _login_fill(domain: str, cred, cfg: dict) -> None:
    delay, submit = _fill_settings(cfg)
    filler.fill_if_focused(domain, cred, submit=submit, keystroke_delay_ms=delay)


def _totp_fill(domain: str, cred, cfg: dict) -> None:
    if not cred.totp:
        raise vault.VaultError(f"no TOTP available for {domain!r}.")
    delay, _submit = _fill_settings(cfg)
    filler.fill_totp_if_focused(domain, cred.totp, submit=True, keystroke_delay_ms=delay)


def _run(domain: str, source: str, cfg: dict, fill_step) -> str:
    """Shared gate -> fetch -> fill -> audit pipeline. Returns the decision.

    The credential (if fetched) lives only inside this call; it is never
    returned, logged, or stored.
    """
    whitelist = cfg.get("approval", {}).get("whitelist", []) if isinstance(cfg, dict) else []
    if is_whitelisted(domain, whitelist):
        decision, latency_ms, approved = "whitelisted", 0, True
    else:
        timeout = int(cfg.get("approval", {}).get("timeout_seconds", 60))
        result = approval.request_approval_detailed(domain, timeout)
        decision, latency_ms, approved = result.decision, result.latency_ms, result.approved

    if approved:
        try:
            cred = vault.fetch(domain, username=_username_hint(domain, cfg))
            fill_step(domain, cred, cfg)
        except vault.MultipleMatchesError as exc:
            _LOG.warning("multiple logins for %s: %s", domain, exc.usernames)
            decision = "error"
        except Exception as exc:  # fetch, focus-lost, or fill failure
            _LOG.warning("fill failed for %s: %s", domain, exc)
            decision = "error"

    try:
        audit.log(domain, decision, latency_ms, source=source)
    except Exception as exc:  # auditing must never crash the flow
        _LOG.warning("audit write failed for %s: %s", domain, exc)

    _LOG.info("%s -> %s (%d ms)", domain, decision, latency_ms)
    return decision


def handle_request(domain: str, *, source: str = "hotkey", cfg: dict | None = None) -> str:
    """Approval (or whitelist) -> fetch -> fill username+password -> audit."""
    return _run(domain, source, cfg if cfg is not None else _safe_config(), _login_fill)


def handle_totp_request(domain: str, *, source: str = "totp", cfg: dict | None = None) -> str:
    """Approval (or whitelist) -> fetch fresh -> type the TOTP code -> audit."""
    return _run(domain, source, cfg if cfg is not None else _safe_config(), _totp_fill)


def trigger_from_active_window(*, source: str = "hotkey") -> str | None:
    """Resolve the focused window's domain and run a login cycle; ``None`` if unknown."""
    domain = guess_domain_from_title(filler.active_window_title())
    if not domain:
        _LOG.warning("could not determine a domain from the active window title")
        return None
    return handle_request(domain, source=source)


def trigger_totp_from_active_window(*, source: str = "totp") -> str | None:
    """Resolve the focused window's domain and type its TOTP; ``None`` if unknown."""
    domain = guess_domain_from_title(filler.active_window_title())
    if not domain:
        _LOG.warning("could not determine a domain from the active window title")
        return None
    return handle_totp_request(domain, source=source)


def _tray_image():
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, size - 6, size - 6), fill=(37, 99, 235, 255))  # blue disc
    draw.rectangle((26, 30, 38, 46), fill=(255, 255, 255, 255))        # lock body
    draw.arc((24, 16, 40, 36), start=180, end=360, fill=(255, 255, 255, 255), width=4)
    return image


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    cfg = _safe_config()
    hotkey_cfg = cfg.get("hotkey", {})
    combo = str(hotkey_cfg.get("combo", "ctrl+alt+l"))
    totp_combo = str(hotkey_cfg.get("totp_combo", "ctrl+alt+t"))

    import keyboard
    import pystray

    def _spawn(target) -> None:
        # Run off the hotkey/tray thread so the blocking approval doesn't freeze it.
        threading.Thread(target=target, daemon=True).start()

    keyboard.add_hotkey(combo, lambda: _spawn(trigger_from_active_window))
    keyboard.add_hotkey(totp_combo, lambda: _spawn(trigger_totp_from_active_window))
    _LOG.info(
        "Claude Vault Bridge running. Login: %s  TOTP: %s", combo, totp_combo
    )

    def on_quit(icon, _item) -> None:
        for hk in (combo, totp_combo):
            try:
                keyboard.remove_hotkey(hk)
            except (KeyError, ValueError):
                pass
        icon.stop()

    icon = pystray.Icon(
        "claude-vault-bridge",
        _tray_image(),
        "Claude Vault Bridge",
        menu=pystray.Menu(
            pystray.MenuItem(f"Login: {combo}", None, enabled=False),
            pystray.MenuItem(f"TOTP: {totp_combo}", None, enabled=False),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    icon.run()


if __name__ == "__main__":
    main()
