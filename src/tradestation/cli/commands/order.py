"""``ts order`` command group — order execution (D1-D8).

Subcommands:
    routes        — list execution routes (D8)
    triggers      — list activation triggers (D7)
    confirm       — preview a single order without submitting (D1)
    place         — submit a single order (D2) — shows preview + prompts first
    cancel        — cancel a working order (D4) — requires typing the order ID
    replace       — modify a working order (D3)
    group confirm — preview a grouped OCO/bracket/OSO order (D5)
    group place   — submit a grouped OCO/bracket/OSO order (D6)

See docs/03-endpoint-inventory.md §"D. OrderExecution".
See docs/04-cli-design.md §"Section D — OrderExecution".
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
from rich import box
from rich.table import Table

from tradestation.cli.ctx import CLIContext, OutputMode
from tradestation.cli.render import (
    banner as render_banner,
)
from tradestation.cli.render import (
    panel_order_preview,
    render_error,
    table_routes,
)
from tradestation.enums import OrderType, Side, TimeInForce
from tradestation.models.orders import (
    LimitOrderRequest,
    MarketOrderRequest,
    OrderGroupRequest,
    OrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)

app = typer.Typer(
    name="order",
    help="[bold]Order execution[/bold]: place, cancel, confirm, routes, triggers.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _exit_code(exc: Exception) -> int:
    from tradestation.errors import (
        ApiError,
        AuthError,
        NoCredentialsError,
        OrderRejectedError,
        RateLimitError,
    )

    if isinstance(exc, (AuthError, NoCredentialsError)):
        return 3
    if isinstance(exc, RateLimitError):
        return 4
    if isinstance(exc, OrderRejectedError):
        return 6
    if isinstance(exc, ApiError):
        return 5
    return 1


def _run(cli: CLIContext, coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except Exception as exc:
        render_error(exc, console=cli.console, verbose=cli.verbose)
        raise typer.Exit(code=_exit_code(exc)) from exc


def _build_request(
    *,
    account: str,
    symbol: str,
    side: Side,
    order_type: OrderType,
    qty: float,
    tif: TimeInForce,
    limit_price: float | None,
    stop_price: float | None,
) -> OrderRequest:
    """Construct the right OrderRequest subclass for the order type."""
    if order_type is OrderType.MARKET:
        return MarketOrderRequest(
            account_id=account, symbol=symbol, quantity=qty, side=side, time_in_force=tif
        )
    if order_type is OrderType.LIMIT:
        if limit_price is None:
            raise typer.BadParameter("--limit-price is required for a limit order")
        return LimitOrderRequest(
            account_id=account,
            symbol=symbol,
            quantity=qty,
            side=side,
            time_in_force=tif,
            limit_price=limit_price,
        )
    if order_type is OrderType.STOP_MARKET:
        if stop_price is None:
            raise typer.BadParameter("--stop-price is required for a stop order")
        return StopOrderRequest(
            account_id=account,
            symbol=symbol,
            quantity=qty,
            side=side,
            time_in_force=tif,
            stop_price=stop_price,
        )
    if stop_price is None or limit_price is None:
        raise typer.BadParameter(
            "--stop-price and --limit-price are required for a stop-limit order"
        )
    return StopLimitOrderRequest(
        account_id=account,
        symbol=symbol,
        quantity=qty,
        side=side,
        time_in_force=tif,
        stop_price=stop_price,
        limit_price=limit_price,
    )


def _show_preview(cli: CLIContext, conf: Any, req: OrderRequest) -> None:
    """Render the confirm preview panel from an OrderConfirmation model."""

    def _f(v: Any) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    panel = panel_order_preview(
        account=req.account_id,
        symbol=req.symbol,
        side=req.side.value,
        qty=format(req.quantity, "g"),
        order_type=req.order_type.value,
        tif=req.time_in_force.value,
        est_cost=_f(conf.estimated_cost),
        commission=_f(conf.estimated_commission or conf.commission),
        route=conf.route or req.route,
        warnings=[conf.summary_message] if conf.summary_message else None,
    )
    cli.console.print(panel)


# ---------------------------------------------------------------------------
# D8 — routes
# ---------------------------------------------------------------------------


@app.command(name="routes")
def routes_cmd(ctx: typer.Context) -> None:
    """List available execution routes.

    Maps to: D8 — ``GET /v3/orderexecution/routes``
    """
    cli = CLIContext.from_typer(ctx)
    routes = _run(cli, cli.client.order_execution.list_routes())
    if cli.output_mode == OutputMode.TABLE:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cli.console.print(render_banner("Routes", f"{len(routes)}", cli.environment.value, now))
        cli.console.print(table_routes([r.model_dump(by_alias=True) for r in routes]))
    else:
        for r in routes:
            sys.stdout.write(json.dumps(r.model_dump(by_alias=False), default=str) + "\n")


# ---------------------------------------------------------------------------
# D7 — triggers
# ---------------------------------------------------------------------------


@app.command(name="triggers")
def triggers_cmd(ctx: typer.Context) -> None:
    """List available conditional activation triggers.

    Maps to: D7 — ``GET /v3/orderexecution/activationtriggers``
    """
    cli = CLIContext.from_typer(ctx)
    triggers = _run(cli, cli.client.order_execution.list_activation_triggers())
    if cli.output_mode == OutputMode.TABLE:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cli.console.print(
            render_banner("Activation Triggers", f"{len(triggers)}", cli.environment.value, now)
        )
        tbl = Table(box=box.ROUNDED, header_style="ts.header")
        tbl.add_column("Key", style="ts.mono")
        tbl.add_column("Name", style="ts.symbol")
        tbl.add_column("Description")
        for t in triggers:
            tbl.add_row(t.key or "", t.name or "", t.description or "")
        cli.console.print(tbl)
    else:
        for t in triggers:
            sys.stdout.write(json.dumps(t.model_dump(by_alias=False), default=str) + "\n")


# ---------------------------------------------------------------------------
# Shared order-construction options
# ---------------------------------------------------------------------------

_AccountOpt = Annotated[str, typer.Option("--account", "-a", help="Account ID.")]
_SymbolOpt = Annotated[str, typer.Option("--symbol", "-s", help="Symbol (e.g. AAPL, @ES, BTCUSD).")]
_SideOpt = Annotated[
    Side,
    typer.Option("--side", case_sensitive=False, help="buy / sell / sell_short / buy_to_cover."),
]
_TypeOpt = Annotated[
    OrderType,
    typer.Option("--type", case_sensitive=False, help="market / limit / stop_market / stop_limit."),
]
_QtyOpt = Annotated[float, typer.Option("--qty", "-q", help="Quantity (fractional OK for crypto).")]
_TifOpt = Annotated[TimeInForce, typer.Option("--tif", case_sensitive=False, help="Time in force.")]
_LimitOpt = Annotated[float | None, typer.Option("--limit-price", help="Limit price.")]
_StopOpt = Annotated[float | None, typer.Option("--stop-price", help="Stop price.")]


# ---------------------------------------------------------------------------
# D1 — confirm (preview)
# ---------------------------------------------------------------------------


@app.command(name="confirm")
def confirm_cmd(
    ctx: typer.Context,
    account: _AccountOpt,
    symbol: _SymbolOpt,
    side: _SideOpt,
    qty: _QtyOpt,
    order_type: _TypeOpt = OrderType.MARKET,
    tif: _TifOpt = TimeInForce.DAY,
    limit_price: _LimitOpt = None,
    stop_price: _StopOpt = None,
) -> None:
    """Preview an order (fees + buying-power impact) WITHOUT submitting.

    Maps to: D1 — ``POST /v3/orderexecution/orderconfirm``
    """
    cli = CLIContext.from_typer(ctx)
    req = _build_request(
        account=account,
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        tif=tif,
        limit_price=limit_price,
        stop_price=stop_price,
    )
    confs = _run(cli, cli.client.order_execution.confirm_order(req))
    if not confs:
        cli.console.print("[ts.warn]No confirmation returned.[/ts.warn]")
        raise typer.Exit(code=1)
    if cli.output_mode == OutputMode.TABLE:
        _show_preview(cli, confs[0], req)
    else:
        sys.stdout.write(json.dumps(confs[0].model_dump(by_alias=False), default=str) + "\n")


# ---------------------------------------------------------------------------
# D2 — place (preview + confirm)
# ---------------------------------------------------------------------------


@app.command(name="place")
def place_cmd(
    ctx: typer.Context,
    account: _AccountOpt,
    symbol: _SymbolOpt,
    side: _SideOpt,
    qty: _QtyOpt,
    order_type: _TypeOpt = OrderType.MARKET,
    tif: _TifOpt = TimeInForce.DAY,
    limit_price: _LimitOpt = None,
    stop_price: _StopOpt = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only; never submit.")] = False,
) -> None:
    """Submit a single order. Always previews + prompts first (unless --yes).

    Maps to: D2 — ``POST /v3/orderexecution/orders``

    ``--dry-run`` runs the confirm preview and exits without submitting.
    """
    cli = CLIContext.from_typer(ctx)
    req = _build_request(
        account=account,
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        tif=tif,
        limit_price=limit_price,
        stop_price=stop_price,
    )
    # Always preview first.
    confs = _run(cli, cli.client.order_execution.confirm_order(req))
    if confs:
        _show_preview(cli, confs[0], req)

    if dry_run:
        cli.console.print("[ts.muted](dry-run — not submitted)[/ts.muted]")
        return

    if not cli.yes:
        confirmed = typer.confirm("Submit this order?", default=False)
        if not confirmed:
            cli.console.print("[ts.warn]Aborted — order not submitted.[/ts.warn]")
            raise typer.Exit(code=0)

    resp = _run(cli, cli.client.order_execution.place_order(req))
    if resp.rejected:
        for o in resp.orders:
            if o.error:
                cli.console.print(f"[ts.bad]✖ Rejected: {o.error} — {o.message}[/ts.bad]")
        raise typer.Exit(code=6)
    for o in resp.orders:
        cli.console.print(f"[ts.ok]✔ Order {o.order_id}: {o.message}[/ts.ok]")


# ---------------------------------------------------------------------------
# D4 — cancel
# ---------------------------------------------------------------------------


@app.command(name="cancel")
def cancel_cmd(
    ctx: typer.Context,
    order_id: Annotated[str, typer.Argument(help="Order ID to cancel.")],
) -> None:
    """Cancel a working order. Requires typing the order ID to confirm.

    Maps to: D4 — ``DELETE /v3/orderexecution/orders/{orderID}``
    """
    cli = CLIContext.from_typer(ctx)
    if not cli.yes:
        typed = typer.prompt(f"Type the order ID ({order_id}) to confirm cancellation")
        if typed.strip() != order_id:
            cli.console.print("[ts.warn]Mismatch — cancellation aborted.[/ts.warn]")
            raise typer.Exit(code=0)
    resp = _run(cli, cli.client.order_execution.cancel_order(order_id))
    for o in resp.orders:
        cli.console.print(f"[ts.ok]✔ {o.order_id}: {o.message or 'cancelled'}[/ts.ok]")


# ---------------------------------------------------------------------------
# D3 — replace
# ---------------------------------------------------------------------------


@app.command(name="replace")
def replace_cmd(
    ctx: typer.Context,
    order_id: Annotated[str, typer.Argument(help="Order ID to replace.")],
    account: _AccountOpt,
    symbol: _SymbolOpt,
    side: _SideOpt,
    qty: _QtyOpt,
    order_type: _TypeOpt = OrderType.LIMIT,
    tif: _TifOpt = TimeInForce.DAY,
    limit_price: _LimitOpt = None,
    stop_price: _StopOpt = None,
) -> None:
    """Replace (modify) a working order.

    Maps to: D3 — ``PUT /v3/orderexecution/orders/{orderID}``
    """
    cli = CLIContext.from_typer(ctx)
    req = _build_request(
        account=account,
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        tif=tif,
        limit_price=limit_price,
        stop_price=stop_price,
    )
    resp = _run(cli, cli.client.order_execution.replace_order(order_id, req))
    for o in resp.orders:
        cli.console.print(f"[ts.ok]✔ {o.order_id}: {o.message or 'replaced'}[/ts.ok]")


# ---------------------------------------------------------------------------
# D5 / D6 — grouped orders (OCO / bracket / OSO)
# ---------------------------------------------------------------------------

group_app = typer.Typer(
    name="group",
    help="[bold]Grouped orders[/bold] (OCO / bracket / OSO): confirm, place.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(group_app, name="group")

_E = TypeVar("_E", bound=Enum)


def _enum_lookup(enum_cls: type[_E], value: Any) -> _E:
    """Resolve *value* to an enum member by name or value, case-insensitively."""
    s = str(value).strip().lower()
    for member in enum_cls:
        if s in (str(member.value).lower(), member.name.lower()):
            return member
    choices = ", ".join(str(m.value) for m in enum_cls)
    raise typer.BadParameter(f"invalid {enum_cls.__name__} {value!r} (choices: {choices})")


def _load_group_spec(file: Path | None, json_str: str | None) -> dict[str, Any]:
    """Load a group-order spec from a JSON file, a --json string, or stdin."""
    if file is not None:
        text = file.read_text()
    elif json_str is not None:
        text = json_str
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise typer.BadParameter("provide --file, --json, or pipe a JSON spec on stdin")
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON: {exc}") from None
    if not isinstance(spec, dict):
        raise typer.BadParameter("group spec must be a JSON object")
    return spec


def _build_group_request(spec: dict[str, Any]) -> OrderGroupRequest:
    """Build an :class:`OrderGroupRequest` from a JSON spec dict.

    Spec shape::

        {
            "type": "OCO",
            "orders": [
                {
                    "account": "...",
                    "symbol": "AAPL",
                    "side": "sell",
                    "type": "limit",
                    "qty": 1,
                    "limit_price": 200,
                    "tif": "GTC",
                },
                ...,
            ],
        }
    """
    group_type = str(spec.get("type") or spec.get("group_type") or "OCO").upper()
    raw_orders = spec.get("orders") or []
    if not isinstance(raw_orders, list) or not raw_orders:
        raise typer.BadParameter("group spec must contain a non-empty 'orders' list")
    orders: list[OrderRequest] = []
    for i, o in enumerate(raw_orders):
        if not isinstance(o, dict):
            raise typer.BadParameter(f"orders[{i}] must be an object")
        try:
            orders.append(
                _build_request(
                    account=str(o["account"]),
                    symbol=str(o["symbol"]),
                    side=_enum_lookup(Side, o["side"]),
                    order_type=_enum_lookup(OrderType, o.get("type", "market")),
                    qty=float(o["qty"]),
                    tif=_enum_lookup(TimeInForce, o["tif"]) if o.get("tif") else TimeInForce.DAY,
                    limit_price=float(o["limit_price"])
                    if o.get("limit_price") is not None
                    else None,
                    stop_price=float(o["stop_price"]) if o.get("stop_price") is not None else None,
                )
            )
        except KeyError as exc:
            raise typer.BadParameter(f"orders[{i}] missing required field {exc}") from None
    return OrderGroupRequest(group_type=group_type, orders=orders)


_GroupFileOpt = Annotated[
    Path | None,
    typer.Option("--file", "-f", exists=True, readable=True, help="JSON group-order spec file."),
]
_GroupJsonOpt = Annotated[str | None, typer.Option("--json", help="Inline JSON group-order spec.")]


@group_app.command(name="confirm")
def group_confirm_cmd(
    ctx: typer.Context,
    file: _GroupFileOpt = None,
    json_str: _GroupJsonOpt = None,
) -> None:
    """Preview a grouped order (OCO / bracket / OSO) without submitting.

    Maps to: D5 — ``POST /v3/orderexecution/ordergroupconfirm``

    Reads a JSON spec from ``--file``, ``--json``, or stdin. Example spec::

        {
            "type": "OCO",
            "orders": [
                {
                    "account": "11111111",
                    "symbol": "AAPL",
                    "side": "sell",
                    "type": "limit",
                    "qty": 1,
                    "limit_price": 200,
                },
                {
                    "account": "11111111",
                    "symbol": "AAPL",
                    "side": "sell",
                    "type": "stop_market",
                    "qty": 1,
                    "stop_price": 170,
                },
            ],
        }
    """
    cli = CLIContext.from_typer(ctx)
    req = _build_group_request(_load_group_spec(file, json_str))
    confs = _run(cli, cli.client.order_execution.confirm_order_group(req))
    if cli.output_mode == OutputMode.TABLE:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cli.console.print(
            render_banner(
                f"Group {req.group_type}", f"{len(req.orders)} legs", cli.environment.value, now
            )
        )
        for conf, child in zip(confs, req.orders, strict=False):
            _show_preview(cli, conf, child)
    else:
        for conf in confs:
            sys.stdout.write(json.dumps(conf.model_dump(by_alias=False), default=str) + "\n")


@group_app.command(name="place")
def group_place_cmd(
    ctx: typer.Context,
    file: _GroupFileOpt = None,
    json_str: _GroupJsonOpt = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only; never submit.")] = False,
) -> None:
    """Submit a grouped order (OCO / bracket / OSO). Previews + prompts first.

    Maps to: D6 — ``POST /v3/orderexecution/ordergroups``

    Reads the same JSON spec as ``ts order group confirm`` (``--file`` / ``--json`` / stdin).
    """
    cli = CLIContext.from_typer(ctx)
    req = _build_group_request(_load_group_spec(file, json_str))

    confs = _run(cli, cli.client.order_execution.confirm_order_group(req))
    if cli.output_mode == OutputMode.TABLE:
        for conf, child in zip(confs, req.orders, strict=False):
            _show_preview(cli, conf, child)

    if dry_run:
        cli.console.print("[ts.muted](dry-run — not submitted)[/ts.muted]")
        return

    prompt = f"Submit this {req.group_type} group of {len(req.orders)} orders?"
    if not cli.yes and not typer.confirm(prompt, default=False):
        cli.console.print("[ts.warn]Aborted — group not submitted.[/ts.warn]")
        raise typer.Exit(code=0)

    resp = _run(cli, cli.client.order_execution.place_order_group(req))
    if resp.rejected:
        for o in resp.orders:
            if o.error:
                cli.console.print(f"[ts.bad]✖ Rejected: {o.error} — {o.message}[/ts.bad]")
        raise typer.Exit(code=6)
    for o in resp.orders:
        cli.console.print(f"[ts.ok]✔ Order {o.order_id}: {o.message}[/ts.ok]")
