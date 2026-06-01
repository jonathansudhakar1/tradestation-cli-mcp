"""Rich theme for the ``ts`` CLI.

Named styles applied semantically — never raw hex in command code.
See docs/07-output-style.md §"Color palette" for the full design.

Usage::

    from tradestation.cli.theme import TS_THEME
    from rich.console import Console

    console = Console(theme=TS_THEME)
"""

from __future__ import annotations

from rich.theme import Theme

#: The canonical Rich theme for all ``ts`` CLI output.
TS_THEME = Theme(
    {
        "ts.header": "bold cyan",
        "ts.label": "dim white",
        "ts.value": "white",
        "ts.mono": "bright_black",
        "ts.symbol": "bold yellow",
        "ts.price": "white",
        "ts.up": "bold green",
        "ts.down": "bold red",
        "ts.flat": "dim white",
        "ts.warn": "bold yellow",
        "ts.danger": "bold red",
        "ts.ok": "bold green",
        "ts.bad": "bold red",
        "ts.muted": "dim",
        "ts.kbd": "reverse",
        "ts.heartbeat": "bright_black",
        "ts.json.key": "cyan",
        "ts.json.string": "green",
        "ts.json.number": "magenta",
    }
)
