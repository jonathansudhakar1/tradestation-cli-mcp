"""Local CLI test fixtures.

Provides:
    cli_runner           — typer.testing.CliRunner
    fake_credentials     — object satisfying the Credentials public interface
    fake_auth_manager    — minimal fake AuthManager
    fake_transport       — minimal fake Transport
    fake_client          — fake TradeStationClient (no real HTTP calls)
    tmp_tscli_dir        — isolated ~/.tscli substitute (patched via TS_CREDENTIALS)
"""

from __future__ import annotations

import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from tradestation.enums import Environment

# ---------------------------------------------------------------------------
# CliRunner
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CliRunner for testing CLI commands."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Fake Credentials (satisfies the public Credentials interface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeCredentials:
    """Fake immutable credentials snapshot for testing.

    Intentionally mirrors the public :class:`~tradestation.credentials.Credentials`
    interface so CLI code works against it without importing the real class.
    """

    client_id: str = "FAKECLIENTID1234567890M3xQ"
    client_secret: str = "FAKESECRET1234567890"
    refresh_token: str = "FAKEREFRESHTOKEN1234567890t9pK"
    scope: str = "openid offline_access MarketData ReadAccount Trade"
    environment: Environment = Environment.SIM
    access_token: str | None = "FAKEACCESSTOKEN"
    access_token_expires_at: str | None = "2026-06-01T16:00:00Z"
    id_token: str | None = None

    @property
    def base_url(self) -> str:
        if self.environment == Environment.SIM:
            return "https://sim-api.tradestation.com/v3"
        return "https://api.tradestation.com/v3"


@pytest.fixture()
def fake_credentials() -> FakeCredentials:
    """Return a :class:`FakeCredentials` instance for testing."""
    return FakeCredentials()


# ---------------------------------------------------------------------------
# Fake AuthManager
# ---------------------------------------------------------------------------


class FakeAuthManager:
    """Minimal fake AuthManager for testing auth commands."""

    def __init__(self, credentials: FakeCredentials) -> None:
        self._credentials = credentials
        self.refresh_called = False
        self.refresh_should_fail = False

    def ensure_fresh(self) -> str:
        if self.refresh_should_fail:
            from tradestation.errors import RefreshTokenExpired

            raise RefreshTokenExpired("Fake refresh failure")
        return self._credentials.access_token or "FAKEACCESSTOKEN"

    def refresh(self) -> str:
        self.refresh_called = True
        if self.refresh_should_fail:
            from tradestation.errors import RefreshTokenExpired

            raise RefreshTokenExpired("Fake refresh failure")
        return self._credentials.access_token or "FAKEACCESSTOKEN"


@pytest.fixture()
def fake_auth_manager(fake_credentials: FakeCredentials) -> FakeAuthManager:
    """Return a :class:`FakeAuthManager` for testing."""
    return FakeAuthManager(fake_credentials)


# ---------------------------------------------------------------------------
# Fake Transport
# ---------------------------------------------------------------------------


class FakeTransport:
    """Minimal fake HTTP transport — records calls, returns canned responses."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> MagicMock:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        return resp

    def post(self, url: str, **kwargs: Any) -> MagicMock:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "access_token": "NEWTOKEN",
            "expires_in": 1200,
            "scope": "openid offline_access MarketData ReadAccount Trade",
        }
        return resp


@pytest.fixture()
def fake_transport() -> FakeTransport:
    """Return a :class:`FakeTransport` for testing."""
    return FakeTransport()


# ---------------------------------------------------------------------------
# Fake TradeStationClient
# ---------------------------------------------------------------------------


class FakeTradeStationClient:
    """Fake ``TradeStationClient`` for CLI tests — no real HTTP."""

    def __init__(self, credentials: FakeCredentials) -> None:
        self._credentials = credentials

    @property
    def credentials(self) -> FakeCredentials:
        return self._credentials


@pytest.fixture()
def fake_client(fake_credentials: FakeCredentials) -> FakeTradeStationClient:
    """Return a :class:`FakeTradeStationClient` for testing."""
    return FakeTradeStationClient(fake_credentials)


# ---------------------------------------------------------------------------
# Isolated ~/.tscli directory
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_tscli_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temporary directory that acts as ``~/.tscli/``.

    Sets ``TS_CREDENTIALS`` so the library reads credentials from here
    rather than the real user home directory.

    Also patches ``Path.home()`` → ``tmp_path`` to isolate state.json writes
    in env commands.
    """
    tscli = tmp_path / ".tscli"
    tscli.mkdir(mode=0o700)
    creds_file = tscli / "credentials"
    monkeypatch.setenv("TS_CREDENTIALS", str(creds_file))
    # Patch home for env.py which uses Path.home() directly
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return tscli


