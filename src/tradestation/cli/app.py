"""Root Typer application for the ``ts`` CLI.

Entry point: ``tradestation.cli.app:main`` (registered in pyproject.toml).

Command tree (Phase 0 scaffolding — subcommands are empty stubs)::

    ts
    ├── auth      — credential management (set, status, refresh, login, clear, …)
    ├── env       — environment switch (live / sim)
    ├── md        — market data (quotes, bars, options, streams, …)
    ├── brokerage — account data (balances, positions, orders, wallets, …)
    └── order     — order execution (place, replace, cancel, confirm, …)

See docs/01-project-structure.md §"Entry points" and docs/07-output-style.md.
"""

from __future__ import annotations

import typer

from tradestation.cli.commands import auth as auth_commands
from tradestation.cli.commands import brokerage as brokerage_commands
from tradestation.cli.commands import market_data as market_data_commands
from tradestation.cli.commands import order as order_commands

app = typer.Typer(
    name="ts",
    help=(
        "[bold cyan]TradeStation CLI[/bold cyan] — library, CLI, and MCP server for the "
        "TradeStation v3 API.\n\n"
        "Use [bold]ts auth set[/bold] to configure credentials before running other commands."
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_enable=False,
)

# ---------------------------------------------------------------------------
# Register sub-applications
# ---------------------------------------------------------------------------

app.add_typer(
    auth_commands.app,
    name="auth",
    help="[bold]Credential management[/bold]: set, status, refresh, login, clear, doctor.",
)

app.add_typer(
    market_data_commands.app,
    name="md",
    help="[bold]Market data[/bold]: quotes, bars, option chains, streaming.",
)

app.add_typer(
    brokerage_commands.app,
    name="brokerage",
    help="[bold]Account data[/bold]: balances, positions, orders, wallets, streaming.",
)

app.add_typer(
    order_commands.app,
    name="order",
    help="[bold]Order execution[/bold]: place, replace, cancel, confirm, routes.",
)


@app.command("env")
def env_cmd(
    environment: str = typer.Argument(
        ...,
        help="Target environment: [bold]live[/bold] or [bold]sim[/bold].",
        metavar="ENV",
    ),
) -> None:
    """Switch the default environment (live / sim) stored in credentials.

    Equivalent to ``ts auth set --env <ENV>`` but faster for frequent switching.
    """
    raise NotImplementedError("see docs/02-auth-and-credentials.md §'Other ts auth subcommands'")


def main() -> None:
    """Entry point for the ``ts`` console script."""
    app()
