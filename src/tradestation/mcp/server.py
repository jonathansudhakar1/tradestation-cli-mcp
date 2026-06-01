"""FastMCP server entry point for the ``ts-mcp`` console script.

See docs/06-mcp-server.md for the full design.

Usage::

    ts-mcp                                           # stdio (default, sim)
    ts-mcp --transport http --port 8765              # local HTTP
    ts-mcp --toolsets market,brokerage               # disable trading tools
    ts-mcp --profile paper                           # use ~/.tscli/profiles/paper
    ts-mcp --env live                                # override to live
    ts-mcp --read-only                               # disable all D-series tools
    ts-mcp --confirm-trades require                  # default safety mode
    ts-mcp --allow-remote --http-token secret        # expose on non-loopback
"""

from __future__ import annotations

import argparse
import ipaddress
import sys
from typing import Any

from fastmcp import FastMCP

from tradestation.mcp.toolsets import active_tool_names, resolve_toolsets

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ts-mcp",
        description=(
            "TradeStation MCP Server — exposes the TradeStation v3 API as a "
            "Model Context Protocol (MCP) server."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ts-mcp                                   # stdio, sim env\n"
            "  ts-mcp --transport http --port 8765      # local HTTP\n"
            "  ts-mcp --toolsets market,brokerage       # no trading tools\n"
            "  ts-mcp --read-only                       # disable D-series\n"
            "  ts-mcp --env live --confirm-trades off   # live, no safety gate\n"
        ),
    )

    # --- transport ---
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        metavar="MODE",
        help="Transport mode: stdio (default) or http.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        metavar="PORT",
        help="HTTP port (only used when --transport=http). Default: 8765.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help=(
            "HTTP bind address (only used when --transport=http). "
            "Default: 127.0.0.1. Non-loopback requires --allow-remote."
        ),
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        default=False,
        help=(
            "Allow non-loopback HTTP connections. "
            "Requires --http-token for security."
        ),
    )
    parser.add_argument(
        "--http-token",
        default=None,
        metavar="TOKEN",
        help=(
            "Bearer token required for HTTP connections when --allow-remote. "
            "Also readable from TS_MCP_HTTP_TOKEN env var."
        ),
    )

    # --- toolsets & safety ---
    parser.add_argument(
        "--toolsets",
        default="all",
        metavar="SETS",
        help=(
            "Comma-separated toolset allowlist. "
            "Options: market, brokerage, trading, auth, all. Default: all."
        ),
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=False,
        help="Disable all D-series (order execution) tools.",
    )
    parser.add_argument(
        "--confirm-trades",
        choices=["off", "require", "review"],
        default="require",
        metavar="MODE",
        help=(
            "Safety mode for destructive trading tools. "
            "off | require (default) | review."
        ),
    )
    parser.add_argument(
        "--max-order-notional",
        type=float,
        default=None,
        metavar="USD",
        help=(
            "Reject orders whose preview estimate exceeds this USD cap. "
            "Default: no cap."
        ),
    )
    parser.add_argument(
        "--allowed-symbols",
        default=None,
        metavar="SYMBOLS",
        help=(
            "Comma-separated symbol allowlist for trading tools. "
            "Default: all symbols allowed."
        ),
    )

    # --- credentials ---
    parser.add_argument(
        "--profile",
        default="default",
        metavar="NAME",
        help="Named credential profile under ~/.tscli/profiles/. Default: default.",
    )
    parser.add_argument(
        "--env",
        choices=["live", "sim", ""],
        default="sim",
        metavar="ENV",
        help="Override environment: live or sim. Default: sim.",
    )
    parser.add_argument(
        "--allow-env-fallback",
        action="store_true",
        default=False,
        help=(
            "Fall back to TS_CLIENT_ID / TS_CLIENT_SECRET / TS_REFRESH_TOKEN "
            "env vars when no credentials file is found."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Credential loading (builds against Phase 2 interfaces; gracefully skips)
# ---------------------------------------------------------------------------


def _load_client(
    profile: str,
    env: str,
    allow_env_fallback: bool,
) -> Any:
    """Load credentials and return a TradeStationClient.

    At this phase the real implementations raise NotImplementedError — callers
    catch that and fall back to None (tests inject a fake client directly).
    """
    from tradestation.client import TradeStationClient
    from tradestation.credentials import load_credentials, load_from_env
    from tradestation.enums import Environment
    from tradestation.errors import NoCredentialsError

    environment = Environment.SIM if env in ("", "sim") else Environment.LIVE

    try:
        if profile != "default":
            client = TradeStationClient.from_profile(profile)
        else:
            creds = load_credentials()
            import dataclasses

            if environment is not None:
                creds = dataclasses.replace(creds, environment=environment)
            client = TradeStationClient(creds)
        return client
    except NotImplementedError:
        # Phase 2 not yet implemented — return None; tests inject fake client
        return None
    except NoCredentialsError as exc:
        if allow_env_fallback:
            try:
                creds = load_from_env()
                return TradeStationClient(creds)
            except (NotImplementedError, NoCredentialsError):
                pass
        print(
            f"[ts-mcp] ERROR: {exc}\n"
            "Run `ts auth set` to configure credentials, "
            "or pass --allow-env-fallback to read from TS_* env vars.",
            file=sys.stderr,
        )
        sys.exit(3)


# ---------------------------------------------------------------------------
# Server factory (importable by tests)
# ---------------------------------------------------------------------------


def build_server(
    *,
    toolsets: str = "all",
    read_only: bool = False,
    confirm_mode: str = "require",
    max_order_notional: float | None = None,
    allowed_symbols: list[str] | None = None,
    client: Any = None,
) -> FastMCP:
    """Build and return a configured FastMCP server.

    This is the importable factory used by tests (and called by :func:`main`).

    Args:
        toolsets: Comma-separated toolset names (see :func:`resolve_toolsets`).
        read_only: If ``True``, no D-series tools are registered.
        confirm_mode: Safety mode for destructive tools (off/require/review).
        max_order_notional: Optional USD cap for order size.
        allowed_symbols: Optional symbol allowlist for trading tools.
        client: Pre-built client; if ``None``, tools are registered but will
            raise when called (useful for ``--help``-only invocations).

    Returns:
        Configured :class:`~fastmcp.FastMCP` instance.
    """
    from tradestation.mcp.tools import brokerage as brokerage_tools
    from tradestation.mcp.tools import market_data as md_tools
    from tradestation.mcp.tools import order_execution as oe_tools

    resolved = resolve_toolsets(toolsets)
    active = active_tool_names(resolved, read_only=read_only)

    mcp = FastMCP(
        name="tradestation",
        version="0.0.1",
        instructions=(
            "TradeStation v3 API — market data, brokerage, and order execution. "
            "Default environment is SIM. Destructive tools (order_place, "
            "order_replace, order_cancel, order_group_place) require a "
            "confirmation token unless --confirm-trades=off."
        ),
    )

    # --- auth_status tool ---
    if "auth_status" in active:

        @mcp.tool(name="auth_status")
        async def auth_status() -> dict[str, Any]:
            """Report current authentication status (no secrets exposed).

            Returns environment, token expiry, and available scopes.
            """
            if client is None:
                return {
                    "status": "no_client",
                    "message": "No client loaded — credentials not configured.",
                }
            try:
                from tradestation.credentials import load_credentials

                creds = load_credentials()
                return {
                    "environment": str(creds.environment),
                    "scope": creds.scope,
                    "access_token_expires_at": creds.access_token_expires_at,
                    "client_id_last4": creds.client_id[-4:] if creds.client_id else None,
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

    # --- market tools ---
    if "market" in resolved:
        md_tools.register_all(mcp, client)

    # --- brokerage tools ---
    if "brokerage" in resolved:
        brokerage_tools.register_all(mcp, client)

    # --- trading tools ---
    if "trading" in resolved and not read_only:
        oe_tools.register_all(
            mcp,
            client,
            confirm_mode=confirm_mode,
            max_order_notional=max_order_notional,
            allowed_symbols=allowed_symbols or [],
        )

    return mcp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``ts-mcp`` console script."""
    parser = _build_parser()
    args = parser.parse_args()

    # Validate toolsets early (before any expensive credential loading)
    try:
        resolved = resolve_toolsets(args.toolsets)
    except ValueError as exc:
        print(f"[ts-mcp] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # HTTP-specific validation
    if args.transport == "http":
        host = args.host
        if not args.allow_remote:
            # Reject non-loopback binds unless --allow-remote is passed
            try:
                addr = ipaddress.ip_address(host)
                if not addr.is_loopback:
                    print(
                        f"[ts-mcp] ERROR: --host {host} is not a loopback address. "
                        "Pass --allow-remote to bind to non-loopback addresses.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            except ValueError:
                # Not an IP address (e.g. "localhost") — treat as loopback
                if host not in ("localhost", "127.0.0.1", "::1"):
                    print(
                        f"[ts-mcp] ERROR: --host {host} may be non-loopback. "
                        "Pass --allow-remote to bind to non-loopback addresses.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

        if args.allow_remote and args.http_token is None:
            import os

            http_token = os.environ.get("TS_MCP_HTTP_TOKEN")
            if not http_token:
                print(
                    "[ts-mcp] ERROR: --allow-remote requires --http-token (or "
                    "TS_MCP_HTTP_TOKEN env var) to secure the endpoint.",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Parse allowed symbols
    allowed_symbols: list[str] = []
    if args.allowed_symbols:
        allowed_symbols = [s.strip() for s in args.allowed_symbols.split(",") if s.strip()]

    # Load credentials / client
    client = _load_client(args.profile, args.env, args.allow_env_fallback)

    # Print startup banner to stderr
    env_label = args.env if args.env else "sim"
    active = active_tool_names(resolved, read_only=args.read_only)
    print(
        f"[ts-mcp] Starting TradeStation MCP server\n"
        f"  transport   : {args.transport}\n"
        f"  environment : {env_label}\n"
        f"  toolsets    : {', '.join(sorted(resolved))}\n"
        f"  tools active: {len(active)}\n"
        f"  read-only   : {args.read_only}\n"
        f"  confirm-mode: {args.confirm_trades}",
        file=sys.stderr,
    )

    # Build server
    mcp = build_server(
        toolsets=args.toolsets,
        read_only=args.read_only,
        confirm_mode=args.confirm_trades,
        max_order_notional=args.max_order_notional,
        allowed_symbols=allowed_symbols,
        client=client,
    )

    # Serve
    if args.transport == "stdio":
        import asyncio

        asyncio.run(mcp.run_stdio_async(show_banner=False))
    else:
        import asyncio

        asyncio.run(
            mcp.run_http_async(
                host=args.host,
                port=args.port,
                show_banner=False,
            )
        )


if __name__ == "__main__":
    main()
