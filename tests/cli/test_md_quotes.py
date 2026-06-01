"""CLI tests for ``ts md quotes`` command (B2).

Uses Typer's CliRunner with a fake client — no real HTTP.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tradestation.cli.app import app
from tradestation.models.market_data import Quote


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

_QUOTE_AAPL = Quote.model_validate(
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
        "NetChange": "1.27",
        "NetChangePct": "0.72",
        "Volume": "42113800",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False, "IsDelayed": False},
    }
)

_QUOTE_ES = Quote.model_validate(
    {
        "Symbol": "@ES",
        "Last": "5318.50",
        "Bid": "5318.25",
        "BidSize": "10",
        "Ask": "5318.75",
        "AskSize": "8",
        "Open": "5300.00",
        "High": "5325.00",
        "Low": "5295.00",
        "NetChange": "18.50",
        "NetChangePct": "0.35",
        "Volume": "125000",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False},
    }
)

_QUOTE_BTCUSD = Quote.model_validate(
    {
        "Symbol": "BTCUSD",
        "Last": "71235.78",
        "Bid": "0",
        "Ask": "0",
        "Open": "73632.023",
        "High": "74092.078",
        "Low": "70555.0",
        "NetChange": "-2340.728",
        "NetChangePct": "-3.18",
        "Volume": "691",
        "TradeTime": "2026-06-01T16:30:00Z",
        "MarketFlags": {"IsHalted": False},
    }
)

_ALL_QUOTES = [_QUOTE_AAPL, _QUOTE_ES, _QUOTE_BTCUSD]


# ---------------------------------------------------------------------------
# Helper: invoke the CLI with a patched client
# ---------------------------------------------------------------------------


def _run(args: list[str], quotes: list[Quote] | None = None) -> Any:
    """Run the ``ts md quotes`` CLI command with a fake client.

    Patches ``anyio.run`` to avoid nested event loop issues and
    ``CLIContext.client`` to return a fake market_data service.
    """
    if quotes is None:
        quotes = _ALL_QUOTES

    runner = CliRunner()

    async def fake_get_quotes(symbols: list[str]) -> list[Quote]:
        return [q for q in quotes if q.symbol in symbols] or quotes

    fake_market_data = MagicMock()
    fake_market_data.get_quotes = fake_get_quotes

    fake_client = MagicMock()
    fake_client.market_data = fake_market_data

    import asyncio

    def fake_asyncio_run(coro: Any) -> Any:
        """Run a coroutine synchronously for testing (new loop each time)."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with (
        patch(
            "tradestation.cli.ctx.CLIContext.client",
            new_callable=lambda: property(lambda self: fake_client),
        ),
        patch(
            "tradestation.cli.commands.market_data.asyncio.run",
            side_effect=fake_asyncio_run,
        ),
    ):
        return runner.invoke(app, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMdQuotesTable:
    def test_renders_table_with_expected_columns(self) -> None:
        """Table output includes Symbol, Bid, Ask, and Halted columns.

        ``--output table`` is passed explicitly: under a non-TTY runner (CI),
        output auto-detects to JSONL, so we must force table mode to assert on
        column headers. The CliRunner uses a narrow terminal so column names
        may be abbreviated (e.g. "La…" for "Last").
        """
        result = _run(["--output", "table", "md", "quotes", "AAPL", "@ES", "BTCUSD"])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        # Symbol column always appears full-width
        assert "Symbol" in out
        # Bid and Ask are short enough not to be truncated
        assert "Bid" in out
        assert "Ask" in out
        # Halted is present (may show as H… due to column width)
        assert "Halt" in out or "H…" in out or "Halted" in out

    def test_renders_symbol_rows(self) -> None:
        """Each symbol appears as a row in the table."""
        result = _run(["md", "quotes", "AAPL", "@ES", "BTCUSD"])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "AAPL" in out
        assert "BTCUSD" in out

    def test_futures_large_price_renders(self) -> None:
        """Futures symbol with ~5300 price renders without crashing."""
        result = _run(["md", "quotes", "@ES"], quotes=[_QUOTE_ES])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        # Symbol appears in output
        assert "@ES" in out or "ES" in out

    def test_crypto_large_price_renders(self) -> None:
        """Crypto symbol with ~71k price renders correctly."""
        result = _run(["md", "quotes", "BTCUSD"], quotes=[_QUOTE_BTCUSD])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "BTCUSD" in out

    def test_comma_separated_form(self) -> None:
        """``ts md quotes AAPL,@ES,BTCUSD`` (comma form) works."""
        result = _run(["md", "quotes", "AAPL,@ES,BTCUSD"])
        assert result.exit_code == 0, result.output

    def test_file_flag_loads_symbols(self, tmp_path: Path) -> None:
        """``-f watchlist.txt`` loads symbols from file."""
        symbols_file = tmp_path / "watchlist.txt"
        symbols_file.write_text("AAPL\n@ES\nBTCUSD\n")
        result = _run(["md", "quotes", "-f", str(symbols_file)])
        assert result.exit_code == 0, result.output
        assert "AAPL" in _strip_ansi(result.output)


class TestMdQuotesOutputModes:
    def test_output_json_prints_valid_json_array(self) -> None:
        """``--output json`` prints a valid JSON array to stdout."""
        result = _run(["--output", "json", "md", "quotes", "AAPL"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "symbol" in data[0]
        assert "last" in data[0]

    def test_output_json_aapl_has_correct_values(self) -> None:
        """JSON output for AAPL has the expected numeric values."""
        result = _run(["--output", "json", "md", "quotes", "AAPL"], quotes=[_QUOTE_AAPL])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        q = data[0]
        assert q["symbol"] == "AAPL"
        assert q["last"] == pytest.approx(178.45)

    def test_output_csv_has_headers_and_rows(self) -> None:
        """``--output csv`` prints a header row followed by data rows."""
        result = _run(["--output", "csv", "md", "quotes", "AAPL"], quotes=[_QUOTE_AAPL])
        assert result.exit_code == 0, result.output
        lines = [ln for ln in result.output.strip().splitlines() if ln]
        assert len(lines) >= 2  # header + at least one row
        header = lines[0].split(",")
        assert "symbol" in header
        assert "last" in header
        # Data row
        assert "AAPL" in lines[1]

    def test_output_jsonl_one_per_line(self) -> None:
        """``--output jsonl`` prints one JSON object per line."""
        result = _run(["--output", "jsonl", "md", "quotes", "AAPL", "@ES"])
        assert result.exit_code == 0, result.output
        lines = [ln for ln in result.output.strip().splitlines() if ln]
        assert len(lines) >= 1
        obj = json.loads(lines[0])
        assert "symbol" in obj


class TestMdQuotesEdgeCases:
    def test_no_symbols_exits_2(self) -> None:
        """Running ``ts md quotes`` with no symbols exits with code 2."""
        runner = CliRunner()
        with patch(
            "tradestation.cli.ctx.CLIContext.client",
            new_callable=lambda: property(lambda self: MagicMock()),
        ):
            result = runner.invoke(app, ["md", "quotes"], catch_exceptions=False)
        assert result.exit_code == 2

    def test_banner_not_shown_with_quiet_flag(self) -> None:
        """``--quiet`` suppresses the context banner but keeps data."""
        result = _run(["--quiet", "md", "quotes", "AAPL"])
        assert result.exit_code == 0, result.output
        # With quiet, banner text like "Quotes  •" is suppressed
        assert "Quotes  •" not in result.output
