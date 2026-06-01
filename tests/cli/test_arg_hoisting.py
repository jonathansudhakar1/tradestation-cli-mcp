"""Tests for global-option hoisting (`ts <cmd> ... --output json` support)."""

from __future__ import annotations

from tradestation.cli.app import _hoist_global_options


def test_trailing_value_option_hoisted() -> None:
    out = _hoist_global_options(["brokerage", "accounts", "--output", "json"])
    assert out == ["--output", "json", "brokerage", "accounts"]


def test_trailing_short_output_hoisted() -> None:
    out = _hoist_global_options(["md", "quotes", "AAPL", "-o", "csv"])
    assert out == ["-o", "csv", "md", "quotes", "AAPL"]


def test_equals_form_hoisted() -> None:
    out = _hoist_global_options(["brokerage", "accounts", "--output=json"])
    assert out == ["--output=json", "brokerage", "accounts"]


def test_flag_hoisted() -> None:
    out = _hoist_global_options(["brokerage", "positions", "ACC1", "--sim"])
    assert out == ["--sim", "brokerage", "positions", "ACC1"]


def test_already_leading_is_stable() -> None:
    out = _hoist_global_options(["--output", "json", "brokerage", "accounts"])
    assert out == ["--output", "json", "brokerage", "accounts"]


def test_command_options_untouched() -> None:
    # --max and -f are command options, not globals — order preserved.
    out = _hoist_global_options(["md", "quotes", "AAPL", "--max", "3", "-o", "jsonl"])
    assert out == ["-o", "jsonl", "md", "quotes", "AAPL", "--max", "3"]


def test_double_dash_terminates() -> None:
    out = _hoist_global_options(["order", "place", "--", "--output", "json"])
    assert out == ["order", "place", "--", "--output", "json"]


def test_verbose_count_flag() -> None:
    out = _hoist_global_options(["brokerage", "accounts", "-v"])
    assert out == ["-v", "brokerage", "accounts"]
