"""Tests for ``ts auth refresh`` — forces an access-token refresh."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer.testing

from tradestation.cli.app import app


def _fake_token_success(*args: object, **kwargs: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": "NEWTOKEN123",
        "expires_in": 1200,
        "scope": "openid offline_access MarketData ReadAccount Trade",
    }
    return resp


def _fake_token_failure(*args: object, **kwargs: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 401
    resp.text = '{"error":"invalid_grant"}'
    return resp


class TestAuthRefresh:
    def test_refresh_succeeds_with_valid_creds(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """refresh exits 0 on successful token exchange."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 0, result.output

    def test_refresh_updates_access_token_in_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """refresh must update the access_token stored in credentials."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 0

        data = json.loads(tmp_credentials_file.read_text())
        payload = data["payload"]
        assert payload["access_token"] == "NEWTOKEN123"

    def test_refresh_prints_success_message(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """refresh should print a success message with expiry info."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 0
        assert "✔" in result.output or "token" in result.output.lower()

    def test_refresh_fails_with_no_credentials(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """refresh exits 3 when no credentials file exists."""
        result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 3

    def test_refresh_fails_on_bad_token(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """refresh exits 3 when the token exchange fails."""
        with patch("httpx.post", side_effect=_fake_token_failure):
            result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 3

    def test_refresh_calls_auth_manager(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
        fake_auth_manager: object,
    ) -> None:
        """refresh should invoke the token exchange endpoint."""
        with patch("httpx.post", side_effect=_fake_token_success) as mock_post:
            result = cli_runner.invoke(app, ["auth", "refresh"])
        assert result.exit_code == 0
        mock_post.assert_called_once()
