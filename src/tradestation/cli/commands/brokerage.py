"""``ts brokerage`` command group — account data (C1-C9).

Subcommands:
    accounts    — list accounts (C1)
    balances    — real-time balances (C2)
    bod         — beginning-of-day balances (C3)
    positions   — open positions (C4)
    orders      — today's orders (C5)
    order       — specific order(s) by ID (C6)
    historical  — historical orders since a date (C7)
    wallets     — crypto wallets (C9)

See docs/03-endpoint-inventory.md §"C. Brokerage".
See docs/04-cli-design.md §"Section C — Brokerage".
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
from typing import Annotated, Any

import typer
from pydantic import BaseModel
from rich.table import Table

from tradestation.cli.ctx import CLIContext, OutputMode
from tradestation.cli.render import (
    banner as render_banner,
)
from tradestation.cli.render import (
    render_error,
    table_accounts,
    table_balances,
    table_orders,
    table_positions,
)

app = typer.Typer(
    name="brokerage",
    help="[bold]Account data[/bold]: balances, positions, orders, wallets.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _exit_code(exc: Exception) -> int:
    from tradestation.errors import (
        ApiError,
        AuthError,
        NoCredentialsError,
        RateLimitError,
    )

    if isinstance(exc, (AuthError, NoCredentialsError)):
        return 3
    if isinstance(exc, RateLimitError):
        return 4
    if isinstance(exc, ApiError):
        return 5
    return 1


def _split_ids(raw: Sequence[str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        for part in item.split(","):
            s = part.strip()
            if s:
                out.append(s)
    return out


def _emit(
    cli: CLIContext,
    models: Sequence[BaseModel],
    *,
    table_fn: Callable[[Sequence[dict[str, Any]]], Table] | None,
    operation: str,
    scope: str,
) -> None:
    """Render a list of models per the active output mode."""
    mode = cli.output_mode
    if mode == OutputMode.TABLE and table_fn is not None:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cli.console.print(render_banner(operation, scope, cli.environment.value, now))
        rows = [m.model_dump(by_alias=True) for m in models]
        cli.console.print(table_fn(rows))
        if not models:
            cli.console.print("[ts.muted](none)[/ts.muted]")
    elif mode in (OutputMode.JSON,):
        data = [m.model_dump(by_alias=False) for m in models]
        sys.stdout.write(json.dumps(data, default=str) + "\n")
    elif mode in (OutputMode.CSV, OutputMode.TSV):
        delim = "," if mode == OutputMode.CSV else "\t"
        rows = [m.model_dump(by_alias=False) for m in models]
        if rows:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=delim)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: ("" if v is None else v) for k, v in r.items()})
            sys.stdout.write(buf.getvalue())
    elif mode == OutputMode.YAML:
        try:
            import yaml  # type: ignore[import-untyped]

            sys.stdout.write(yaml.safe_dump([m.model_dump(by_alias=False) for m in models]))
        except ImportError:
            for m in models:
                sys.stdout.write(json.dumps(m.model_dump(by_alias=False), default=str) + "\n")
    else:  # JSONL (default when piped)
        for m in models:
            sys.stdout.write(json.dumps(m.model_dump(by_alias=False), default=str) + "\n")


def _run(cli: CLIContext, coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except Exception as exc:
        render_error(exc, console=cli.console, verbose=cli.verbose)
        raise typer.Exit(code=_exit_code(exc)) from exc


# ---------------------------------------------------------------------------
# C1 — accounts
# ---------------------------------------------------------------------------


@app.command(name="accounts")
def accounts_cmd(ctx: typer.Context) -> None:
    """List all brokerage accounts.

    Maps to: C1 — ``GET /v3/brokerage/accounts``

    Examples::

        ts brokerage accounts
        ts brokerage accounts --output json
    """
    cli = CLIContext.from_typer(ctx)
    accounts = _run(cli, cli.client.brokerage.list_accounts())

    # C1 returns account metadata only — Equity / BuyingPower live on the C2
    # balances endpoint. Enrich each account with its balance so the combined
    # view shows real figures instead of zeros. Best-effort: if balances can't
    # be fetched, the accounts still render (with Equity/BuyingPower blank).
    ids = [a.account_id for a in accounts if a.account_id]
    if ids:
        try:
            balances = _run(cli, cli.client.brokerage.get_balances(ids))
            by_id = {b.account_id: b for b in balances}
            accounts = [
                a.model_copy(update={"equity": bal.equity, "buying_power": bal.buying_power})
                if (bal := by_id.get(a.account_id)) is not None
                else a
                for a in accounts
            ]
        except Exception as exc:
            if cli.verbose:
                cli.console.print(
                    f"[ts.muted](could not fetch balances for accounts view: {exc})[/ts.muted]"
                )

    _emit(
        cli,
        accounts,
        table_fn=table_accounts,
        operation="Accounts",
        scope=f"{len(accounts)} account{'s' if len(accounts) != 1 else ''}",
    )


# ---------------------------------------------------------------------------
# C2 / C3 — balances
# ---------------------------------------------------------------------------


@app.command(name="balances")
def balances_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
) -> None:
    """Fetch real-time balances for one or more accounts.

    Maps to: C2 — ``GET /v3/brokerage/accounts/{accountIDs}/balances``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    balances = _run(cli, cli.client.brokerage.get_balances(ids))
    _emit(cli, balances, table_fn=table_balances, operation="Balances", scope=",".join(ids))


