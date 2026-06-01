"""``ts md`` command group — market data.

Subcommands:
    quotes   — snapshot quotes for one or more symbols (B2)
    bars     — historical bar chart data (B1) [stub]
    symbols  — symbol metadata (B3) [stub]
    ...

See docs/03-endpoint-inventory.md §"B. MarketData".
See docs/04-cli-design.md §"Section B — MarketData".
See docs/07-output-style.md for table/banner conventions.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import typer

from tradestation.cli.ctx import CLIContext, OutputMode
from tradestation.cli.render import banner as render_banner
from tradestation.cli.render import render_error, render_jsonl, table_quotes

app = typer.Typer(
    name="md",
    help="[bold]Market data[/bold]: quotes, bars, option chains, streaming.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# B2 — quotes
# ---------------------------------------------------------------------------


@app.command(name="quotes")
def quotes_cmd(
    ctx: typer.Context,
    symbols: Annotated[
        list[str] | None,
        typer.Argument(help="Symbols to quote (e.g. AAPL MSFT BTCUSD, or comma-separated)."),
    ] = None,
    files: Annotated[
        list[Path] | None,
        typer.Option(
            "-f",
            "--file",
            help="File with one symbol per line.",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Fetch quote snapshots for one or more symbols.

    Maps to: B2 — ``GET /v3/marketdata/quotes/{symbols}``

    Accepts positional symbols, comma-separated form, or ``-f file`` (one symbol per line).

    Examples::

        ts md quotes AAPL MSFT NVDA
        ts md quotes AAPL,MSFT,NVDA
        ts md quotes @ES BTCUSD
        ts md quotes -f watchlist.txt
        ts md quotes AAPL --output json
    """
    cli = CLIContext.from_typer(ctx)

    # Collect and normalise symbols
    all_syms: list[str] = []
    for raw in symbols or []:
        for part in raw.split(","):
            s = part.strip()
            if s:
                all_syms.append(s)
    for file_path in files or []:
        for line in file_path.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                all_syms.append(s)

    if not all_syms:
        cli.console.print("[ts.warn]No symbols specified. Pass at least one symbol.[/ts.warn]")
        raise typer.Exit(code=2)

    # Fetch
    try:
        ts = cli.client
        quotes = asyncio.run(ts.market_data.get_quotes(all_syms))
    except Exception as exc:
        render_error(exc, console=cli.console, verbose=cli.verbose)
        raise typer.Exit(code=_exit_code(exc)) from exc

    # Render
    mode = cli.output_mode
    n = len(quotes)
    env_label = cli.environment.value

    if mode == OutputMode.TABLE:
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S")
        banner_text = render_banner(
            "Quotes",
            f"{n} symbol{'s' if n != 1 else ''}",
            env_label,
            now_utc,
        )
        cli.console.print(banner_text)
        # Convert Quote models → dicts for the existing table_quotes renderer
        raw_dicts = [_quote_to_render_dict(q) for q in quotes]
        tbl = table_quotes(raw_dicts)
        cli.console.print(tbl)

    elif mode == OutputMode.JSON:
        data = [q.model_dump(by_alias=False) for q in quotes]
        sys.stdout.write(json.dumps(data, default=str) + "\n")

    elif mode == OutputMode.JSONL:
        for q in quotes:
            sys.stdout.write(json.dumps(q.model_dump(by_alias=False), default=str) + "\n")

    elif mode == OutputMode.CSV:
        _render_csv(quotes, delimiter=",", console=cli.console)

    elif mode == OutputMode.TSV:
        _render_csv(quotes, delimiter="\t", console=cli.console)

    else:
        # YAML fallback
        try:
            import yaml  # type: ignore[import-untyped]

            data_yaml = [q.model_dump(by_alias=False) for q in quotes]
            cli.console.print(yaml.safe_dump(data_yaml, default_flow_style=False))
        except ImportError:
            render_jsonl([q.model_dump(by_alias=False) for q in quotes], console=cli.console)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quote_to_render_dict(q: object) -> dict[str, object]:
    """Convert a Quote model to the PascalCase dict expected by table_quotes."""
    from tradestation.models.market_data import Quote

    assert isinstance(q, Quote)
    mf: dict[str, object] = {}
    if q.market_flags is not None:
        mf = {
            "IsHalted": q.market_flags.is_halted or False,
            "IsDelayed": q.market_flags.is_delayed or False,
        }
    return {
        "Symbol": q.symbol,
        "Last": str(q.last) if q.last is not None else "",
        "NetChange": str(q.net_change) if q.net_change is not None else "0",
        "NetChangePct": str(q.net_change_pct) if q.net_change_pct is not None else "0",
        "Bid": str(q.bid) if q.bid is not None else "",
        "BidSize": str(q.bid_size) if q.bid_size is not None else "",
        "Ask": str(q.ask) if q.ask is not None else "",
        "AskSize": str(q.ask_size) if q.ask_size is not None else "",
        "Volume": str(q.volume) if q.volume is not None else "0",
        "Open": str(q.open) if q.open is not None else "",
        "High": str(q.high) if q.high is not None else "",
        "Low": str(q.low) if q.low is not None else "",
        "MarketFlags": mf,
        "TradeTime": q.trade_time or "",
    }


