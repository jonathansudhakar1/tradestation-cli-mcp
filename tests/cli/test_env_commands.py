"""Tests for ``ts env show|live|sim`` — environment switching commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer.testing

from tradestation.cli.app import app


class TestEnvShow:
    def test_show_reports_sim_by_default(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """show should report 'sim' when no state.json exists."""
        result = cli_runner.invoke(app, ["env", "show"])
        assert result.exit_code == 0, result.output
        assert "sim" in result.output.lower()

    def test_show_reads_existing_state(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """show should read the environment from state.json."""
        state_path = tmp_tscli_dir / "state.json"
        state_path.write_text(json.dumps({"environment": "live"}))
        result = cli_runner.invoke(app, ["env", "show"])
        assert result.exit_code == 0
        assert "live" in result.output.lower()

    def test_show_live_environment_has_warning(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """show should display a warning when environment is live."""
        state_path = tmp_tscli_dir / "state.json"
        state_path.write_text(json.dumps({"environment": "live"}))
        result = cli_runner.invoke(app, ["env", "show"])
        assert result.exit_code == 0
        # Should have some warning indicator
        assert (
            "⚠" in result.output
            or "warning" in result.output.lower()
            or "real money" in result.output.lower()
        )


class TestEnvSim:
    def test_sim_switches_environment(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """sim should write 'sim' to state.json."""
        result = cli_runner.invoke(app, ["env", "sim"])
        assert result.exit_code == 0, result.output
        state_path = tmp_tscli_dir / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["environment"] == "sim"

    def test_sim_prints_confirmation(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """sim should print a confirmation message."""
        result = cli_runner.invoke(app, ["env", "sim"])
        assert result.exit_code == 0
        assert "sim" in result.output.lower()
        assert "✔" in result.output

    def test_sim_creates_state_file(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """sim should create state.json if it doesn't exist."""
        state_path = tmp_tscli_dir / "state.json"
        assert not state_path.exists()
        result = cli_runner.invoke(app, ["env", "sim"])
        assert result.exit_code == 0
        assert state_path.exists()


class TestEnvLive:
    def test_live_with_yes_flag_switches_environment(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """live --yes should switch to live without interactive confirmation."""
        result = cli_runner.invoke(app, ["env", "live", "--yes"])
        assert result.exit_code == 0, result.output
        state_path = tmp_tscli_dir / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["environment"] == "live"

    def test_live_confirmation_prompt_shown(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """live without --yes should show a warning about real money."""
        result = cli_runner.invoke(app, ["env", "live"], input="n\n")
        assert result.exit_code == 0
        output = result.output
        assert "WARNING" in output or "⚠" in output or "real money" in output.lower()

    def test_live_confirmation_aborted_does_not_switch(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Declining the confirmation should NOT change the environment."""
        result = cli_runner.invoke(app, ["env", "live"], input="n\n")
        assert result.exit_code == 0
        state_path = tmp_tscli_dir / "state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            assert state.get("environment") != "live"

    def test_live_confirmation_accepted_switches(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """Accepting the confirmation should switch to live."""
        result = cli_runner.invoke(app, ["env", "live"], input="y\n")
        assert result.exit_code == 0
        state_path = tmp_tscli_dir / "state.json"
        state = json.loads(state_path.read_text())
        assert state["environment"] == "live"

    def test_live_prints_warning_after_switch(
        self,
        cli_runner: typer.testing.CliRunner,
        tmp_tscli_dir: Path,
    ) -> None:
        """After switching to live, output should include a warning."""
        result = cli_runner.invoke(app, ["env", "live", "--yes"])
        assert result.exit_code == 0
        assert "live" in result.output.lower()
        assert "⚠" in result.output or "warning" in result.output.lower()
