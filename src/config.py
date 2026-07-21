"""Minimal YAML config loader.

Reads ``config.yaml`` (gitignored) from the project root, or from a path given
by the ``CLAUDE_VAULT_CONFIG`` environment variable. Non-secret settings only —
the Telegram bot token and Bitwarden master password live in Windows Credential
Manager, never in this file. See ``config.example.yaml`` for the shape.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = PROJECT_ROOT  # backwards-compatible alias
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def config_path() -> Path:
    """Resolve the config path: ``CLAUDE_VAULT_CONFIG`` if set, else project root."""
    env = os.environ.get("CLAUDE_VAULT_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


def load(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load and parse the config file into a dict.

    Raises ``FileNotFoundError`` with a copy-paste hint if it does not exist,
    and ``ValueError`` if the file is not a YAML mapping.
    """
    p = Path(path) if path is not None else config_path()
    if not p.exists():
        raise FileNotFoundError(
            f"Config not found at {p}. "
            "Copy config.example.yaml to config.yaml and edit it."
        )
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Config at {p} must be a YAML mapping, got {type(data).__name__}."
        )
    return data
