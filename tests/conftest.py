"""Shared pytest fixtures for all test suites.

See docs/05-python-library.md §"Testing posture" for test strategy.
"""

from __future__ import annotations

import pathlib
from collections.abc import Generator
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# Phase 2 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_keyring() -> Generator[MagicMock, None, None]:
    """Patch the keyring module so tests don't touch the real OS keyring.

    The fake keyring uses an in-memory dict so round-trip tests work.
    """
    _store: dict[tuple[str, str], str] = {}

    def _get_password(service: str, username: str) -> str | None:
        return _store.get((service, username))

    def _set_password(service: str, username: str, password: str) -> None:
        _store[(service, username)] = password

    mock = MagicMock()
    mock.get_password.side_effect = _get_password
    mock.set_password.side_effect = _set_password

    with patch("tradestation.credentials.keyring", mock):
        yield mock


@pytest.fixture()
def passphrase_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set TSCLI_PASSPHRASE for passphrase-based encryption tests."""
    monkeypatch.setenv("TSCLI_PASSPHRASE", "test-passphrase-secure-123")


@pytest.fixture()
def credentials_file(
    tmp_credentials_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> pathlib.Path:
    """Return a path within tmp_credentials_dir and set TS_CREDENTIALS."""
    creds_path = tmp_credentials_dir / "credentials"
    monkeypatch.setenv("TS_CREDENTIALS", str(creds_path))
    return creds_path


@pytest.fixture()
def refresh_response() -> dict[str, object]:
    """Canned successful token refresh response from TradeStation."""
    return {
        "access_token": "new-access-token-abc123",
        "id_token": "new-id-token-xyz",
        "token_type": "Bearer",
        "expires_in": 1200,
        "scope": "openid offline_access MarketData ReadAccount Trade",
    }


@pytest.fixture()
def refresh_response_with_rotation() -> dict[str, object]:
    """Canned token refresh response that includes a rotated refresh token."""
    return {
        "access_token": "new-access-token-abc123",
        "id_token": "new-id-token-xyz",
        "token_type": "Bearer",
        "expires_in": 1200,
        "scope": "openid offline_access MarketData ReadAccount Trade",
        "refresh_token": "rotated-refresh-token-99999",
    }


@pytest.fixture()
def clean_ts_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any TS_* environment variables to avoid polluting tests."""
    for var in ("TS_CLIENT_ID", "TS_CLIENT_SECRET", "TS_REFRESH_TOKEN", "TS_ENV", "TS_SCOPE"):
        monkeypatch.delenv(var, raising=False)
