"""Rich renderers for CLI output.

See docs/07-output-style.md for table conventions, detail panels, and streaming
output design.  All renderers are stubs in Phase 0.

Phase 2+: implement quote_table, positions_table, order_panel, error_panel, etc.
"""

from __future__ import annotations


def quote_table() -> None:
    """Render a Rich table of quote snapshots.

    See docs/07-output-style.md §"Example: ts md quotes …".
    """
    raise NotImplementedError("see docs/07-output-style.md §'Table conventions'")


def positions_table() -> None:
    """Render a Rich table of open positions.

    See docs/07-output-style.md §"Example: ts brokerage positions …".
    """
    raise NotImplementedError("see docs/07-output-style.md §'Table conventions'")


def order_panel() -> None:
    """Render a Rich detail panel for a single order.

    See docs/07-output-style.md §"Detail panel convention".
    """
    raise NotImplementedError("see docs/07-output-style.md §'Detail panel convention'")


def error_panel() -> None:
    """Render a Rich error panel with request-id, detail, and next-step hint.

    See docs/07-output-style.md §"Error rendering".
    """
    raise NotImplementedError("see docs/07-output-style.md §'Error rendering'")
