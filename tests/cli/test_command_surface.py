"""Guard the documented CLI command surface.

Every command promised in docs/04-cli-design.md must be registered and
discoverable via ``--help``. This catches "documented but not wired" gaps
(e.g. B9 strikes, B11 risk-reward, B14/B15 depth streams, B16/B17 option
streams, C11 stream-order-by-id) that were missing from the CLI.
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from tradestation.cli.app import app


def _help(*args: str) -> str:
    result = CliRunner().invoke(app, [*args, "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    return re.sub(r"\x1b\[[0-9;]*m", "", result.output)


def test_md_options_subcommands_present() -> None:
    out = _help("md", "options")
    for cmd in ("expirations", "strikes", "spread-types", "chain", "risk-reward"):
        assert cmd in out, f"missing `ts md options {cmd}`"


def test_md_stream_subcommands_present() -> None:
    out = _help("md", "stream")
    for cmd in ("quotes", "bars", "depth-quotes", "depth-agg", "option-chain", "option-quotes"):
        assert cmd in out, f"missing `ts md stream {cmd}`"


def test_brokerage_stream_subcommands_present() -> None:
    out = _help("brokerage", "stream")
    for cmd in ("orders", "order", "positions", "wallets"):
        assert cmd in out, f"missing `ts brokerage stream {cmd}`"


def test_brokerage_subcommands_present() -> None:
    out = _help("brokerage")
    for cmd in (
        "accounts",
        "balances",
        "bod",
        "positions",
        "orders",
        "order",
        "historical",
        "wallets",
    ):
        assert cmd in out, f"missing `ts brokerage {cmd}`"


def test_order_subcommands_present() -> None:
    out = _help("order")
    for cmd in ("confirm", "place", "replace", "cancel", "routes", "triggers", "group"):
        assert cmd in out, f"missing `ts order {cmd}`"


def test_order_group_subcommands_present() -> None:
    out = _help("order", "group")
    for cmd in ("confirm", "place"):
        assert cmd in out, f"missing `ts order group {cmd}`"
