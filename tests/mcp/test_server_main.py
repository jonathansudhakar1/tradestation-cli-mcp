"""Tests for ts-mcp ``main()`` argument handling and startup paths."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tradestation.mcp import server as srv


def _run_main(argv: list[str]) -> None:
    with patch("sys.argv", ["ts-mcp", *argv]):
        srv.main()


class TestMainValidation:
    def test_invalid_toolset_exits_1(self) -> None:
        with pytest.raises(SystemExit) as ei:
            _run_main(["--toolsets", "bogus"])
        assert ei.value.code == 1

    def test_http_non_loopback_rejected(self) -> None:
        with pytest.raises(SystemExit) as ei:
            _run_main(["--transport", "http", "--host", "8.8.8.8"])
        assert ei.value.code == 1

    def test_http_hostname_non_loopback_rejected(self) -> None:
        with pytest.raises(SystemExit) as ei:
            _run_main(["--transport", "http", "--host", "example.com"])
        assert ei.value.code == 1

    def test_http_allow_remote_without_token_rejected(self, monkeypatch: Any) -> None:
        monkeypatch.delenv("TS_MCP_HTTP_TOKEN", raising=False)
        with pytest.raises(SystemExit) as ei:
            _run_main(["--transport", "http", "--host", "8.8.8.8", "--allow-remote"])
        assert ei.value.code == 1


class TestMainStartup:
    def test_stdio_startup_builds_and_runs(self) -> None:
        """Happy path: stdio transport builds the server and runs it."""
        fake_server = MagicMock()

        async def _noop(**_kwargs: Any) -> None:
            return None

        fake_server.run_stdio_async = _noop

        with (
            patch.object(srv, "_load_client", return_value=MagicMock()),
            patch.object(srv, "build_server", return_value=fake_server) as build,
        ):
            _run_main(["--toolsets", "market"])

        build.assert_called_once()
        assert build.call_args.kwargs["toolsets"] == "market"

    def test_loopback_http_ok(self) -> None:
        fake_server = MagicMock()

        async def _noop(**_kwargs: Any) -> None:
            return None

        fake_server.run_http_async = _noop

        with (
            patch.object(srv, "_load_client", return_value=MagicMock()),
            patch.object(srv, "build_server", return_value=fake_server),
        ):
            # 127.0.0.1 is loopback — should not exit, should run http.
            _run_main(["--transport", "http", "--host", "127.0.0.1", "--port", "8999"])


class TestLoadClient:
    def test_no_credentials_exits_3(self, monkeypatch: Any) -> None:
        from tradestation.errors import NoCredentialsError

        def _boom() -> Any:
            raise NoCredentialsError("no creds")

        monkeypatch.setattr("tradestation.credentials.load_credentials", _boom)
        with pytest.raises(SystemExit) as ei:
            srv._load_client("default", "sim", allow_env_fallback=False)
        assert ei.value.code == 3
