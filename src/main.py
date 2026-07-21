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


def handle_request(domain: str, *, source: str = "hotkey", cfg: dict | None = None) -> str:
    """Run one approval -> fetch -> fill cycle, audit it, return the decision.

    The credential (if fetched) lives only inside this call; it is never
    returned, logged, or stored.
    """
    cfg = cfg if cfg is not None else _safe_config()
    timeout = int(cfg.get("approval", {}).get("timeout_seconds", 60))

    result = approval.request_approval_detailed(domain, timeout)
    decision: str = result.decision

    if result.approved:
        try:
            cred = vault.fetch(domain)
            delay, submit = _fill_settings(cfg)
            filler.fill_if_focused(
                domain, cred, submit=submit, keystroke_delay_ms=delay
            )
        except Exception as exc:  # fetch, focus-lost, or fill failure
            _LOG.warning("fill failed for %s: %s", domain, exc)
            decision = "error"

    try:
        audit.log(domain, decision, result.latency_ms, source=source)
    except Exception as exc:  # auditing must never crash the flow
        _LOG.warning("audit write failed for %s: %s", domain, exc)

    _LOG.info("%s -> %s (%d ms)", domain, decision, result.latency_ms)
    return decision


def trigger_from_active_window(*, source: str = "hotkey") -> str | None:
    """Resolve the focused window's domain and run a cycle; ``None`` if unknown."""
    title = filler.active_window_title()
    domain = guess_domain_from_title(title)
    if not domain:
        _LOG.warning("could not determine a domain from window title: %r", title)
        return None
    return handle_request(domain, source=source)


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
    combo = str(cfg.get("hotkey", {}).get("combo", "ctrl+alt+l"))

    import keyboard
    import pystray

    def on_trigger() -> None:
        # Run off the hotkey/tray thread so the blocking approval doesn't freeze it.
        threading.Thread(
            target=trigger_from_active_window,
            kwargs={"source": "hotkey"},
            daemon=True,
        ).start()

    keyboard.add_hotkey(combo, on_trigger)
    _LOG.info("Claude Vault Bridge running. Press %s on a login page.", combo)

    def on_quit(icon, _item) -> None:
        try:
            keyboard.remove_hotkey(combo)
        except (KeyError, ValueError):
            pass
        icon.stop()

    icon = pystray.Icon(
        "claude-vault-bridge",
        _tray_image(),
        "Claude Vault Bridge",
        menu=pystray.Menu(
            pystray.MenuItem(f"Hotkey: {combo}", None, enabled=False),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    icon.run()


if __name__ == "__main__":
    main()
