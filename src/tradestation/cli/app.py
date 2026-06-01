"""Root Typer application for the ``ts`` CLI.

Entry point: ``tradestation.cli.app:main`` (registered in pyproject.toml).

Command tree::

    ts
    ├── auth      — credential management (set, status, refresh, login, clear, export, doctor)
    ├── env       — environment switch (show, live, sim)
    ├── md        — market data (quotes, bars, options, streams, …)       [placeholder]
    ├── brokerage — account data (balances, positions, orders, wallets, …) [placeholder]
    └── order     — order execution (place, replace, cancel, confirm, …)  [placeholder]

See docs/01-project-structure.md §"Entry points" and docs/07-output-style.md.
"""

from __future__ import annotations

from typing import Annotated

import typer

from tradestation._version import __version__
from tradestation.cli.commands import auth as auth_commands
from tradestation.cli.commands import brokerage as brokerage_commands
from tradestation.cli.commands import env as env_commands
from tradestation.cli.commands import market_data as market_data_commands
from tradestation.cli.commands import order as order_commands

app = typer.Typer(
    name="ts",
    help=(
        "[bold cyan]TradeStation CLI[/bold cyan] — library, CLI, and MCP server for the "
        "TradeStation v3 API.\n\n"
        "Use [bold]ts auth set[/bold] to configure credentials before running other commands.\n\n"
        "[dim]Default environment: [bold]sim[/bold] (paper trading — safe by default).[/dim]"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)

# ---------------------------------------------------------------------------
# Register sub-applications
# ---------------------------------------------------------------------------

app.add_typer(
    auth_commands.app,
    name="auth",
    help="[bold]Credential management[/bold]: set, status, refresh, login, clear, export, doctor.",
)

app.add_typer(
    env_commands.app,
    name="env",
    help="[bold]Environment switching[/bold]: show, live, sim.",
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


# ---------------------------------------------------------------------------
# Global --version callback
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tscli {__version__}  (tradestation {__version__})")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _global_options(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
            expose_value=False,
        ),
    ] = None,
    env: Annotated[
        str | None,
        typer.Option(
            "--env",
            help="Override environment for this invocation: [bold]live[/bold] or [bold]sim[/bold].",
            metavar="ENV",
            envvar="TS_ENV",
        ),
    ] = None,
    sim: Annotated[
        bool,
        typer.Option(
            "--sim",
            help="Shorthand for --env sim.",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="Use ~/.tscli/profiles/NAME instead of the default credentials file.",
            metavar="NAME",
            envvar="TS_PROFILE",
        ),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Rendering mode: [bold]table[/bold]|json|jsonl|csv|tsv|yaml. "
            "Default: table (TTY) / jsonl (pipe).",
            metavar="FORMAT",
        ),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option(
            "--no-color",
            help="Force plain ANSI-free output. Also honors NO_COLOR=1.",
            envvar="NO_COLOR",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress non-data output (banners, progress).",
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Verbose logging (-v URLs+status, -vv +redacted bodies).",
        ),
    ] = 0,
    unsafe_log_secrets: Annotated[
        bool,
        typer.Option(
            "--unsafe-log-secrets",
            help="Disable redaction (dev only; emits red warning banner).",
            hidden=True,
        ),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="Per-request timeout in seconds (default 30).",
        ),
    ] = 30.0,
    retries: Annotated[
        int,
        typer.Option(
            "--retries",
            help="Retry budget for transient failures (default 3).",
        ),
    ] = 3,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompts.",
        ),
    ] = False,
) -> None:
    """[bold cyan]TradeStation CLI[/bold cyan] — TradeStation v3 API client.

    Default environment: [bold]sim[/bold] (paper trading).
    Use [bold]--env live[/bold] to operate on real accounts.
    """
    # Resolve environment: --sim > --env > default SIM
    from tradestation.cli.ctx import CLIContext, OutputMode
    from tradestation.enums import Environment

    if sim:
        resolved_env = Environment.SIM
    elif env is not None:
        try:
            resolved_env = Environment(env.lower())
        except ValueError:
            from rich.console import Console

            Console().print(
                f"[bold red]Error:[/bold red] Unknown environment {env!r}. Use 'live' or 'sim'."
            )
            raise typer.Exit(code=2) from None
    else:
        resolved_env = Environment.SIM

    # Resolve output mode
    resolved_output: OutputMode | None = None
    if output is not None:
        try:
            resolved_output = OutputMode(output.lower())
        except ValueError:
            from rich.console import Console

            Console().print(
                f"[bold red]Error:[/bold red] Unknown output format {output!r}. "
                "Use: table, json, jsonl, csv, tsv, yaml."
            )
            raise typer.Exit(code=2) from None

    cli_ctx = CLIContext.create(
        environment=resolved_env,
        profile=profile,
        output=resolved_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        unsafe_log_secrets=unsafe_log_secrets,
        timeout=timeout,
        retries=retries,
        yes=yes,
    )
    cli_ctx.attach(ctx)

    if unsafe_log_secrets:
        cli_ctx.console.print(
            "[ts.danger]  ⚠  --unsafe-log-secrets is active — "
            "secrets may appear in log output[/ts.danger]"
        )


def main() -> None:
    """Entry point for the ``ts`` console script."""
    app()
