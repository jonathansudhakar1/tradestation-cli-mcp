"""Tests for render.py — tables and panels render expected columns; piped mode uses JSONL."""

from __future__ import annotations

import io
from typing import Any

from rich.console import Console

from tradestation.cli.render import (
    banner,
    panel_auth_status,
    panel_order_preview,
    render_error,
    render_json,
    render_jsonl,
    table_accounts,
    table_balances,
    table_orders,
    table_positions,
    table_quotes,
)
from tradestation.cli.theme import get_theme


def _make_console(*, is_terminal: bool = True) -> tuple[Console, io.StringIO]:
    """Return a (Console, StringIO) pair for testing output.

    Uses a wide width (200) to avoid column truncation and no_color=True for
    plain-text assertions.
    """
    buf = io.StringIO()
    theme = get_theme()
    console = Console(
        file=buf,
        theme=theme,
        force_terminal=is_terminal,
        force_jupyter=False,
        no_color=True,  # plain text for assertions
        width=200,  # wide enough to avoid cell truncation
    )
    return console, buf


# ---------------------------------------------------------------------------
# table_quotes
# ---------------------------------------------------------------------------


class TestTableQuotes:
    def test_renders_expected_columns(self, sample_quotes: list[dict[str, Any]]) -> None:
        """quote table must have Symbol, Last, Δ, Δ%, Bid, BidSz, Ask, AskSz, Volume columns."""
        tbl = table_quotes(sample_quotes)
        column_headers = [str(col.header) for col in tbl.columns]
        assert "Symbol" in column_headers
        assert "Last" in column_headers
        assert "Δ" in column_headers
        assert "Δ%" in column_headers
        assert "Bid" in column_headers
        assert "Ask" in column_headers
        assert "Volume" in column_headers

    def test_renders_all_rows(self, sample_quotes: list[dict[str, Any]]) -> None:
        """table must contain a row for each input quote."""
        tbl = table_quotes(sample_quotes)
        assert tbl.row_count == len(sample_quotes)

    def test_renders_futures_symbol(self, sample_quotes: list[dict[str, Any]]) -> None:
        """table must include the futures symbol ES.M26."""
        console, buf = _make_console()
        console.print(table_quotes(sample_quotes))
        output = buf.getvalue()
        assert "ES.M26" in output

    def test_renders_crypto_symbol(self, sample_quotes: list[dict[str, Any]]) -> None:
        """table must include the crypto symbol BTCUSD."""
        console, buf = _make_console()
        console.print(table_quotes(sample_quotes))
        output = buf.getvalue()
        assert "BTCUSD" in output

    def test_empty_quotes_produces_table(self) -> None:
        """empty input should still return a valid table (no rows)."""
        tbl = table_quotes([])
        assert tbl.row_count == 0

    def test_halted_symbol_flag(self) -> None:
        """Halted symbols should show 'yes' in the Halted column."""
        quotes = [
            {
                "Symbol": "HALTED",
                "Last": "10.00",
                "NetChange": "0",
                "NetChangePct": "0",
                "Bid": "10.00",
                "BidSize": "100",
                "Ask": "10.01",
                "AskSize": "100",
                "Open": "10.00",
                "High": "10.00",
                "Low": "10.00",
                "Volume": "0",
                "MarketFlags": {"IsHalted": True},
            }
        ]
        console, buf = _make_console()
        console.print(table_quotes(quotes))
        output = buf.getvalue()
        assert "yes" in output


# ---------------------------------------------------------------------------
# table_positions
# ---------------------------------------------------------------------------


class TestTablePositions:
    def test_renders_expected_columns(
        self, sample_positions: list[dict[str, Any]]
    ) -> None:
        """positions table must have Symbol, Asset, Qty, AvgEntry, Last, MV, UPnL columns."""
        tbl = table_positions(sample_positions)
        column_headers = [str(col.header) for col in tbl.columns]
        assert "Symbol" in column_headers
        assert "Asset" in column_headers
        assert "Qty" in column_headers
        assert "AvgEntry" in column_headers
        assert "Last" in column_headers
        assert "MV" in column_headers

    def test_renders_futures(self, sample_positions: list[dict[str, Any]]) -> None:
        """positions table must include ES.M26 (futures)."""
        console, buf = _make_console()
        console.print(table_positions(sample_positions))
        assert "ES.M26" in buf.getvalue()

    def test_renders_crypto(self, sample_positions: list[dict[str, Any]]) -> None:
        """positions table must include BTCUSD (crypto)."""
        console, buf = _make_console()
        console.print(table_positions(sample_positions))
        assert "BTCUSD" in buf.getvalue()

    def test_upnl_shown(self, sample_positions: list[dict[str, Any]]) -> None:
        """positions table must include UPnL values."""
        tbl = table_positions(sample_positions)
        column_headers = [str(col.header) for col in tbl.columns]
        assert any("PnL" in h or "UPnL" in h for h in column_headers)

    def test_all_rows_rendered(self, sample_positions: list[dict[str, Any]]) -> None:
        """table must contain a row for each position."""
        tbl = table_positions(sample_positions)
        assert tbl.row_count == len(sample_positions)


