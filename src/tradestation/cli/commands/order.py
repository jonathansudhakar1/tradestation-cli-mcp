"""``ts order`` command group — order execution.

Subcommands (Phase 2 implementation):
    confirm       — preview order without submitting (D1)
    place         — submit a single order (D2)
    replace       — modify a working order (D3)
    cancel        — cancel a working order (D4)
    group-confirm — preview a grouped order (D5)
    group-place   — submit a grouped order (D6)
    triggers      — list activation triggers (D7)
    routes        — list execution routes (D8)

See docs/03-endpoint-inventory.md §"D. OrderExecution".
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="order",
    help="[bold]Order execution[/bold]: place, replace, cancel, confirm, routes.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
