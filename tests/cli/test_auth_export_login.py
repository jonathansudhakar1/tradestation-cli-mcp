"""Tests for ``ts auth export`` and ``ts auth login`` commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer.testing

from tradestation.cli.app import app


class TestAuthExport:
    def test_export_without_guard_flag_exits_1(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """export without --yes-i-want-secrets-on-stdout should exit 1."""
        result = cli_runner.invoke(app, ["auth", "export"])
        assert result.exit_code == 1
        assert "secret" in result.output.lower() or "stdout" in result.output.lower()

    def test_export_with_guard_flag_prints_json(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """export with guard flag should print JSON payload to stdout."""
        result = cli_runner.invoke(app, ["auth", "export", "--yes-i-want-secrets-on-stdout"])
        assert result.exit_code == 0, result.output
        # Output should be valid JSON containing credential fields
        output = result.output.strip()
        data = json.loads(output)
        assert "client_id" in data
        assert "refresh_token" in data

    def test_export_no_credentials_exits_3(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """export exits 3 when no credentials file exists."""
        result = cli_runner.invoke(app, ["auth", "export", "--yes-i-want-secrets-on-stdout"])
        assert result.exit_code == 3

    def test_export_credential_values_present(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
        fake_credentials: object,
    ) -> None:
        """Exported JSON must include the stored credential values."""
        result = cli_runner.invoke(app, ["auth", "export", "--yes-i-want-secrets-on-stdout"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        # Values from FakeCredentials
        assert data["client_id"] == "FAKECLIENTID1234567890M3xQ"
        assert data["refresh_token"] == "FAKEREFRESHTOKEN1234567890t9pK"


class TestAuthLogin:
    def test_login_not_implemented_exits_1(
        self,
        cli_runner: typer.testing.CliRunner,
    ) -> None:
        """login should print a not-yet-implemented message and exit 1."""
        result = cli_runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 1
        output = result.output.lower()
        assert (
            "not yet implemented" in output
            or "not implemented" in output
            or "ts auth set" in result.output
        )
