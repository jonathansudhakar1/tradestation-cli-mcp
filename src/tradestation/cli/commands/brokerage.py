"""``ts brokerage`` command group — account data.

Subcommands (Phase 2 implementation):
    accounts  — list accounts (C1)
    balances  — real-time balances (C2)
    bod       — beginning-of-day balances (C3)
    positions — open positions (C4)
    orders    — today's orders (C5-C8)
    wallets   — crypto wallets (C9)
    stream    — live streaming subgroup (C10-C13)

See docs/03-endpoint-inventory.md §"C. Brokerage".
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="brokerage",
    help="[bold]Account data[/bold]: balances, positions, orders, wallets, streaming.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
