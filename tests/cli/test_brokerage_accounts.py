"""CLI tests for ``ts brokerage accounts`` (C1) — balance enrichment.

The C1 accounts endpoint returns metadata only; Equity / BuyingPower come
from the C2 balances endpoint. ``accounts`` merges them so the combined view
shows real figures instead of zeros (regression test for that bug).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tradestation.cli.app import app
from tradestation.models.brokerage import Account, Balances


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


_ACCOUNTS = [
    Account.model_validate(
        {"AccountID": "SIM123M", "AccountType": "Margin", "Status": "Active", "Currency": "USD"}
    )
]
_BALANCES = [
    Balances.model_validate(
        {"AccountID": "SIM123M", "Equity": "124308.41", "BuyingPower": "248616.82"}
    )
]


def _run(*, balances_raise: bool = False) -> Any:
    runner = CliRunner()

    async def fake_list_accounts() -> list[Account]:
        return _ACCOUNTS

    async def fake_get_balances(ids: list[str]) -> list[Balances]:
        if balances_raise:
            raise RuntimeError("balances unavailable")
        return _BALANCES

    fake_brokerage = MagicMock()
    fake_brokerage.list_accounts = fake_list_accounts
    fake_brokerage.get_balances = fake_get_balances

    fake_client = MagicMock()
    fake_client.brokerage = fake_brokerage

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
            "tradestation.cli.commands.brokerage.asyncio.run",
            side_effect=fake_asyncio_run,
        ),
    ):
        return runner.invoke(app, ["--output", "table", "brokerage", "accounts"])


class TestAccountsBalanceEnrichment:
    def test_accounts_show_real_equity_and_buying_power(self) -> None:
        """accounts merges C2 balances so figures are real, not 0.00."""
        result = _run()
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "124,308.41" in out
        assert "248,616.82" in out

    def test_accounts_render_when_balances_unavailable(self) -> None:
        """If balances can't be fetched, accounts still render (no zeros implied)."""
        result = _run(balances_raise=True)
        assert result.exit_code == 0, result.output
        out = _strip_ansi(result.output)
        assert "SIM123M" in out
        # Unknown balances render as an em dash, never a misleading 0.00.
        assert "—" in out
        assert "0.00" not in out
