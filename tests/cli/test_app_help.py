"""Snapshot test for ``ts --help`` output — verifies full command tree is visible."""

from __future__ import annotations

import typer.testing

from tradestation.cli.app import app


def test_ts_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts --help`` should exit 0."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output


def test_ts_help_shows_all_subcommands(cli_runner: typer.testing.CliRunner) -> None:
    """``ts --help`` must mention all top-level subcommands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0

    output = result.output
    for cmd in ("auth", "env", "md", "brokerage", "order"):
        assert cmd in output, f"Subcommand {cmd!r} not found in help output"


def test_ts_help_mentions_sim_default(cli_runner: typer.testing.CliRunner) -> None:
    """Help text must mention that the default environment is sim."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sim" in result.output.lower()


def test_ts_version(cli_runner: typer.testing.CliRunner) -> None:
    """``ts --version`` should print version and exit 0."""
    result = cli_runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tscli" in result.output.lower() or "0.0.1" in result.output


def test_auth_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts auth --help`` should exit 0 and list subcommands."""
    result = cli_runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0
    for cmd in ("set", "status", "refresh", "login", "clear", "export", "doctor"):
        assert cmd in result.output, f"auth subcommand {cmd!r} not in help"


def test_env_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts env --help`` should exit 0 and list subcommands."""
    result = cli_runner.invoke(app, ["env", "--help"])
    assert result.exit_code == 0
    for cmd in ("show", "live", "sim"):
        assert cmd in result.output, f"env subcommand {cmd!r} not in help"


def test_md_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts md --help`` should exit 0."""
    result = cli_runner.invoke(app, ["md", "--help"])
    assert result.exit_code == 0


def test_brokerage_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts brokerage --help`` should exit 0."""
    result = cli_runner.invoke(app, ["brokerage", "--help"])
    assert result.exit_code == 0


def test_order_help_exits_zero(cli_runner: typer.testing.CliRunner) -> None:
    """``ts order --help`` should exit 0."""
    result = cli_runner.invoke(app, ["order", "--help"])
    assert result.exit_code == 0


def test_ts_bad_env_flag(cli_runner: typer.testing.CliRunner) -> None:
    """``ts --env badvalue auth --help`` should fail with exit code 2."""
    result = cli_runner.invoke(app, ["--env", "badvalue", "auth", "--help"])
    assert result.exit_code == 2


def test_ts_bad_output_flag(cli_runner: typer.testing.CliRunner) -> None:
    """``ts --output badformat auth --help`` should fail with exit code 2."""
    result = cli_runner.invoke(app, ["--output", "badformat", "auth", "--help"])
    assert result.exit_code == 2
