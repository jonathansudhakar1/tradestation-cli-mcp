"""Rich renderers for CLI output.

Each renderer takes model-like inputs (dicts or dataclass-like objects) and
returns Rich renderables (tables, panels, text) or prints to a Console.

See docs/07-output-style.md for table conventions, detail panels, banner
format, and error rendering.

All renderers are **pure** (no I/O) unless they accept a ``console`` argument
and actually print.  Prefer returning renderables; let commands do the print.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign(value: float) -> str:
    """Return a string with an explicit ``+`` or ``-`` sign."""
    return f"+{value:,.2f}" if value >= 0 else f"{value:,.2f}"


def _pnl_style(value: float) -> str:
    """Return the semantic style name for a profit/loss value."""
    if value > 0:
        return "ts.up"
    if value < 0:
        return "ts.down"
    return "ts.flat"


def _masked(secret: str, visible: int = 4) -> str:
    """Return ``******XXXX`` where XXXX is the last *visible* chars."""
    if len(secret) <= visible:
        return "******"
    return "******" + secret[-visible:]


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def banner(operation: str, scope: str, env: str, ts: str | None = None) -> Text:
    """Return a one-line context banner as a Rich :class:`~rich.text.Text`.

    Format: ``{operation}  •  {scope}  •  {env}  •  {ts} UTC``

    Args:
        operation: Command name, e.g. ``"Quotes"``.
        scope: Scope description, e.g. ``"3 symbols"``.
        env: Environment, e.g. ``"live"`` or ``"sim"``.
        ts: Timestamp string (UTC HH:MM:SS).  Defaults to current UTC time.
    """
    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    text = Text()
    parts = [operation, scope, env, f"{ts} UTC"]
    sep = Text("  •  ", style="ts.muted")
    for i, part in enumerate(parts):
        if i > 0:
            text.append_text(sep)
        text.append(part, style="ts.header")
    return text


# ---------------------------------------------------------------------------
# Quote table
# ---------------------------------------------------------------------------


def table_quotes(quotes: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for quote snapshots.

    Expected dict keys (TradeStation v3 Quote shape, case-insensitive mapping):
        Symbol, Last, NetChange, NetChangePct, Bid, BidSize, Ask, AskSize,
        Volume, Open, High, Low, MarketFlags.IsHalted, TradeTime.

    See docs/07-output-style.md §"Example: ts md quotes …".
    """
    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("Symbol", style="ts.symbol", no_wrap=True)
    tbl.add_column("Last", style="ts.price", justify="right")
    tbl.add_column("Δ", justify="right")
    tbl.add_column("Δ%", justify="right")
    tbl.add_column("Bid", style="ts.price", justify="right")
    tbl.add_column("BidSz", justify="right")
    tbl.add_column("Ask", style="ts.price", justify="right")
    tbl.add_column("AskSz", justify="right")
    tbl.add_column("Volume", justify="right", style="ts.muted")
    tbl.add_column("Open", style="ts.price", justify="right")
    tbl.add_column("High", style="ts.price", justify="right")
    tbl.add_column("Low", style="ts.price", justify="right")
    tbl.add_column("Halted", justify="center")

    for q in quotes:
        symbol = str(q.get("Symbol", ""))
        last_raw = q.get("Last", "0")
        last = float(last_raw) if last_raw else 0.0
        change_raw = q.get("NetChange", "0")
        change = float(change_raw) if change_raw else 0.0
        pct_raw = q.get("NetChangePct", "0")
        pct = float(pct_raw) if pct_raw else 0.0
        bid = q.get("Bid", "")
        bid_sz = q.get("BidSize", "")
        ask = q.get("Ask", "")
        ask_sz = q.get("AskSize", "")
        volume_raw = q.get("Volume", "0")
        volume = int(float(volume_raw)) if volume_raw else 0
        open_ = q.get("Open", "")
        high = q.get("High", "")
        low = q.get("Low", "")
        mf = q.get("MarketFlags", {})
        halted = mf.get("IsHalted", False) if isinstance(mf, dict) else False
        halted_str = Text("yes", style="ts.warn") if halted else Text("no", style="ts.muted")

        change_style = _pnl_style(change)
        tbl.add_row(
            symbol,
            f"{last:,.2f}",
            Text(_sign(change), style=change_style),
            Text(f"{'+' if pct >= 0 else ''}{pct:.2f}%", style=change_style),
            str(bid),
            str(bid_sz),
            str(ask),
            str(ask_sz),
            f"{volume:,}",
            str(open_),
            str(high),
            str(low),
            halted_str,
        )
    return tbl