# ---------------------------------------------------------------------------
# table_orders
# ---------------------------------------------------------------------------


class TestTableOrders:
    def test_renders_expected_columns(self) -> None:
        """orders table must have ID, Time, Symbol, Side, Type, Qty, Filled, Price, Status."""
        orders: list[dict[str, Any]] = [
            {
                "OrderID": "835711",
                "OpenedDateTime": "2026-06-01T09:30:00Z",
                "Symbol": "AAPL",
                "Side": "BUY",
                "OrderType": "Limit",
                "Quantity": "100",
                "FilledQuantity": "0",
                "LimitPrice": "178.00",
                "Status": "Working",
            }
        ]
        tbl = table_orders(orders)
        column_headers = [str(col.header) for col in tbl.columns]
        assert "ID" in column_headers
        assert "Symbol" in column_headers
        assert "Side" in column_headers
        assert "Status" in column_headers

    def test_long_order_id_truncated(self) -> None:
        """Long order IDs should be truncated with '…' prefix."""
        orders: list[dict[str, Any]] = [
            {
                "OrderID": "VERYLONGORDERID123456789",
                "Symbol": "AAPL",
                "Side": "BUY",
                "OrderType": "Market",
                "Quantity": "100",
                "FilledQuantity": "0",
                "Status": "Working",
            }
        ]
        console, buf = _make_console()
        console.print(table_orders(orders))
        output = buf.getvalue()
        # Should not contain the full long ID
        assert "VERYLONGORDERID123456789" not in output


# ---------------------------------------------------------------------------
# table_accounts
# ---------------------------------------------------------------------------


class TestTableAccounts:
    def test_renders_expected_columns(self) -> None:
        """accounts table must have Account, Type, Status, Currency, Equity, BuyingPower."""
        accounts: list[dict[str, Any]] = [
            {
                "AccountID": "11111111",
                "AccountType": "Margin",
                "Status": "Active",
                "Currency": "USD",
                "Equity": "124308.41",
                "BuyingPower": "248616.82",
            }
        ]
        tbl = table_accounts(accounts)
        column_headers = [str(col.header) for col in tbl.columns]
        assert "Account" in column_headers
        assert "Type" in column_headers
        assert "Equity" in column_headers


# ---------------------------------------------------------------------------
# table_balances
# ---------------------------------------------------------------------------


class TestTableBalances:
    def test_renders_expected_columns(self) -> None:
        """balances table must include Account, Cash Balance, Equity, Unrealized PnL."""
        balances: list[dict[str, Any]] = [
            {
                "AccountID": "11111111",
                "CashBalance": "100000.00",
                "Equity": "124308.41",
                "MarketValue": "24308.41",
                "UnrealizedProfitLoss": "1234.56",
            }
        ]
        tbl = table_balances(balances)
        column_headers = [str(col.header) for col in tbl.columns]
        assert "Account" in column_headers
        assert any("Cash" in h or "Balance" in h for h in column_headers)


# ---------------------------------------------------------------------------
# panel_auth_status
# ---------------------------------------------------------------------------


class TestPanelAuthStatus:
    def test_shows_masked_client_id(self) -> None:
        """Auth status panel must mask the client_id."""
        panel = panel_auth_status(
            path="/home/user/.tscli/credentials",
            scheme="plaintext",
            keyring_backend=None,
            environment="sim",
            client_id="LONGFAKECLIENTID1234M3xQ",
            refresh_token="LONGFAKEREFRESHTOKEN1234t9pK",
            access_token_status="valid",
            access_token_expiry="in 17m 02s — 15:30",
            scope="openid offline_access MarketData",
        )
        console, buf = _make_console()
        console.print(panel)
        output = buf.getvalue()
        # Full client_id must not appear
        assert "LONGFAKECLIENTID1234M3xQ" not in output
        # Last-4 should appear
        assert "M3xQ" in output

    def test_shows_environment(self) -> None:
        """Auth status panel must show the environment."""
        panel = panel_auth_status(
            path="/home/user/.tscli/credentials",
            scheme="plaintext",
            keyring_backend=None,
            environment="live",
            client_id="CLIENTID",
            refresh_token="TOKEN",
            access_token_status="valid",
            access_token_expiry="in 17m",
            scope="openid",
        )
        console, buf = _make_console()
        console.print(panel)
        assert "live" in buf.getvalue()

    def test_shows_scope(self) -> None:
        """Auth status panel must show scope string."""
        panel = panel_auth_status(
            path="/tmp/credentials",
            scheme="fernet-v1",
            keyring_backend="SecretService",
            environment="sim",
            client_id="ID",
            refresh_token="TOKEN",
            access_token_status="valid",
            access_token_expiry=None,
            scope="openid offline_access MarketData ReadAccount Trade",
        )
        console, buf = _make_console()
        console.print(panel)
        assert "MarketData" in buf.getvalue()