@pytest.fixture()
def tmp_credentials_file(tmp_tscli_dir: Path, fake_credentials: FakeCredentials) -> Path:
    """Write a plaintext credentials file and return its path."""
    creds_path = tmp_tscli_dir / "credentials"
    payload = {
        "version": 1,
        "scheme": "plaintext",
        "payload": {
            "client_id": fake_credentials.client_id,
            "client_secret": fake_credentials.client_secret,
            "refresh_token": fake_credentials.refresh_token,
            "scope": fake_credentials.scope,
            "environment": fake_credentials.environment.value,
            "access_token": fake_credentials.access_token,
            "access_token_expires_at": fake_credentials.access_token_expires_at,
            "id_token": fake_credentials.id_token,
        },
    }
    creds_path.write_text(json.dumps(payload, indent=2))
    creds_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return creds_path


# ---------------------------------------------------------------------------
# Fixture data with futures + crypto (as required by spec)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_positions() -> list[dict[str, Any]]:
    """Sample positions including equities, futures, options, and crypto."""
    return [
        {
            "Symbol": "AAPL",
            "AssetType": "EQ",
            "Quantity": "500",
            "AveragePrice": "162.10",
            "Last": "178.45",
            "MarketValue": "89225.00",
            "UnrealizedProfitLoss": "8175.00",
            "UnrealizedProfitLossPct": "10.09",
            "LongShort": "Long",
        },
        {
            "Symbol": "ES.M26",
            "AssetType": "FUT",
            "Quantity": "2",
            "AveragePrice": "5300.00",
            "Last": "5318.50",
            "MarketValue": "531850.00",
            "UnrealizedProfitLoss": "1850.00",
            "UnrealizedProfitLossPct": "0.35",
            "LongShort": "Long",
        },
        {
            "Symbol": "BTCUSD",
            "AssetType": "CRYPTO",
            "Quantity": "0.5",
            "AveragePrice": "68000.00",
            "Last": "71200.00",
            "MarketValue": "35600.00",
            "UnrealizedProfitLoss": "1600.00",
            "UnrealizedProfitLossPct": "4.71",
            "LongShort": "Long",
        },
    ]


@pytest.fixture()
def sample_quotes() -> list[dict[str, Any]]:
    """Sample quotes including equity, futures, and crypto."""
    return [
        {
            "Symbol": "AAPL",
            "Last": "178.45",
            "NetChange": "1.27",
            "NetChangePct": "0.72",
            "Bid": "178.44",
            "BidSize": "400",
            "Ask": "178.46",
            "AskSize": "300",
            "Open": "177.10",
            "High": "179.02",
            "Low": "176.81",
            "Volume": "42113800",
            "MarketFlags": {"IsHalted": False},
        },
        {
            "Symbol": "ES.M26",
            "Last": "5318.50",
            "NetChange": "18.50",
            "NetChangePct": "0.35",
            "Bid": "5318.25",
            "BidSize": "10",
            "Ask": "5318.75",
            "AskSize": "8",
            "Open": "5300.00",
            "High": "5325.00",
            "Low": "5295.00",
            "Volume": "125000",
            "MarketFlags": {"IsHalted": False},
        },
        {
            "Symbol": "BTCUSD",
            "Last": "71200.00",
            "NetChange": "1200.00",
            "NetChangePct": "1.71",
            "Bid": "71195.00",
            "BidSize": "1",
            "Ask": "71205.00",
            "AskSize": "1",
            "Open": "70000.00",
            "High": "71500.00",
            "Low": "69800.00",
            "Volume": "5000",
            "MarketFlags": {"IsHalted": False},
        },
    ]
