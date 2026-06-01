"""Shared pytest fixtures for all test suites.

See docs/05-python-library.md §"Testing posture" for test strategy.
"""

from __future__ import annotations

import pathlib

import pytest

from tradestation.credentials import Credentials
from tradestation.enums import Environment


@pytest.fixture()
def tmp_credentials_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a temporary directory that mimics ``~/.tscli/``.

    Sets the ``TS_CREDENTIALS`` environment variable so the library reads
    from this path instead of the real user directory.
    """
    creds_dir = tmp_path / ".tscli"
    creds_dir.mkdir(mode=0o700, parents=True)
    return creds_dir


@pytest.fixture()
def sample_credentials() -> Credentials:
    """Return a synthetic :class:`~tradestation.credentials.Credentials` for testing.

    Uses fake tokens; never makes real HTTP calls.
    """
    return Credentials(
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token",
        scope="openid offline_access MarketData ReadAccount Trade",
        environment=Environment.SIM,
    )


@pytest.fixture()
def sample_quote_payload() -> dict[str, object]:
    """Return a synthetic quote API response payload."""
    return {
        "Quotes": [
            {
                "Symbol": "AAPL",
                "Last": "178.45",
                "Bid": "178.44",
                "BidSize": "400",
                "Ask": "178.46",
                "AskSize": "300",
                "Open": "177.10",
                "High": "179.02",
                "Low": "176.81",
                "Volume": "42113800",
                "DailyOpenInterest": "0",
                "NetChange": "1.27",
                "NetChangePct": "0.72",
                "TradeTime": "2026-06-01T15:32:07Z",
                "MarketFlags": {"IsDelayed": False, "IsHalted": False},
            }
        ]
    }
