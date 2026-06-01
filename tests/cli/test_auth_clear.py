"""Tests for ``ts auth clear`` — requires typing DELETE; --yes shortcut."""

from __future__ import annotations

from pathlib import Path

import typer.testing

from tradestation.cli.app import app


class TestAuthClear:
    def test_clear_with_yes_flag_removes_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """--yes flag skips the prompt and removes the credentials file."""
        assert tmp_credentials_file.exists()
        result = cli_runner.invoke(app, ["auth", "clear", "--yes"])
        assert result.exit_code == 0, result.output
        assert not tmp_credentials_file.exists()

    def test_clear_typing_delete_confirms(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """Typing DELETE at the prompt should remove the credentials file."""
        assert tmp_credentials_file.exists()
        result = cli_runner.invoke(app, ["auth", "clear"], input="DELETE\n")
        assert result.exit_code == 0, result.output
        assert not tmp_credentials_file.exists()

    def test_clear_wrong_input_does_not_remove_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """Typing the wrong token should NOT remove the credentials file."""
        assert tmp_credentials_file.exists()
        result = cli_runner.invoke(app, ["auth", "clear"], input="delete\n")  # lowercase
        assert result.exit_code == 0  # aborted gracefully
        assert tmp_credentials_file.exists(), "File should still exist after wrong token"

    def test_clear_empty_input_does_not_remove_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """Pressing Enter without typing should NOT remove the credentials file."""
        assert tmp_credentials_file.exists()
        result = cli_runner.invoke(app, ["auth", "clear"], input="\n")
        assert result.exit_code == 0
        assert tmp_credentials_file.exists()

    def test_clear_shows_path_in_confirmation(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """Confirmation panel should show the credentials path."""
        result = cli_runner.invoke(app, ["auth", "clear"], input="\n")
        output = result.output
        # The path (or part of it) should appear
        assert str(tmp_credentials_file).split("/")[-1] in output or ".tscli" in output

    def test_clear_no_file_exits_zero(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """clear exits 0 (gracefully) when no credentials file exists."""
        result = cli_runner.invoke(app, ["auth", "clear"])
        assert result.exit_code == 0

    def test_clear_success_prints_confirmation(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_credentials_file: Path,
    ) -> None:
        """Successful clear should print a ✔ confirmation message."""
        result = cli_runner.invoke(app, ["auth", "clear", "--yes"])
        assert result.exit_code == 0
        assert "✔" in result.output or "removed" in result.output.lower()
