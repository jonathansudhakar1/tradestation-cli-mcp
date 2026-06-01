"""``ts md`` command group — market data.

Subcommands (Phase 2 implementation):
    quotes   — snapshot quotes for one or more symbols (B2)
    bars     — historical bar chart data (B1)
    symbols  — symbol metadata (B3)
    lists    — symbol list management (B4-B6)
    crypto   — supported crypto pairs (B7)
    options  — option chain data (B8-B11)
    stream   — live streaming subgroup (B12-B17)

See docs/03-endpoint-inventory.md §"B. MarketData".
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="md",
    help="[bold]Market data[/bold]: quotes, bars, option chains, streaming.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
