"""Focus verification and keystroke-based form fill.

Confirms Chrome is focused and the window title matches the requested
domain, then types username + Tab + password. Wipes credential variables
after fill. Never touches the clipboard.
"""

from .vault import Credential


def is_target_focused(domain: str) -> bool:
    raise NotImplementedError("Phase 2")


def fill(credential: Credential, submit: bool = False) -> None:
    raise NotImplementedError("Phase 2")
