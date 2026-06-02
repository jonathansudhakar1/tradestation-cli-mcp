"""Rich theme for the ``ts`` CLI.

Named styles applied semantically — never raw hex in command code.
See docs/07-output-style.md §"Color palette" for the full design.

User overrides are loaded from ``~/.tscli/theme.toml`` if present.

Usage::

    from tradestation.cli.theme import get_theme
    from rich.console import Console

    console = Console(theme=get_theme())
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from rich.theme import Theme

#: Default style definitions — every ``ts.*`` name from docs/07.
_DEFAULT_STYLES: dict[str, str] = {
    # Section headings, panel borders
    "ts.header": "bold cyan",
    # Field labels in detail panels
    "ts.label": "dim white",
    # Field values
    "ts.value": "white",
    # Inline code, account IDs, order IDs
    "ts.mono": "bright_black",
    # Ticker symbols
    "ts.symbol": "bold yellow",
    # Numeric prices
    "ts.price": "white",
    # Positive Δ, Δ%, fill
    "ts.up": "bold green",
    # Negative Δ, Δ%, rejected
    "ts.down": "bold red",
    # Zero Δ
    "ts.flat": "dim white",
    # Warnings (preview banners, halted symbol)
    "ts.warn": "bold yellow",
    # Destructive prompts, --unsafe-log-secrets banner
    "ts.danger": "bold red",
    # "✔" markers, healthy auth
    "ts.ok": "bold green",
    # "✖" markers, expired auth
    "ts.bad": "bold red",
    # Timestamps, secondary data
    "ts.muted": "dim",
    # Keys to press in confirmation prompts
    "ts.kbd": "reverse",
    # Stream heartbeat lines (suppressed unless --show-heartbeats)
    "ts.heartbeat": "bright_black",
    # JSON output keys (when --output json)
    "ts.json.key": "cyan",
    # JSON strings
    "ts.json.string": "green",
    # JSON numbers
    "ts.json.number": "magenta",
}

#: The canonical Rich theme for all ``ts`` CLI output (no user overrides).
TS_THEME = Theme(_DEFAULT_STYLES)

#: Path to the optional user theme override file.
_USER_THEME_PATH = Path.home() / ".tscli" / "theme.toml"


def _load_user_overrides(path: Path = _USER_THEME_PATH) -> dict[str, str]:
    """Load style overrides from ``path`` if it exists.

    Returns an empty dict when the file is absent or malformed.
    Only the ``[styles]`` table is consumed; unknown sections are ignored.
    """
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            data: Any = tomllib.load(fh)
        styles = data.get("styles", {})
        if not isinstance(styles, dict):
            return {}
        return {k: str(v) for k, v in styles.items() if isinstance(v, str)}
    except Exception:
        return {}


def get_theme(*, override_path: Path | None = None) -> Theme:
    """Return a Rich :class:`~rich.theme.Theme` with optional user overrides.

    Args:
        override_path: Path to a ``theme.toml`` file (default: ``~/.tscli/theme.toml``).
            Pass an explicit path in tests to avoid touching the real user dir.

    Returns:
        A :class:`~rich.theme.Theme` merging defaults with any user overrides.
    """
    path = override_path if override_path is not None else _USER_THEME_PATH
    overrides = _load_user_overrides(path)
    merged = {**_DEFAULT_STYLES, **overrides}
    return Theme(merged)
