"""FastMCP server entry point for the ``ts-mcp`` console script.

See docs/06-mcp-server.md for the full design.

Usage::

    ts-mcp                                       # stdio (default)
    ts-mcp --transport http --port 8765          # local HTTP/SSE
    ts-mcp --toolsets market,brokerage           # disable trading tools
    ts-mcp --profile paper                       # use ~/.tscli/profiles/paper
    ts-mcp --env sim                             # force SIM
    ts-mcp --read-only                           # disable all D-series tools
    ts-mcp --confirm-trades require              # default safety mode

Implementation: Phase 2 (tool registrations, credential loading, etc.).
Phase 0: ``--help`` exits cleanly; boot exits 0.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="ts-mcp",
    help=(
        "[bold cyan]TradeStation MCP Server[/bold cyan]\n\n"
        "Exposes the TradeStation v3 API as a Model Context Protocol (MCP) server.\n"
        "Supports stdio (default) and local HTTP transports.\n\n"
        "See [link=https://modelcontextprotocol.io]modelcontextprotocol.io[/link] for "
        "MCP client configuration."
    ),
    rich_markup_mode="rich",
    add_completion=False,
    pretty_exceptions_enable=False,
)


@app.command()
def serve(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        help="Transport mode: [bold]stdio[/bold] (default) or [bold]http[/bold].",
        metavar="MODE",
    ),
    port: int = typer.Option(
        8765,
        "--port",
        help="HTTP port (only used when --transport=http). Default: 8765.",
    ),
    toolsets: str = typer.Option(
        "all",
        "--toolsets",
        help=(
            "Comma-separated toolset allowlist. "
            "Options: [bold]market[/bold], [bold]brokerage[/bold], "
            "[bold]trading[/bold], [bold]auth[/bold], [bold]all[/bold]. "
            "Default: all."
        ),
        metavar="SETS",
    ),
    read_only: bool = typer.Option(
        False,
        "--read-only",
        help="Disable all D-series (order execution) tools.",
    ),
    confirm_trades: str = typer.Option(
        "require",
        "--confirm-trades",
        help=(
            "Safety mode for destructive trading tools. "
            "Options: [bold]off[/bold], [bold]require[/bold] (default), "
            "[bold]review[/bold]."
        ),
        metavar="MODE",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        help="Named credential profile under ~/.tscli/profiles/. Default: default.",
        metavar="NAME",
    ),
    env: str = typer.Option(
        "",
        "--env",
        help="Override environment: [bold]live[/bold] or [bold]sim[/bold].",
        metavar="ENV",
    ),
    allow_remote: bool = typer.Option(
        False,
        "--allow-remote",
        help="Allow non-loopback HTTP connections (insecure; use with care).",
        hidden=True,
    ),
    allow_env_fallback: bool = typer.Option(
        False,
        "--allow-env-fallback",
        help=(
            "Fall back to TS_CLIENT_ID / TS_CLIENT_SECRET / TS_REFRESH_TOKEN "
            "env vars when no credentials file is found."
        ),
    ),
) -> None:
    """Start the TradeStation MCP server.

    Phase 0 stub — exits cleanly without starting any real server.
    Phase 2 will instantiate FastMCP, register tools, and serve.

    See docs/06-mcp-server.md for the full transport and safety design.
    """
    raise NotImplementedError("see docs/06-mcp-server.md §'Run'")


def main() -> None:
    """Entry point for the ``ts-mcp`` console script."""
    app()