@app.command(name="bod")
def bod_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
) -> None:
    """Fetch beginning-of-day balances.

    Maps to: C3 — ``GET /v3/brokerage/accounts/{accountIDs}/bodbalances``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    balances = _run(cli, cli.client.brokerage.get_bod_balances(ids))
    _emit(cli, balances, table_fn=table_balances, operation="BOD Balances", scope=",".join(ids))


# ---------------------------------------------------------------------------
# C4 — positions
# ---------------------------------------------------------------------------


@app.command(name="positions")
def positions_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
) -> None:
    """Fetch open positions.

    Maps to: C4 — ``GET /v3/brokerage/accounts/{accountIDs}/positions``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    positions = _run(cli, cli.client.brokerage.get_positions(ids))
    _emit(
        cli,
        positions,
        table_fn=table_positions,
        operation="Positions",
        scope=f"{len(positions)} open",
    )


# ---------------------------------------------------------------------------
# C5 / C6 — orders
# ---------------------------------------------------------------------------


@app.command(name="orders")
def orders_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
) -> None:
    """Fetch today's orders.

    Maps to: C5 — ``GET /v3/brokerage/accounts/{accountIDs}/orders``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    orders = _run(cli, cli.client.brokerage.get_orders(ids))
    _emit(cli, orders, table_fn=table_orders, operation="Orders", scope=",".join(ids))


@app.command(name="order")
def order_cmd(
    ctx: typer.Context,
    account_id: Annotated[str, typer.Argument(help="Account ID.")],
    order_ids: Annotated[list[str], typer.Argument(help="Order ID(s).")],
) -> None:
    """Fetch specific order(s) by ID.

    Maps to: C6 — ``GET /v3/brokerage/accounts/{accountIDs}/orders/{orderIDs}``
    """
    cli = CLIContext.from_typer(ctx)
    oids = _split_ids(order_ids)
    orders = _run(cli, cli.client.brokerage.get_orders_by_id([account_id], oids))
    _emit(cli, orders, table_fn=table_orders, operation="Order", scope=",".join(oids))


# ---------------------------------------------------------------------------
# C7 — historical orders
# ---------------------------------------------------------------------------


@app.command(name="historical")
def historical_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
    since: Annotated[
        datetime, typer.Option("--since", help="Start date (YYYY-MM-DD).", formats=["%Y-%m-%d"])
    ],
) -> None:
    """Fetch historical orders since a date.

    Maps to: C7 — ``GET /v3/brokerage/accounts/{accountIDs}/historicalorders``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    since_date: date = since.date()
    orders = _run(cli, cli.client.brokerage.get_historical_orders(ids, since=since_date))
    _emit(
        cli,
        orders,
        table_fn=table_orders,
        operation="Historical Orders",
        scope=f"since {since_date.isoformat()}",
    )


