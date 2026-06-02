"""CLI tests for ``ts md options chain`` (B16 snapshot)."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tradestation.cli.app import app
from tradestation.models.market_data import OptionExpiration, Quote
from tradestation.streaming import StreamEvent


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _frame(strike: float, otype: str) -> dict[str, Any]:
    return {
        "Legs": [{"OptionType": otype, "StrikePrice": str(strike)}],
        "Bid": "1.20",
        "Ask": "1.30",
        "Last": "1.25",
        "Volume": "42",
        "DailyOpenInterest": "1000",
        "ImpliedVolatility": "0.25",
        "Delta": "0.50",
    }


_EXPIRATIONS = [
    OptionExpiration.model_validate({"Date": "2099-01-15", "Type": "Monthly"}),
    OptionExpiration.model_validate({"Date": "2099-02-19", "Type": "Monthly"}),
]


def _run(
    args: list[str],
    *,
    strike_universe: tuple[float, ...] = (195.0, 200.0, 205.0),
    captured: dict[str, Any] | None = None,
) -> Any:
    runner = CliRunner()

    async def fake_get_option_expirations(underlying: str, **kw: Any) -> list[OptionExpiration]:
        return _EXPIRATIONS

    async def fake_get_quotes(symbols: list[str]) -> list[Quote]:
        return [Quote.model_validate({"Symbol": symbols[0], "Last": "200.00"})]

    async def fake_stream_option_chain(underlying: str, expiration: str, **kw: Any) -> Any:
        if captured is not None:
            captured.update(kw)
        for strike in strike_universe:
            yield StreamEvent(raw=_frame(strike, "Call"))
            yield StreamEvent(raw=_frame(strike, "Put"))
        yield StreamEvent(raw={"StreamStatus": "EndSnapshot"})

    fake_md = MagicMock()
    fake_md.get_option_expirations = fake_get_option_expirations
    fake_md.get_quotes = fake_get_quotes
    fake_md.stream_option_chain = fake_stream_option_chain

    fake_client = MagicMock()
    fake_client.market_data = fake_md

    def fake_asyncio_run(coro: Any) -> Any:
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
        # Wide terminal so the multi-column chain table isn't truncated.
        return runner.invoke(app, args, catch_exceptions=False, env={"COLUMNS": "250"})


class TestOptionChain:
    def test_chain_renders_strikes_and_columns(self) -> None:
        result = _run(["--output", "table", "md", "options", "chain", "AAPL"])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "Strike" in out
        for strike in ("195.00", "200.00", "205.00"):
            assert strike in out
        # default columns include bid/ask -> values rendered on both sides
        assert "1.20" in out and "1.30" in out

    def test_chain_respects_column_selection(self) -> None:
        result = _run(
            ["--output", "table", "md", "options", "chain", "AAPL", "--columns", "iv,delta"]
        )
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "IV" in out and "Δ" in out
        # bid was not requested -> its value should not appear
        assert "1.20" not in out

    def test_chain_limits_strike_count(self) -> None:
        result = _run(["--output", "table", "md", "options", "chain", "AAPL", "--strikes", "1"])
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        # ATM is 200 -> only the 200 strike should show
        assert "200.00" in out
        assert "195.00" not in out and "205.00" not in out

    def test_chain_json_output(self) -> None:
        result = _run(["--output", "json", "md", "options", "chain", "AAPL"])
        assert result.exit_code == 0, result.output
        assert '"Strike"' in result.output

    def test_strikes_drives_server_strike_proximity(self) -> None:
        """-n must widen the request (strikeProximity), not just trim client-side.

        Regression: previously the stream was opened without strikeProximity, so
        the server returned its small default window and -n could never grow it.
        """
        captured: dict[str, Any] = {}
        result = _run(
            ["--output", "json", "md", "options", "chain", "AAPL", "-n", "100"],
            captured=captured,
        )
        assert result.exit_code == 0, result.output
        # proximity = (strikes // 2) + 3 = 53, requested per side of ATM.
        assert captured.get("strike_proximity") == 53

    def test_chain_returns_more_than_default_window(self) -> None:
        """With a wide universe and -n 40, ~40 strikes render (not capped at 20)."""
        universe = tuple(float(s) for s in range(100, 100 + 60))  # 60 strikes
        result = _run(
            ["--output", "json", "md", "options", "chain", "AAPL", "-n", "40"],
            strike_universe=universe,
        )
        assert result.exit_code == 0, result.output
        lines = [ln for ln in result.output.splitlines() if '"Strike"' in ln]
        assert len(lines) == 40, f"expected 40 strikes, got {len(lines)}"
