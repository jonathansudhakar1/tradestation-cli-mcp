"""Phase 0 smoke tests — verify the scaffold is importable and CLIs exit cleanly.

Tests:
    test_version              — tradestation.__version__ == "0.0.1"
    test_client_is_class      — TradeStationClient is a class
    test_async_client_is_class — AsyncTradeStationClient is a class
    test_services_importable  — all three service classes are importable
    test_errors_importable    — full error hierarchy is importable
    test_enums_importable     — all enum classes are importable
    test_ts_help              — ``ts --help`` exits 0
    test_ts_mcp_help          — ``ts-mcp --help`` exits 0
"""

from __future__ import annotations

import subprocess
import sys


def test_version() -> None:
    """tradestation.__version__ must be a valid semver string and match _version."""
    import re

    import tradestation
    from tradestation import _version

    assert tradestation.__version__ == _version.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+([.-].+)?", tradestation.__version__)


def test_client_is_class() -> None:
    """TradeStationClient must be importable and must be a class."""
    from tradestation import TradeStationClient

    assert isinstance(TradeStationClient, type)


def test_async_client_is_class() -> None:
    """AsyncTradeStationClient must be importable and must be a class."""
    from tradestation import AsyncTradeStationClient

    assert isinstance(AsyncTradeStationClient, type)


def test_credentials_is_dataclass() -> None:
    """Credentials must be importable and constructable."""
    from tradestation import Credentials, Environment

    creds = Credentials(
        client_id="x",
        client_secret="y",
        refresh_token="z",
        environment=Environment.SIM,
    )
    assert creds.client_id == "x"
    assert creds.environment == Environment.SIM
    assert creds.base_url == "https://sim-api.tradestation.com/v3"


def test_services_importable() -> None:
    """All three service classes must be importable."""
    from tradestation.services import BrokerageService, MarketDataService, OrderExecutionService

    assert isinstance(MarketDataService, type)
    assert isinstance(BrokerageService, type)
    assert isinstance(OrderExecutionService, type)


def test_errors_importable() -> None:
    """Full error hierarchy must be importable."""
    from tradestation.errors import (
        ApiError,
        AuthError,
        NetworkError,
        NoCredentialsError,
        NotFoundError,
        OrderRejectedError,
        RateLimitError,
        RefreshTokenExpired,
        ServerError,
        StreamError,
        StreamHeartbeat,
        TimeoutError,
        TradeStationError,
        ValidationError,
    )

    # Verify inheritance chain
    assert issubclass(NoCredentialsError, AuthError)
    assert issubclass(RefreshTokenExpired, AuthError)
    assert issubclass(AuthError, TradeStationError)
    assert issubclass(TimeoutError, NetworkError)
    assert issubclass(NetworkError, TradeStationError)
    assert issubclass(RateLimitError, TradeStationError)
    assert issubclass(ValidationError, ApiError)
    assert issubclass(NotFoundError, ApiError)
    assert issubclass(ServerError, ApiError)
    assert issubclass(ApiError, TradeStationError)
    assert issubclass(OrderRejectedError, TradeStationError)
    assert issubclass(StreamError, TradeStationError)
    assert issubclass(StreamHeartbeat, Exception)


def test_enums_importable() -> None:
    """All enum classes must be importable and have expected members."""
    from tradestation.enums import (
        AssetType,
        BarUnit,
        Environment,
        MarketSession,
        OrderStatus,
        OrderType,
        Side,
        StreamMessageType,
        TimeInForce,
    )

    assert Environment.LIVE == "live"
    assert Environment.SIM == "sim"
    assert Side.BUY == "BUY"
    assert OrderType.MARKET == "Market"
    assert TimeInForce.DAY == "DAY"
    assert BarUnit.MINUTE == "Minute"
    assert StreamMessageType.HEARTBEAT == "Heartbeat"
    assert AssetType.STOCK == "STOCK"
    assert MarketSession.DEFAULT == "Default"
    assert OrderStatus.FILLED == "Filled"


def test_streaming_event_importable() -> None:
    """StreamEvent must be importable and constructable."""
    from tradestation.streaming import StreamEvent

    event = StreamEvent(raw={"Type": "Heartbeat"}, is_heartbeat=True)
    assert event.is_heartbeat is True
    assert event.error is None


def test_ts_help() -> None:
    """``ts --help`` must exit 0 and show the top-level command tree."""
    result = subprocess.run(
        [sys.executable, "-m", "tradestation.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"ts --help failed:\n{result.stderr}"
    output = result.stdout + result.stderr
    # Verify the main command groups are present
    assert "auth" in output
    assert "md" in output
    assert "brokerage" in output
    assert "order" in output


def test_ts_mcp_help() -> None:
    """``ts-mcp --help`` must exit 0 and show transport/toolsets/safety flags."""
    import re

    result = subprocess.run(
        [sys.executable, "-m", "tradestation.mcp", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        env={**__import__("os").environ, "NO_COLOR": "1"},
    )
    assert result.returncode == 0, f"ts-mcp --help failed:\n{result.stderr}"
    # Strip ANSI escape codes for reliable substring matching
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    output = ansi_escape.sub("", result.stdout + result.stderr)
    # Verify the key flags are described
    assert "transport" in output
    assert "toolsets" in output
    assert "read-only" in output
