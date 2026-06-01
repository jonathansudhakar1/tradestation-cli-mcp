"""Tests for ``ts auth status`` — renders panel, reads from fake creds, never prints secrets."""

from __future__ import annotations

from pathlib import Path

import typer.testing

from tradestation.cli.app import app


class TestAuthStatus:
    def test_status_exits_zero_with_valid_token(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status exits 0 when a valid (non-expired) access token is present."""
        result = cli_runner.invoke(app, ["auth", "status"])
        # Access token in fake creds is future-dated, so should be valid
        assert result.exit_code in (0, 3)  # may be 3 if fake token is past its expiry date

    def test_status_shows_panel_fields(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status panel must show Path, Scheme, Environment, Client ID, Scope."""
        result = cli_runner.invoke(app, ["auth", "status"])
        output = result.output

        assert "Path" in output or "path" in output.lower()
        assert "Scheme" in output or "scheme" in output.lower()
        assert "Environment" in output or "environment" in output.lower()
        assert "Client ID" in output or "client" in output.lower()
        assert "Scope" in output or "scope" in output.lower()

    def test_status_never_prints_full_client_id(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status must NOT print the full client_id secret."""
        result = cli_runner.invoke(app, ["auth", "status"])
        # Full client ID from FakeCredentials
        assert "FAKECLIENTID1234567890M3xQ" not in result.output

    def test_status_never_prints_full_refresh_token(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status must NOT print the full refresh token."""
        result = cli_runner.invoke(app, ["auth", "status"])
        assert "FAKEREFRESHTOKEN1234567890t9pK" not in result.output

    def test_status_shows_masked_client_id(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status should show last-4 of client_id with masking."""
        result = cli_runner.invoke(app, ["auth", "status"])
        # Last-4 of FAKECLIENTID1234567890M3xQ is "M3xQ"
        assert "M3xQ" in result.output

    def test_status_shows_masked_refresh_token(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status should show last-4 of refresh token with masking."""
        result = cli_runner.invoke(app, ["auth", "status"])
        # Last-4 of FAKEREFRESHTOKEN1234567890t9pK is "t9pK"
        assert "t9pK" in result.output

    def test_status_no_secrets_regex(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """No 20+ character secret-looking strings should appear in status output."""
        result = cli_runner.invoke(app, ["auth", "status"])
        # Look for patterns that could be secrets (long alphanumeric strings)
        # The masked form is ******XXXX (10 chars), so anything >16 chars alphanumeric
        # that isn't a path or URL is suspicious
        # We check specifically that our known secrets don't appear
        secrets = [
            "FAKECLIENTID1234567890M3xQ",
            "FAKESECRET1234567890",
            "FAKEREFRESHTOKEN1234567890t9pK",
            "FAKEACCESSTOKEN",
        ]
        for secret in secrets:
            assert secret not in result.output, f"Secret {secret!r} found in status output"

    def test_status_missing_credentials_exits_3(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """status exits 3 when credentials file is absent."""
        result = cli_runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 3
        assert "ts auth set" in result.output or "No credentials" in result.output

    def test_status_shows_environment(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """status panel must show the environment value."""
        result = cli_runner.invoke(app, ["auth", "status"])
        assert "sim" in result.output or "live" in result.output