# ---------------------------------------------------------------------------
# Positions table
# ---------------------------------------------------------------------------


def table_positions(positions: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for open brokerage positions.

    See docs/07-output-style.md §"Example: ts brokerage positions …".
    """
    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("Symbol", style="ts.symbol", no_wrap=True)
    tbl.add_column("Asset", justify="center")
    tbl.add_column("Qty", justify="right")
    tbl.add_column("AvgEntry", justify="right", style="ts.price")
    tbl.add_column("Last", justify="right", style="ts.price")
    tbl.add_column("MV", justify="right", style="ts.price")
    tbl.add_column("UPnL ($)", justify="right")
    tbl.add_column("UPnL (%)", justify="right")
    tbl.add_column("Side", justify="center")

    for p in positions:
        symbol = str(p.get("Symbol", ""))
        asset = str(p.get("AssetType", ""))
        qty_raw = p.get("Quantity", "0")
        qty = float(qty_raw) if qty_raw else 0.0
        avg_raw = p.get("AveragePrice", "0")
        avg = float(avg_raw) if avg_raw else 0.0
        last_raw = p.get("Last", "0")
        last = float(last_raw) if last_raw else 0.0
        mv_raw = p.get("MarketValue", "0")
        mv = float(mv_raw) if mv_raw else 0.0
        upnl_raw = p.get("UnrealizedProfitLoss", "0")
        upnl = float(upnl_raw) if upnl_raw else 0.0
        upnl_pct_raw = p.get("UnrealizedProfitLossPct", "0")
        upnl_pct = float(upnl_pct_raw) if upnl_pct_raw else 0.0
        long_short = p.get("LongShort", "Long")
        side = "LONG" if str(long_short).lower() == "long" else "SHORT"

        upnl_style = _pnl_style(upnl)
        qty_str = f"{qty:g}" if qty == int(qty) else f"{qty}"
        tbl.add_row(
            symbol,
            asset[:6],
            qty_str,
            f"{avg:,.2f}",
            f"{last:,.2f}",
            f"{mv:,.2f}",
            Text(_sign(upnl), style=upnl_style),
            Text(f"{'+' if upnl_pct >= 0 else ''}{upnl_pct:.2f}%", style=upnl_style),
            side,
        )
    return tbl


# ---------------------------------------------------------------------------
# Orders table
# ---------------------------------------------------------------------------


def table_orders(orders: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for brokerage orders.

    Columns: ID · Time · Symbol · Side · Type · Qty · Filled · Price · Status.
    """
    _STATUS_STYLES: dict[str, str] = {
        "filled": "ts.up",
        "partiallyFilled": "ts.up",
        "working": "cyan",
        "fpo": "cyan",
        "rejected": "ts.down",
        "cancelled": "ts.muted",
        "expired": "ts.muted",
    }

    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("ID", style="ts.mono", no_wrap=True)
    tbl.add_column("Time", justify="right", style="ts.muted")
    tbl.add_column("Symbol", style="ts.symbol")
    tbl.add_column("Side", justify="center")
    tbl.add_column("Type", justify="center")
    tbl.add_column("Qty", justify="right")
    tbl.add_column("Filled", justify="right")
    tbl.add_column("Price", justify="right", style="ts.price")
    tbl.add_column("Status", justify="center")

    for o in orders:
        order_id = str(o.get("OrderID", ""))
        # Truncate long IDs
        if len(order_id) > 8:
            order_id = "…" + order_id[-4:]
        opened_raw = o.get("OpenedDateTime", "")
        if opened_raw:
            try:
                dt = datetime.fromisoformat(str(opened_raw).replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except ValueError:
                time_str = str(opened_raw)[:8]
        else:
            time_str = ""
        # Symbol / side / qty live in the first leg for TS v3 orders;
        # fall back to top-level fields when present.
        legs = o.get("Legs") or []
        leg0: dict[str, Any] = legs[0] if legs and isinstance(legs[0], dict) else {}
        symbol = str(o.get("Symbol") or leg0.get("Symbol", ""))
        side = str(o.get("Side") or leg0.get("BuyOrSell", ""))
        order_type = str(o.get("OrderType", ""))
        qty = str(o.get("Quantity") or leg0.get("QuantityOrdered", ""))
        filled = str(o.get("FilledQuantity") or leg0.get("ExecQuantity", "0"))
        # Price — limit or stop
        price = o.get("LimitPrice", o.get("StopPrice", ""))
        price_str = str(price) if price else "MKT"
        status = str(o.get("Status", ""))
        status_lower = status.lower()
        status_style = _STATUS_STYLES.get(status_lower, "ts.value")
        tbl.add_row(
            order_id,
            time_str,
            symbol,
            side,
            order_type,
            qty,
            filled,
            price_str,
            Text(status, style=status_style),
        )
    return tbl


# ---------------------------------------------------------------------------
# Accounts table
# ---------------------------------------------------------------------------


def table_accounts(accounts: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for brokerage accounts (C1)."""
    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("Account", style="ts.mono")
    tbl.add_column("Type")
    tbl.add_column("Status")
    tbl.add_column("Currency", justify="center")
    tbl.add_column("Equity", justify="right", style="ts.price")
    tbl.add_column("BuyingPower", justify="right", style="ts.price")

    for a in accounts:
        acct = str(a.get("AccountID", ""))
        acct_type = str(a.get("AccountType", ""))
        status = str(a.get("Status", ""))
        currency = str(a.get("Currency", "USD"))
        equity_raw = a.get("Equity", "0")
        equity = float(equity_raw) if equity_raw else 0.0
        bp_raw = a.get("BuyingPower", "0")
        bp = float(bp_raw) if bp_raw else 0.0
        tbl.add_row(
            acct,
            acct_type,
            status,
            currency,
            f"{equity:,.2f}",
            f"{bp:,.2f}",
        )
    return tbl


# ---------------------------------------------------------------------------
# Balances table
# ---------------------------------------------------------------------------


def table_balances(balances: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for account balances (C2/C3)."""
    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("Account", style="ts.mono")
    tbl.add_column("Cash Balance", justify="right", style="ts.price")
    tbl.add_column("Equity", justify="right", style="ts.price")
    tbl.add_column("Market Value", justify="right", style="ts.price")
    tbl.add_column("Unrealized PnL", justify="right")

    for b in balances:
        acct = str(b.get("AccountID", ""))
        cash_raw = b.get("CashBalance", "0")
        cash = float(cash_raw) if cash_raw else 0.0
        equity_raw = b.get("Equity", "0")
        equity = float(equity_raw) if equity_raw else 0.0
        mv_raw = b.get("MarketValue", "0")
        mv = float(mv_raw) if mv_raw else 0.0
        upnl_raw = b.get("UnrealizedProfitLoss", "0")
        upnl = float(upnl_raw) if upnl_raw else 0.0
        upnl_style = _pnl_style(upnl)
        tbl.add_row(
            acct,
            f"{cash:,.2f}",
            f"{equity:,.2f}",
            f"{mv:,.2f}",
            Text(_sign(upnl), style=upnl_style),
        )
    return tbl


# ---------------------------------------------------------------------------
# Routes table
# ---------------------------------------------------------------------------


def table_routes(routes: Sequence[dict[str, Any]]) -> Table:
    """Return a Rich table for execution routes (D8)."""
    tbl = Table(
        box=box.ROUNDED,
        header_style="ts.header",
        show_lines=False,
    )
    tbl.add_column("Route", style="ts.mono")
    tbl.add_column("Asset")
    tbl.add_column("Exchange")
    tbl.add_column("Description")

    for r in routes:
        tbl.add_row(
            str(r.get("Id", r.get("Route", ""))),
            str(r.get("AssetTypes", r.get("AssetType", ""))),
            str(r.get("Exchange", "")),
            str(r.get("Name", r.get("Description", ""))),
        )
    return tbl


# ---------------------------------------------------------------------------
# Auth status panel
# ---------------------------------------------------------------------------


def panel_auth_status(
    *,
    path: str,
    scheme: str,
    keyring_backend: str | None,
    environment: str,
    client_id: str,
    refresh_token: str,
    access_token_status: str,
    access_token_expiry: str | None,
    scope: str,
    rotation: str = "off",
) -> Panel:
    """Return a Rich panel for ``ts auth status`` output.

    All secret values should already be masked (last-4 only).

    See docs/04-cli-design.md §"ts auth status" for the example layout.
    """
    keyring_str = f"   [ts.muted](keyring: {keyring_backend})[/ts.muted]" if keyring_backend else ""
    rotation_str = f"   [ts.muted](rotation: {rotation})[/ts.muted]"

    if access_token_expiry:
        token_line = (
            f"[ts.ok]valid[/ts.ok]   [ts.muted](expires {access_token_expiry} UTC)[/ts.muted]"
        )
    else:
        token_line = f"[ts.bad]{access_token_status}[/ts.bad]"

    lines = [
        f"[ts.label]Path          [/ts.label]  [ts.mono]{path}[/ts.mono]",
        f"[ts.label]Scheme        [/ts.label]  [ts.value]{scheme}[/ts.value]{keyring_str}",
        f"[ts.label]Environment   [/ts.label]  [ts.value]{environment}[/ts.value]",
        f"[ts.label]Client ID     [/ts.label]  [ts.mono]{_masked(client_id)}[/ts.mono]",
        f"[ts.label]Refresh token [/ts.label]  "
        f"[ts.mono]{_masked(refresh_token)}[/ts.mono]{rotation_str}",
        f"[ts.label]Access token  [/ts.label]  {token_line}",
        f"[ts.label]Scope         [/ts.label]  [ts.muted]{scope}[/ts.muted]",
    ]
    content = "\n".join(lines)
    return Panel(
        content,
        title="[ts.header]TradeStation credentials[/ts.header]",
        border_style="ts.header",
        expand=False,
    )


# ---------------------------------------------------------------------------
# Order preview panel
# ---------------------------------------------------------------------------


def panel_order_preview(
    *,
    account: str,
    symbol: str,
    side: str,
    qty: str | int,
    order_type: str,
    tif: str,
    est_cost: float | None = None,
    commission: float | None = None,
    buying_power_after: float | None = None,
    buying_power_before: float | None = None,
    route: str = "AUTO",
    warnings: list[str] | None = None,
) -> Panel:
    """Return a Rich panel for order preview (D1 / ``ts order confirm``)."""
    header_line = (
        f"[ts.mono]{account}[/ts.mono]  •  "
        f"[ts.symbol]{symbol}[/ts.symbol]  •  "
        f"[ts.value]{side.upper()} {qty}[/ts.value]  •  "
        f"[ts.value]{order_type}[/ts.value]  •  "
        f"[ts.muted]{tif.upper()}[/ts.muted]"
    )
    lines = [header_line, ""]
    if est_cost is not None:
        lines.append(f"[ts.label]Est cost      [/ts.label]  [ts.price]${est_cost:,.2f}[/ts.price]")
    if commission is not None:
        lines.append(
            f"[ts.label]Commission    [/ts.label]  [ts.price]${commission:,.2f}[/ts.price]"
        )
    if buying_power_after is not None and buying_power_before is not None:
        delta = buying_power_after - buying_power_before
        delta_str = _sign(delta)
        lines.append(
            f"[ts.label]BuyingPower   [/ts.label]  "
            f"[ts.price]${buying_power_after:,.2f}[/ts.price]  "
            f"[ts.muted](was ${buying_power_before:,.2f} — Δ {delta_str})[/ts.muted]"
        )
    lines.append(f"[ts.label]Route         [/ts.label]  [ts.value]{route}[/ts.value]")
    warns = warnings or []
    if warns:
        for w in warns:
            lines.append(f"[ts.warn]  ⚠  {w}[/ts.warn]")
    else:
        lines.append("[ts.label]Warnings      [/ts.label]  [ts.muted](none)[/ts.muted]")

    content = "\n".join(lines)
    return Panel(
        content,
        title="[ts.header]Order preview (Confirm)[/ts.header]",
        border_style="ts.header",
        expand=False,
    )


# ---------------------------------------------------------------------------
# Symbol detail panel
# ---------------------------------------------------------------------------


def panel_symbol_detail(symbol_data: dict[str, Any]) -> Panel:
    """Return a Rich detail panel for a single symbol (B3)."""
    symbol = str(symbol_data.get("Symbol", ""))
    lines: list[str] = []
    for key, val in symbol_data.items():
        if key == "Symbol":
            continue
        lines.append(f"[ts.label]{key:<20}[/ts.label]  [ts.value]{val}[/ts.value]")
    content = "\n".join(lines) if lines else "[ts.muted](no detail)[/ts.muted]"
    return Panel(
        content,
        title=f"[ts.symbol]{symbol}[/ts.symbol]",
        border_style="ts.header",
        expand=False,
    )


# ---------------------------------------------------------------------------
# Error rendering
# ---------------------------------------------------------------------------


def render_error(
    err: Exception,
    *,
    console: Console,
    verbose: int = 0,
) -> None:
    """Print a formatted error block to *console*.

    Format::

        ✖ AUTH 401   refresh token rejected
          endpoint     POST https://…
          request id   8b2a3c8e-…
          detail       invalid_grant
          next step    Run `ts auth login` …

    See docs/07-output-style.md §"Error rendering".
    """
    from tradestation.errors import ApiError, AuthError, OrderRejectedError, TradeStationError

    if isinstance(err, TradeStationError):
        status = err.status
        if isinstance(err, AuthError):
            category = f"AUTH {status}" if status else "AUTH"
        elif isinstance(err, ApiError):
            category = f"API {status}" if status else "API"
        elif isinstance(err, OrderRejectedError):
            category = "ORDER REJECTED"
        else:
            category = "ERROR"

        console.print(f"\n[ts.bad]✖[/ts.bad] [ts.danger]{category}[/ts.danger]   {err}")
        if err.request_id:
            console.print(
                f"  [ts.label]request id  [/ts.label] [ts.mono]{err.request_id}[/ts.mono]"
            )
        if err.payload:
            detail = err.payload.get("error_description") or err.payload.get("Message", "")
            if detail:
                console.print(f"  [ts.label]detail      [/ts.label] {detail}")
        hint = _error_hint(err)
        if hint:
            console.print(f"  [ts.label]next step   [/ts.label] {hint}")
        if verbose >= 2:
            console.print_exception()
    else:
        console.print(f"\n[ts.bad]✖[/ts.bad] [ts.danger]{type(err).__name__}[/ts.danger]: {err}")
        if verbose >= 2:
            console.print_exception()


def _error_hint(err: Exception) -> str:
    """Return a contextual next-step hint for *err*."""
    from tradestation.errors import AuthError, NoCredentialsError, RefreshTokenExpired

    if isinstance(err, RefreshTokenExpired):
        return (
            "Run `ts auth login` to obtain a new refresh token, or `ts auth set --refresh-token …`."
        )
    if isinstance(err, NoCredentialsError):
        return "Run `ts auth set` to configure credentials."
    if isinstance(err, AuthError):
        return (
            "Run `ts auth status` to inspect credentials, or `ts auth refresh` to force a refresh."
        )
    return ""


# ---------------------------------------------------------------------------
# JSON rendering
# ---------------------------------------------------------------------------


def render_json(data: Any, *, console: Console) -> None:
    """Print *data* as syntax-highlighted JSON to *console*."""
    json_str = json.dumps(data, indent=2, default=str)
    syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
    console.print(syntax)


def render_jsonl(items: Sequence[Any], *, console: Console) -> None:
    """Print *items* as newline-delimited JSON (one object per line) to *console*."""
    for item in items:
        console.print(json.dumps(item, default=str))
