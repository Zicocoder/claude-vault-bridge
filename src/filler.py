"""Focus verification and keystroke-based form fill.

Confirms Chrome is focused and the foreground window title matches the requested
domain, then types username + Tab + password. Never touches the clipboard.

A note on "wiping": Python ``str`` objects are immutable, so we cannot truly
scrub the credential from memory. The best we do is drop our references promptly
so the garbage collector can reclaim them; callers should not retain the
``Credential`` after filling.
"""

from __future__ import annotations

import time

from .vault import Credential

# Foreground-window title suffix Chrome uses on Windows.
CHROME_MARKERS = ("Google Chrome",)


class FillError(RuntimeError):
    """Raised when the target window is not focused, so nothing was typed."""


def _domain_tokens(domain: str) -> list[str]:
    """Domain plus its meaningful labels (len > 2), lowercased, for title matching."""
    domain = domain.lower().strip()
    labels = [label for label in domain.split(".") if len(label) > 2]
    return [domain, *labels]


def _title_matches(domain: str, title: str) -> bool:
    lowered = title.lower()
    if not any(marker.lower() in lowered for marker in CHROME_MARKERS):
        return False
    return any(token in lowered for token in _domain_tokens(domain))


def active_window_title() -> str:
    """Return the foreground window title, or "" if none (lazy GUI import)."""
    import pygetwindow as gw

    window = gw.getActiveWindow()
    if window is None:
        return ""
    return getattr(window, "title", "") or ""


def is_target_focused(domain: str, *, title: str | None = None) -> bool:
    """True only if Chrome is foreground and its title references ``domain``."""
    if title is None:
        title = active_window_title()
    return _title_matches(domain, title)


def fill(
    credential: Credential,
    submit: bool = False,
    *,
    keystroke_delay_ms: int = 15,
    controller=None,
    tab_key=None,
    enter_key=None,
) -> None:
    """Type ``username`` + Tab + ``password`` into the focused field.

    Does NOT re-check focus — the orchestrator gates on :func:`is_target_focused`
    immediately before calling. Inject ``controller``/``tab_key``/``enter_key``
    to test without driving the real keyboard.
    """
    if controller is None:
        from pynput.keyboard import Controller, Key

        controller = Controller()
        tab_key = Key.tab
        enter_key = Key.enter

    delay = max(0.0, keystroke_delay_ms / 1000.0)
    username = credential.username
    password = credential.password
    try:
        for ch in username:
            controller.type(ch)
            if delay:
                time.sleep(delay)
        controller.tap(tab_key)
        if delay:
            time.sleep(delay)
        for ch in password:
            controller.type(ch)
            if delay:
                time.sleep(delay)
        if submit:
            controller.tap(enter_key)
    finally:
        # Drop references promptly (see module docstring on wiping limits).
        del username, password


def fill_if_focused(
    domain: str,
    credential: Credential,
    *,
    submit: bool = False,
    keystroke_delay_ms: int = 15,
    title: str | None = None,
) -> None:
    """Focus-check ``domain`` then fill; raise :class:`FillError` if not focused."""
    if not is_target_focused(domain, title=title):
        raise FillError(
            f"Chrome is not focused on {domain!r}; refusing to type the credential."
        )
    fill(credential, submit=submit, keystroke_delay_ms=keystroke_delay_ms)


def fill_totp(
    totp: str,
    submit: bool = True,
    *,
    keystroke_delay_ms: int = 15,
    controller=None,
    enter_key=None,
) -> None:
    """Type a TOTP code into the focused 2FA field (Enter after, by default)."""
    if not totp:
        raise FillError("no TOTP code to type.")
    if controller is None:
        from pynput.keyboard import Controller, Key

        controller = Controller()
        enter_key = Key.enter

    delay = max(0.0, keystroke_delay_ms / 1000.0)
    code = totp
    try:
        for ch in code:
            controller.type(ch)
            if delay:
                time.sleep(delay)
        if submit:
            controller.tap(enter_key)
    finally:
        del code


def fill_totp_if_focused(
    domain: str,
    totp: str,
    *,
    submit: bool = True,
    keystroke_delay_ms: int = 15,
    title: str | None = None,
) -> None:
    """Focus-check ``domain`` then type the TOTP; raise :class:`FillError` if not."""
    if not is_target_focused(domain, title=title):
        raise FillError(
            f"Chrome is not focused on {domain!r}; refusing to type the TOTP."
        )
    fill_totp(totp, submit=submit, keystroke_delay_ms=keystroke_delay_ms)
