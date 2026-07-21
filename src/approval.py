"""Phone-tap approval via Telegram inline buttons.

Sends a message with Approve / Deny buttons, blocks until callback or timeout,
returns True (approved) / False (denied or timed out). Bot token loaded from
Windows Credential Manager, never from disk.
"""


def request_approval(domain: str, timeout_seconds: int = 60) -> bool:
    raise NotImplementedError("Phase 1")