def _render_csv(quotes: Sequence[object], *, delimiter: str, console: object) -> None:
    """Render quotes as CSV/TSV to stdout (bypassing Rich for clean piping)."""
    from tradestation.models.market_data import Quote

    fields = [
        "symbol",
        "last",
        "net_change",
        "net_change_pct",
        "bid",
        "bid_size",
        "ask",
        "ask_size",
        "volume",
        "open",
        "high",
        "low",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    writer.writerow(fields)
    for q in quotes:
        assert isinstance(q, Quote)
        writer.writerow(
            [
                q.symbol,
                q.last,
                q.net_change,
                q.net_change_pct,
                q.bid,
                q.bid_size,
                q.ask,
                q.ask_size,
                q.volume,
                q.open,
                q.high,
                q.low,
            ]
        )
    sys.stdout.write(buf.getvalue())


def _exit_code(exc: Exception) -> int:
    """Map exception type to CLI exit code."""
    from tradestation.errors import (
        ApiError,
        AuthError,
        NetworkError,
        OrderRejectedError,
        RateLimitError,
    )

    if isinstance(exc, (AuthError,)):
        return 3
    if isinstance(exc, RateLimitError):
        return 4
    if isinstance(exc, ApiError):
        return 5
    if isinstance(exc, OrderRejectedError):
        return 6
    if isinstance(exc, NetworkError):
        return 1
    return 1


# ---------------------------------------------------------------------------
# B1 — bars
# ---------------------------------------------------------------------------


def _run_md(cli: CLIContext, coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except Exception as exc:
        render_error(exc, console=cli.console, verbose=cli.verbose)
        raise typer.Exit(code=_exit_code(exc)) from exc


@app.command(name="bars")
def bars_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Symbol (e.g. AAPL, @ES, BTCUSD).")],
    interval: Annotated[int, typer.Option("--interval", help="Bar interval.")] = 1,
    unit: Annotated[str, typer.Option("--unit", help="Minute/Daily/Weekly/Monthly.")] = "Minute",
    barsback: Annotated[int, typer.Option("--barsback", help="Number of bars back.")] = 50,
) -> None:
    """Historical bar chart data.

    Maps to: B1 — ``GET /v3/marketdata/barcharts/{symbol}``

    Examples::

        ts md bars AAPL --barsback 100
        ts md bars @ES --unit Daily --barsback 30
    """
    from tradestation.enums import BarUnit

    cli = CLIContext.from_typer(ctx)
    bars = _run_md(
        cli,
        cli.client.market_data.get_bars(
            symbol, interval=interval, unit=BarUnit(unit), barsback=barsback
        ),
    )
    if cli.output_mode == OutputMode.TABLE:
        from rich import box
        from rich.table import Table

        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cli.console.print(
            render_banner(f"Bars {symbol}", f"{len(bars)} bars", cli.environment.value, now)
        )
        tbl = Table(box=box.ROUNDED, header_style="ts.header")
        for col in ("Time", "Open", "High", "Low", "Close", "Volume"):
            tbl.add_column(
                col,
                justify="right" if col != "Time" else "left",
                style="ts.price" if col not in ("Time", "Volume") else None,
            )
        for b in bars:
            tbl.add_row(
                (b.timestamp or "")[:19].replace("T", " "),
                f"{b.open:,.2f}" if b.open else "",
                f"{b.high:,.2f}" if b.high else "",
                f"{b.low:,.2f}" if b.low else "",
                f"{b.close:,.2f}" if b.close else "",
                f"{b.total_volume:,}" if b.total_volume else "",
            )
        cli.console.print(tbl)
    else:
        for b in bars:
            sys.stdout.write(json.dumps(b.model_dump(by_alias=False), default=str) + "\n")


@app.command(name="symbols")
def symbols_cmd(
    ctx: typer.Context,
    symbols: Annotated[list[str], typer.Argument(help="Symbol(s).")],
) -> None:
    """Symbol metadata.

    Maps to: B3 — ``GET /v3/marketdata/symbols/{symbols}``
    """
    cli = CLIContext.from_typer(ctx)
    syms = [s.strip() for raw in symbols for s in raw.split(",") if s.strip()]
    result = _run_md(cli, cli.client.market_data.get_symbols(syms))
    if cli.output_mode == OutputMode.TABLE:
        from tradestation.cli.render import panel_symbol_detail

        for s in result:
            cli.console.print(panel_symbol_detail(s.model_dump(by_alias=True)))
    else:
        for s in result:
            sys.stdout.write(json.dumps(s.model_dump(by_alias=False), default=str) + "\n")


crypto_app = typer.Typer(name="crypto", help="Crypto market data.", no_args_is_help=True)
options_app = typer.Typer(name="options", help="Options market data.", no_args_is_help=True)
app.add_typer(crypto_app, name="crypto")
app.add_typer(options_app, name="options")


@crypto_app.command(name="pairs")
def crypto_pairs_cmd(ctx: typer.Context) -> None:
    """List supported crypto trading pairs.

    Maps to: B7 — ``GET /v3/marketdata/symbollists/cryptopairs/symbolnames``
    """
    cli = CLIContext.from_typer(ctx)
    pairs = _run_md(cli, cli.client.market_data.list_crypto_pairs())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print("[ts.symbol]" + "  ".join(pairs) + "[/ts.symbol]")
    else:
        sys.stdout.write(json.dumps(pairs) + "\n")


@options_app.command(name="expirations")
def opt_expirations_cmd(
    ctx: typer.Context,
    underlying: Annotated[str, typer.Argument(help="Underlying symbol.")],
) -> None:
    """List option expiration dates for an underlying.

    Maps to: B8 — ``GET /v3/marketdata/options/expirations/{underlying}``
    """
    cli = CLIContext.from_typer(ctx)
    exps = _run_md(cli, cli.client.market_data.get_option_expirations(underlying))
    if cli.output_mode == OutputMode.TABLE:
        from rich import box
        from rich.table import Table

        tbl = Table(box=box.ROUNDED, header_style="ts.header")
        tbl.add_column("Date")
        tbl.add_column("Type")
        for e in exps:
            tbl.add_row((e.date or "")[:10], e.type or "")
        cli.console.print(tbl)
    else:
        for e in exps:
            sys.stdout.write(json.dumps(e.model_dump(by_alias=False), default=str) + "\n")


@options_app.command(name="spread-types")
def opt_spread_types_cmd(ctx: typer.Context) -> None:
    """List supported option spread types.

    Maps to: B10 — ``GET /v3/marketdata/options/spreadtypes``
    """
    cli = CLIContext.from_typer(ctx)
    types = _run_md(cli, cli.client.market_data.list_option_spread_types())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print("[ts.symbol]" + "  ".join(t.name or "" for t in types) + "[/ts.symbol]")
    else:
        for t in types:
            sys.stdout.write(json.dumps(t.model_dump(by_alias=False), default=str) + "\n")


# ---------------------------------------------------------------------------
# Streaming (B12-B17) — `ts md stream ...`
# ---------------------------------------------------------------------------

stream_app = typer.Typer(name="stream", help="Live streaming market data.", no_args_is_help=True)
app.add_typer(stream_app, name="stream")


async def _consume_stream(
    cli: CLIContext, agen: Any, *, max_frames: int, for_seconds: float
) -> int:
    """Print stream events as they arrive, bounded by --max / --for. Returns count."""
    import contextlib

    count = 0
    loop = asyncio.get_event_loop()
    deadline = loop.time() + for_seconds if for_seconds > 0 else None
    with contextlib.suppress(KeyboardInterrupt):
        async for ev in agen:
            data = ev.raw or {}
            if cli.output_mode == OutputMode.TABLE:
                sym = data.get("Symbol") or data.get("OrderID") or ""
                cli.console.print(f"[ts.symbol]{sym}[/ts.symbol]  {json.dumps(data, default=str)}")
            else:
                sys.stdout.write(json.dumps(data, default=str) + "\n")
                sys.stdout.flush()
            count += 1
            if max_frames and count >= max_frames:
                break
            if deadline and loop.time() >= deadline:
                break
    return count


_MaxOpt = Annotated[int, typer.Option("--max", help="Stop after N frames (0 = unlimited).")]
_ForOpt = Annotated[float, typer.Option("--for", help="Stop after N seconds (0 = unlimited).")]


@stream_app.command(name="quotes")
def stream_quotes_cmd(
    ctx: typer.Context,
    symbols: Annotated[list[str], typer.Argument(help="Symbol(s).")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live quote updates. Ctrl-C to stop.

    Maps to: B13 — ``GET /v3/marketdata/stream/quotes/{symbols}``
    """
    cli = CLIContext.from_typer(ctx)
    syms = [s.strip() for raw in symbols for s in raw.split(",") if s.strip()]

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_quotes(syms),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")


@stream_app.command(name="bars")
def stream_bars_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Symbol.")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live bar updates. Ctrl-C to stop.

    Maps to: B12 — ``GET /v3/marketdata/stream/barcharts/{symbol}``
    """
    cli = CLIContext.from_typer(ctx)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_bars(symbol),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")
