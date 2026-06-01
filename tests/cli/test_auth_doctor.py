"""Tests for ``ts auth doctor`` — diagnostics command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import typer.testing

from tradestation.cli.app import app


def _fake_token_success(*args: object, **kwargs: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": "NEWTOKEN",
        "expires_in": 1200,
        "scope": "openid offline_access MarketData ReadAccount Trade",
    }
    return resp


class TestAuthDoctor:
    def test_doctor_runs_without_error(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor should exit 0 and produce diagnostic output."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        assert result.exit_code == 0, result.output

    def test_doctor_checks_file_existence(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor output should mention the credentials file."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        output = result.output
        assert "credentials" in output.lower() or "file" in output.lower()

    def test_doctor_checks_file_permissions(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor should report file permissions."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        output = result.output
        # Should mention permissions in some form
        assert "0o600" in output or "600" in output or "Permissions" in output

    def test_doctor_checks_keyring(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor should report keyring backend availability."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        output = result.output
        # Should mention keyring in some form
        assert "keyring" in output.lower() or "Keyring" in output

    def test_doctor_reports_scopes(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor should list scopes returned by token exchange."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        output = result.output
        # Should mention scopes
        assert "scope" in output.lower() or "MarketData" in output or "openid" in output

    def test_doctor_no_credentials_still_runs(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """doctor without credentials should still run (exit 0) with diagnostic info."""
        result = cli_runner.invoke(app, ["auth", "doctor"])
        assert result.exit_code == 0
        assert (
            "Not found" in result.output
            or "No credentials" in result.output
            or "✖" in result.output
        )

    def test_doctor_reports_token_exchange_success(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """doctor should confirm token exchange succeeded."""
        with patch("httpx.post", side_effect=_fake_token_success):
            result = cli_runner.invoke(app, ["auth", "doctor"])
        output = result.output
        assert "✔" in output or "succeeded" in output.lower() or "Exchange" in output