# ---------------------------------------------------------------------------
# C9 — wallets
# ---------------------------------------------------------------------------


def _table_wallets(rows: Sequence[dict[str, Any]]) -> Table:
    from rich import box

    tbl = Table(box=box.ROUNDED, header_style="ts.header")
    tbl.add_column("Account", style="ts.mono")
    tbl.add_column("Currency", justify="center", style="ts.symbol")
    tbl.add_column("Balance", justify="right", style="ts.price")
    tbl.add_column("Avail (Trade)", justify="right", style="ts.price")
    tbl.add_column("Status")
    for w in rows:
        tbl.add_row(
            str(w.get("AccountID", "")),
            str(w.get("Currency", "")),
            str(w.get("Balance", "")),
            str(w.get("BalanceAvailableForTrading", "")),
            str(w.get("Status", "")),
        )
    return tbl


@app.command(name="wallets")
def wallets_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
) -> None:
    """Fetch crypto wallets.

    Maps to: C9 — ``GET /v3/brokerage/accounts/{accountIDs}/wallets``
    """
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)
    wallets = _run(cli, cli.client.brokerage.get_wallets(ids))
    _emit(cli, wallets, table_fn=_table_wallets, operation="Wallets", scope=",".join(ids))


# ---------------------------------------------------------------------------
# Streaming (C10-C13) — `ts brokerage stream ...`
# ---------------------------------------------------------------------------

stream_app = typer.Typer(name="stream", help="Live account streaming.", no_args_is_help=True)
app.add_typer(stream_app, name="stream")

_MaxOpt = Annotated[int, typer.Option("--max", help="Stop after N frames (0 = unlimited).")]
_ForOpt = Annotated[float, typer.Option("--for", help="Stop after N seconds (0 = unlimited).")]


async def _consume(cli: CLIContext, agen: Any, *, max_frames: int, for_seconds: float) -> int:
    import contextlib

    count = 0
    loop = asyncio.get_event_loop()
    deadline = loop.time() + for_seconds if for_seconds > 0 else None
    with contextlib.suppress(KeyboardInterrupt):
        async with contextlib.aclosing(agen) as stream:
            async for ev in stream:
                sys.stdout.write(json.dumps(ev.raw or {}, default=str) + "\n")
                sys.stdout.flush()
                count += 1
                if max_frames and count >= max_frames:
                    break
                if deadline and loop.time() >= deadline:
                    break
    return count


@stream_app.command(name="orders")
def stream_orders_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live order events. Maps to: C10."""
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume(
                cli,
                ts.brokerage.stream_orders(ids),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    _run(cli, _go())


@stream_app.command(name="order")
def stream_order_by_id_cmd(
    ctx: typer.Context,
    account_id: Annotated[str, typer.Argument(help="Account ID.")],
    order_ids: Annotated[list[str], typer.Argument(help="Order ID(s).")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live events for specific orders. Maps to: C11."""
    cli = CLIContext.from_typer(ctx)
    oids = _split_ids(order_ids)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume(
                cli,
                ts.brokerage.stream_orders_by_id([account_id], oids),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    _run(cli, _go())


@stream_app.command(name="positions")
def stream_positions_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live position updates. Maps to: C12."""
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume(
                cli,
                ts.brokerage.stream_positions(ids),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    _run(cli, _go())


@stream_app.command(name="wallets")
def stream_wallets_cmd(
    ctx: typer.Context,
    account_ids: Annotated[list[str], typer.Argument(help="Account ID(s).")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live wallet updates. Maps to: C13."""
    cli = CLIContext.from_typer(ctx)
    ids = _split_ids(account_ids)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume(
                cli,
                ts.brokerage.stream_wallets(ids),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    _run(cli, _go())