# ---------------------------------------------------------------------------
# panel_order_preview
# ---------------------------------------------------------------------------


class TestPanelOrderPreview:
    def test_shows_order_details(self) -> None:
        """Order preview panel must show account, symbol, side, qty."""
        panel = panel_order_preview(
            account="11111111",
            symbol="AAPL",
            side="BUY",
            qty=100,
            order_type="Market",
            tif="DAY",
            est_cost=16743.00,
            commission=0.00,
            buying_power_after=231873.82,
            buying_power_before=248616.82,
            route="AUTO",
        )
        console, buf = _make_console()
        console.print(panel)
        output = buf.getvalue()
        assert "AAPL" in output
        assert "BUY" in output
        assert "11111111" in output

    def test_shows_warnings(self) -> None:
        """Order preview panel should display warnings when provided."""
        panel = panel_order_preview(
            account="11111111",
            symbol="AAPL",
            side="BUY",
            qty=100,
            order_type="Limit",
            tif="GTC",
            warnings=["This is a test warning"],
        )
        console, buf = _make_console()
        console.print(panel)
        assert "test warning" in buf.getvalue()


# ---------------------------------------------------------------------------
# banner
# ---------------------------------------------------------------------------


class TestBanner:
    def test_banner_contains_all_parts(self) -> None:
        """Banner should contain operation, scope, env, and timestamp."""
        text = banner("Quotes", "3 symbols", "live", "15:32:07")
        rendered = text.plain
        assert "Quotes" in rendered
        assert "3 symbols" in rendered
        assert "live" in rendered
        assert "15:32:07" in rendered

    def test_banner_auto_timestamp(self) -> None:
        """Banner with no ts should auto-generate a UTC timestamp."""
        text = banner("Positions", "2 accounts", "sim")
        rendered = text.plain
        # Should have a HH:MM:SS UTC timestamp somewhere
        import re

        assert re.search(r"\d{2}:\d{2}:\d{2}", rendered)


# ---------------------------------------------------------------------------
# render_error
# ---------------------------------------------------------------------------


class TestRenderError:
    def test_renders_auth_error(self) -> None:
        """render_error should format AuthError with AUTH label."""
        from tradestation.errors import AuthError

        err = AuthError("refresh token rejected", status=401, request_id="abc123")
        console, buf = _make_console()
        render_error(err, console=console)
        output = buf.getvalue()
        assert "AUTH" in output or "auth" in output.lower()
        assert "401" in output

    def test_renders_generic_exception(self) -> None:
        """render_error should handle generic Python exceptions gracefully."""
        err = ValueError("something went wrong")
        console, buf = _make_console()
        render_error(err, console=console)
        output = buf.getvalue()
        assert "something went wrong" in output

    def test_renders_request_id(self) -> None:
        """render_error should include the request_id when present."""
        import re

        from tradestation.errors import ApiError

        err = ApiError("not found", status=404, request_id="req-999")
        console, buf = _make_console()
        render_error(err, console=console)
        # Strip ANSI escape sequences before asserting (bold markup may split the string)
        raw = buf.getvalue()
        plain = re.sub(r"\x1b\[[0-9;]*m", "", raw)
        assert "req-999" in plain


# ---------------------------------------------------------------------------
# render_json / render_jsonl
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_render_json_outputs_json(self) -> None:
        """render_json should produce valid JSON-parseable output."""
        import json

        console, buf = _make_console()
        render_json({"symbol": "AAPL", "price": 178.45}, console=console)
        output = buf.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["symbol"] == "AAPL"

    def test_render_jsonl_outputs_one_per_line(self) -> None:
        """render_jsonl should output one JSON object per line."""
        import json

        items = [{"a": 1}, {"b": 2}, {"c": 3}]
        console, buf = _make_console(is_terminal=False)
        render_jsonl(items, console=console)
        lines = [ln.strip() for ln in buf.getvalue().strip().splitlines() if ln.strip()]
        assert len(lines) == 3
        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed == items[i]


# ---------------------------------------------------------------------------
# Piped output mode (JSONL auto-detect)
# ---------------------------------------------------------------------------


class TestPipedOutputMode:
    def test_non_terminal_console_is_not_terminal(self) -> None:
        """A Console with force_terminal=False should report is_terminal as False."""
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False)
        assert not console.is_terminal

    def test_terminal_console_is_terminal(self) -> None:
        """A Console with force_terminal=True should report is_terminal as True."""
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=True)
        assert console.is_terminal
