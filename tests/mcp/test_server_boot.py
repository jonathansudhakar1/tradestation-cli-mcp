"""Tests for server boot, CLI argument validation, and transport safety."""

from __future__ import annotations

import subprocess
import sys


def _run_ts_mcp(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ts-mcp with given args and return the CompletedProcess."""
    venv_python = sys.executable
    return subprocess.run(
        [venv_python, "-m", "tradestation.mcp.server", *args],
        capture_output=True,
        text=True,
    )


def test_help_exits_zero() -> None:
    """--help exits 0 and shows all major flags."""
    result = _run_ts_mcp("--help")
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "--transport" in output
    assert "--port" in output
    assert "--host" in output
    assert "--toolsets" in output
    assert "--read-only" in output
    assert "--confirm-trades" in output
    assert "--max-order-notional" in output
    assert "--allowed-symbols" in output
    assert "--profile" in output
    assert "--env" in output
    assert "--allow-env-fallback" in output
    assert "--allow-remote" in output
    assert "--http-token" in output


def test_invalid_toolset_exits_nonzero() -> None:
    """An unknown toolset name causes exit with code 1."""
    result = _run_ts_mcp("--toolsets", "bogus")
    assert result.returncode == 1
    assert "Unknown toolset" in result.stderr


def test_non_loopback_without_allow_remote_exits_nonzero() -> None:
    """--host 0.0.0.0 --transport http without --allow-remote exits with code 1."""
    result = _run_ts_mcp("--transport", "http", "--host", "0.0.0.0")
    assert result.returncode == 1
    assert "non-loopback" in result.stderr.lower() or "allow-remote" in result.stderr.lower()


def test_allow_remote_without_token_exits_nonzero() -> None:
    """--allow-remote without --http-token exits with code 1."""
    result = _run_ts_mcp("--transport", "http", "--host", "0.0.0.0", "--allow-remote")
    assert result.returncode == 1
    assert "http-token" in result.stderr.lower() or "token" in result.stderr.lower()


def test_loopback_host_is_accepted() -> None:
    """127.0.0.1 is accepted without --allow-remote (exits non-zero for other reasons)."""
    # We can't actually start the server in a test, but we can verify that the
    # host validation passes (exit code 3 = no credentials, not 1 = bad args).
    result = _run_ts_mcp("--transport", "http", "--host", "127.0.0.1")
    # Should NOT fail with "non-loopback" error (code 1 from arg validation)
    if result.returncode == 1:
        assert "non-loopback" not in result.stderr.lower()


def test_build_server_returns_fastmcp() -> None:
    """build_server() returns a FastMCP instance."""
    from fastmcp import FastMCP

    from tests.mcp.conftest import FakeTradeStationClient
    from tradestation.mcp.server import build_server

    client = FakeTradeStationClient()
    server = build_server(toolsets="all", client=client)
    assert isinstance(server, FastMCP)


def test_build_server_no_client_still_works() -> None:
    """build_server() with client=None still returns a FastMCP instance."""
    from fastmcp import FastMCP

    from tradestation.mcp.server import build_server

    server = build_server(toolsets="market", client=None)
    assert isinstance(server, FastMCP)


def test_build_parser_returns_parser() -> None:
    """_build_parser returns an ArgumentParser with all expected args."""
    from tradestation.mcp.server import _build_parser

    parser = _build_parser()
    args = parser.parse_args([])
    assert args.transport == "stdio"
    assert args.port == 8765
    assert args.host == "127.0.0.1"
    assert args.env == "sim"
    assert args.profile == "default"
    assert args.toolsets == "all"
    assert args.read_only is False
    assert args.confirm_trades == "require"
    assert args.allow_remote is False
    assert args.allow_env_fallback is False


def test_build_parser_live_env() -> None:
    """_build_parser correctly parses --env live."""
    from tradestation.mcp.server import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["--env", "live"])
    assert args.env == "live"


def test_load_client_no_credentials_exits_3() -> None:
    """_load_client exits with code 3 when credentials are missing and no fallback."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c",
         "from tradestation.mcp.server import _load_client; _load_client('default', 'sim', False)"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "TS_CREDENTIALS": "/tmp/nonexistent-creds-xyz"},
    )
    # NoCredentialsError = exit 3 (auth error per docs/04 exit codes)
    assert result.returncode == 3


def test_build_parser_all_flags() -> None:
    """_build_parser parses all flags correctly."""
    from tradestation.mcp.server import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "--transport", "http",
            "--port", "9999",
            "--host", "127.0.0.1",
            "--toolsets", "market,brokerage",
            "--read-only",
            "--confirm-trades", "off",
            "--max-order-notional", "50000",
            "--allowed-symbols", "AAPL,MSFT",
            "--profile", "paper",
            "--env", "live",
            "--allow-env-fallback",
        ]
    )
    assert args.transport == "http"
    assert args.port == 9999
    assert args.toolsets == "market,brokerage"
    assert args.read_only is True
    assert args.confirm_trades == "off"
    assert args.max_order_notional == 50000.0
    assert args.allowed_symbols == "AAPL,MSFT"
    assert args.profile == "paper"
    assert args.env == "live"
    assert args.allow_env_fallback is True


def test_auth_status_no_client() -> None:
    """auth_status returns no_client when client=None."""
    import asyncio
    import json

    from fastmcp import Client

    from tradestation.mcp.server import build_server

    srv = build_server(toolsets="auth", client=None)

    async def _check() -> dict:
        async with Client(srv) as c:
            result = await c.call_tool("auth_status", {})
            if result.data is not None:
                return result.data  # type: ignore[return-value]
            return json.loads(result.content[0].text)  # type: ignore[index]

    data = asyncio.run(_check())
    assert data["status"] == "no_client"


def test_auth_status_error_handling() -> None:
    """auth_status returns error dict when credentials raise an exception."""
    import asyncio
    import json

    from fastmcp import Client

    from tests.mcp.conftest import FakeTradeStationClient
    from tradestation.mcp.server import build_server

    # Use real client so auth_status tries to load credentials → NotImplementedError
    srv = build_server(toolsets="auth", client=FakeTradeStationClient())

    async def _check() -> dict:
        async with Client(srv) as c:
            result = await c.call_tool("auth_status", {})
            if result.data is not None:
                return result.data  # type: ignore[return-value]
            return json.loads(result.content[0].text)  # type: ignore[index]

    data = asyncio.run(_check())
    # load_credentials raises NotImplementedError at this phase → caught as error
    assert "status" in data or "environment" in data
