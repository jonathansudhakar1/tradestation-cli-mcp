"""``ts md`` command group — market data.

Subcommands:
    quotes          — snapshot quotes for one or more symbols (B2)
    bars            — historical bar chart data (B1)
    symbols         — symbol metadata (B3)
    crypto pairs    — supported crypto pairs (B7)
    options chain   — full option chain snapshot for an expiration (B16)
    options expirations / spread-types (B8 / B10)
    stream …        — live streaming: quotes, bars, depth, option chain (B12-B17)

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


@options_app.command(name="strikes")
def opt_strikes_cmd(
    ctx: typer.Context,
    underlying: Annotated[str, typer.Argument(help="Underlying symbol.")],
    expiration: Annotated[
        str | None,
        typer.Option("--expiration", "-e", help="Expiration date (YYYY-MM-DD)."),
    ] = None,
    spread_type: Annotated[
        str | None,
        typer.Option("--spread-type", help="Spread type filter (e.g. Single, Vertical)."),
    ] = None,
) -> None:
    """List available strike prices for an underlying.

    Maps to: B9 — ``GET /v3/marketdata/options/strikes/{underlying}``

    Examples::

        ts md options strikes AAPL --expiration 2026-06-19
        ts md options strikes AAPL -e 2026-06-19 --spread-type Vertical
    """
    cli = CLIContext.from_typer(ctx)
    result = _run_md(
        cli,
        cli.client.market_data.get_option_strikes(
            underlying, expiration=expiration, spread_type=spread_type
        ),
    )
    if cli.output_mode != OutputMode.TABLE:
        sys.stdout.write(json.dumps(result, default=str) + "\n")
        return

    groups = result.get("Strikes", []) if isinstance(result, dict) else []
    spread = result.get("SpreadType", "") if isinstance(result, dict) else ""
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    cli.console.print(
        render_banner(
            f"Strikes {underlying}",
            f"{spread or 'Single'}  ·  {len(groups)} strikes"
            + (f"  ·  exp {expiration}" if expiration else ""),
            cli.environment.value,
            now,
        )
    )
    # Each group is a list (one element for single-leg spreads). Render compactly.
    chips = ["·".join(str(s) for s in grp) if isinstance(grp, list) else str(grp) for grp in groups]
    cli.console.print("[ts.price]" + "   ".join(chips) + "[/ts.price]")


@options_app.command(name="risk-reward")
def opt_risk_reward_cmd(
    ctx: typer.Context,
    leg: Annotated[
        list[str] | None,
        typer.Option(
            "--leg",
            help='Leg as "<OCC symbol>,<buy|sell>,<qty>,<openPrice>". Repeatable.',
        ),
    ] = None,
    entry: Annotated[
        float | None,
        typer.Option("--entry", help="Net entry (spread) price."),
    ] = None,
) -> None:
    """Compute risk/reward for a multi-leg option position.

    Maps to: B11 — ``POST /v3/marketdata/options/riskreward``

    Each ``--leg`` is ``<symbol>,<buy|sell>,<qty>,<openPrice>``; sell legs get a
    negative ratio. Example::

        ts md options risk-reward \\
          --leg "AAPL 260619C200,buy,1,5.40" \\
          --leg "AAPL 260619C210,sell,1,2.10" \\
          --entry 3.30
    """
    cli = CLIContext.from_typer(ctx)
    if not leg or entry is None:
        cli.console.print("[ts.bad]✖[/ts.bad] At least one --leg and --entry are required.")
        raise typer.Exit(code=2)

    legs: list[dict[str, Any]] = []
    for spec in leg:
        parts = [p.strip() for p in spec.split(",")]
        if len(parts) != 4:
            cli.console.print(
                f"[ts.bad]✖[/ts.bad] Bad --leg {spec!r}. "
                'Expected "<symbol>,<buy|sell>,<qty>,<openPrice>".'
            )
            raise typer.Exit(code=2)
        sym, side, qty_s, price_s = parts
        try:
            qty = int(qty_s)
        except ValueError:
            cli.console.print(f"[ts.bad]✖[/ts.bad] Bad quantity in --leg {spec!r}.")
            raise typer.Exit(code=2) from None
        ratio = -qty if side.lower().startswith("s") else qty
        legs.append({"Symbol": sym, "Ratio": ratio, "OpenPrice": price_s})

    result = _run_md(cli, cli.client.market_data.option_risk_reward(legs, entry=entry))
    if cli.output_mode != OutputMode.TABLE:
        sys.stdout.write(json.dumps(result, default=str) + "\n")
        return

    from rich import box
    from rich.table import Table

    tbl = Table(box=box.ROUNDED, header_style="ts.header", title="Risk / Reward")
    tbl.add_column("Metric", style="ts.label")
    tbl.add_column("Value", justify="right", style="ts.value")
    if isinstance(result, dict):
        for key, val in result.items():
            tbl.add_row(str(key), str(val))
    cli.console.print(tbl)


# ---------------------------------------------------------------------------
# B16 (snapshot) — `ts md options chain`
# ---------------------------------------------------------------------------

# Column registry for the chain view: key -> (header, raw frame field).
_CHAIN_COLUMNS: dict[str, tuple[str, str]] = {
    "bid": ("Bid", "Bid"),
    "ask": ("Ask", "Ask"),
    "mid": ("Mid", "Mid"),
    "last": ("Last", "Last"),
    "volume": ("Vol", "Volume"),
    "oi": ("OI", "DailyOpenInterest"),
    "iv": ("IV", "ImpliedVolatility"),
    "delta": ("Δ", "Delta"),
    "gamma": ("Γ", "Gamma"),
    "theta": ("Θ", "Theta"),
    "vega": ("Vega", "Vega"),
}
_DEFAULT_CHAIN_COLUMNS = ["bid", "ask", "last", "volume", "oi", "iv", "delta"]


def _fmt_chain_cell(key: str, frame: dict[str, Any] | None) -> str:
    """Format one chain cell for column *key* from a per-strike frame."""
    if not frame:
        return ""
    raw = frame.get(_CHAIN_COLUMNS[key][1])
    if raw is None or raw == "":
        return ""
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if key in ("volume", "oi"):
        return f"{int(x):,}"
    if key == "iv":
        return f"{x * 100:.1f}%" if abs(x) <= 1 else f"{x:.1f}%"
    if key in ("delta", "gamma", "theta", "vega"):
        return f"{x:.3f}"
    return f"{x:,.2f}"


def _resolve_expiration(exps: Sequence[Any], *, date: str | None, dte: int | None) -> str | None:
    """Pick an expiration date string: explicit --date, nearest --dte, or soonest."""
    dates = [str(e.date)[:10] for e in exps if getattr(e, "date", None)]
    if not dates:
        return None
    if date:
        target = date[:10]
        return (
            target
            if target in dates
            else min(dates, key=lambda d: abs(_days_out(d) - _days_out(target)))
        )
    if dte is not None:
        return min(dates, key=lambda d: abs(_days_out(d) - dte))
    # Soonest upcoming expiration (smallest non-negative DTE), else earliest.
    upcoming = [d for d in dates if _days_out(d) >= 0]
    return min(upcoming or dates, key=_days_out)


def _days_out(iso_date: str) -> int:
    """Whole days from today (UTC) to *iso_date* (YYYY-MM-DD). Large if unparsable."""
    try:
        d = datetime.strptime(iso_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 10**6
    return (d.date() - datetime.now(timezone.utc).date()).days


def _assemble_chain(frames: Sequence[dict[str, Any]]) -> dict[float, dict[str, dict[str, Any]]]:
    """Group chain frames into ``{strike: {"Call": frame, "Put": frame}}``."""
    rows: dict[float, dict[str, dict[str, Any]]] = {}
    for f in frames:
        legs = f.get("Legs") or []
        leg = legs[0] if legs else {}
        otype = str(leg.get("OptionType") or f.get("Side") or "").strip().upper()
        side = "Call" if otype.startswith("C") else "Put" if otype.startswith("P") else None
        strike_raw = leg.get("StrikePrice") or (f.get("Strikes") or [None])[0]
        try:
            strike = float(strike_raw)
        except (TypeError, ValueError):
            continue
        if side is None:
            continue
        rows.setdefault(strike, {})[side] = f
    return rows


def _select_strikes(strikes: Sequence[float], *, count: int, atm: float | None) -> list[float]:
    """Return up to *count* strikes, centered on the strike nearest *atm*."""
    ordered = sorted(strikes)
    if count <= 0 or len(ordered) <= count:
        return ordered
    if atm is None:
        return ordered[:count]
    center = min(range(len(ordered)), key=lambda i: abs(ordered[i] - atm))
    lo = max(0, center - count // 2)
    hi = min(len(ordered), lo + count)
    lo = max(0, hi - count)
    return ordered[lo:hi]


@options_app.command(name="chain")
def opt_chain_cmd(
    ctx: typer.Context,
    underlying: Annotated[str, typer.Argument(help="Underlying symbol (e.g. AAPL).")],
    date: Annotated[
        str | None,
        typer.Option("--date", help="Expiration date (YYYY-MM-DD). Default: nearest."),
    ] = None,
    dte: Annotated[
        int | None,
        typer.Option("--dte", help="Target days-to-expiration; picks the nearest expiration."),
    ] = None,
    strikes: Annotated[
        int,
        typer.Option("--strikes", "-n", help="Number of strikes to show, centered on ATM."),
    ] = 20,
    columns: Annotated[
        str | None,
        typer.Option(
            "--columns",
            help=(
                "Comma-separated columns per side. Choices: "
                + ",".join(_CHAIN_COLUMNS)
                + f". Default: {','.join(_DEFAULT_CHAIN_COLUMNS)}."
            ),
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Max seconds to collect the chain snapshot."),
    ] = 10.0,
) -> None:
    """Show a full option chain (calls │ strike │ puts) for one expiration.

    Maps to: B16 — ``GET /v3/marketdata/stream/options/chains/{underlying}``
    (collected into a one-shot snapshot). Picks the nearest expiration by
    default; use ``--date`` for a specific date or ``--dte`` for a target DTE.

    Examples::

        ts md options chain AAPL
        ts md options chain AAPL --dte 30 --strikes 16
        ts md options chain SPY --date 2026-06-19 --columns bid,ask,iv,delta
    """
    cli = CLIContext.from_typer(ctx)

    # 1. Resolve which expiration to show.
    exps = _run_md(cli, cli.client.market_data.get_option_expirations(underlying))
    expiration = _resolve_expiration(exps, date=date, dte=dte)
    if not expiration:
        cli.console.print(f"[ts.bad]✖[/ts.bad] No option expirations found for {underlying}.")
        raise typer.Exit(code=5)

    # 2. ATM reference (best-effort) to center the strike window.
    atm: float | None = None
    try:
        uq = asyncio.run(cli.client.market_data.get_quotes([underlying]))
        if uq and uq[0].last:
            atm = float(uq[0].last)
    except Exception:
        atm = None

    # 3. Collect the chain snapshot (bounded by EndSnapshot or --timeout).
    # The stream defaults to a small window around ATM, so request enough
    # strikes on each side to satisfy --strikes (plus a small buffer, since the
    # server centers on its own ATM which may differ slightly from ours).
    proximity = (strikes // 2) + 3 if strikes > 0 else None

    async def _gather(frames: list[dict[str, Any]]) -> None:
        import contextlib

        agen: Any = cli.client.market_data.stream_option_chain(
            underlying, expiration, strike_proximity=proximity
        )
        async with contextlib.aclosing(agen) as stream:
            async for ev in stream:
                data = ev.raw or {}
                if data.get("StreamStatus") == "EndSnapshot":
                    return
                if data.get("Legs") or data.get("Strikes"):
                    frames.append(data)
                    if len(frames) >= 5000:  # safety cap
                        return

    async def _collect() -> list[dict[str, Any]]:
        import contextlib

        frames: list[dict[str, Any]] = []
        with contextlib.suppress(asyncio.TimeoutError, TimeoutError):
            await asyncio.wait_for(_gather(frames), timeout)
        return frames

    frames = _run_md(cli, _collect())
    rows = _assemble_chain(frames)
    if not rows:
        cli.console.print(
            f"[ts.warn]⚠[/ts.warn] No chain data for {underlying} {expiration} "
            f"(market may be closed, or try a longer --timeout)."
        )
        raise typer.Exit(code=0)

    selected = _select_strikes(list(rows), count=strikes, atm=atm)

    # 4. Resolve the column set.
    if columns:
        cols = [
            c.strip().lower() for c in columns.split(",") if c.strip().lower() in _CHAIN_COLUMNS
        ]
        if not cols:
            cli.console.print(
                f"[ts.bad]✖[/ts.bad] No valid columns in {columns!r}. "
                f"Choices: {', '.join(_CHAIN_COLUMNS)}."
            )
            raise typer.Exit(code=2)
    else:
        cols = list(_DEFAULT_CHAIN_COLUMNS)

    if cli.output_mode != OutputMode.TABLE:
        for strike in selected:
            sys.stdout.write(
                json.dumps(
                    {
                        "Strike": strike,
                        "Call": rows[strike].get("Call"),
                        "Put": rows[strike].get("Put"),
                    },
                    default=str,
                )
                + "\n"
            )
        return

    from rich import box
    from rich.table import Table

    dte_days = _days_out(expiration)
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    cli.console.print(
        render_banner(
            f"Chain {underlying}",
            f"exp {expiration} ({dte_days}d)  ·  {len(selected)} strikes"
            + (f"  ·  ATM ~{atm:,.2f}" if atm else ""),
            cli.environment.value,
            now,
        )
    )
    tbl = Table(box=box.ROUNDED, header_style="ts.header", title="◀ CALLS          PUTS ▶")
    for key in cols:  # call side
        tbl.add_column(_CHAIN_COLUMNS[key][0], justify="right", style="ts.up")
    tbl.add_column("Strike", justify="center", style="ts.symbol")
    for key in cols:  # put side
        tbl.add_column(_CHAIN_COLUMNS[key][0], justify="right", style="ts.down")

    atm_strike = min(selected, key=lambda s: abs(s - atm)) if atm else None
    for strike in selected:
        call = rows[strike].get("Call")
        put = rows[strike].get("Put")
        strike_label = f"{strike:,.2f}"
        if strike == atm_strike:
            strike_label = f"[reverse]{strike_label}[/reverse]"
        cells = [_fmt_chain_cell(k, call) for k in cols]
        cells.append(strike_label)
        cells.extend(_fmt_chain_cell(k, put) for k in cols)
        tbl.add_row(*cells)
    cli.console.print(tbl)


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
        async with contextlib.aclosing(agen) as stream:
            async for ev in stream:
                data = ev.raw or {}
                if cli.output_mode == OutputMode.TABLE:
                    sym = data.get("Symbol") or data.get("OrderID") or ""
                    cli.console.print(
                        f"[ts.symbol]{sym}[/ts.symbol]  {json.dumps(data, default=str)}"
                    )
                else:
                    sys.stdout.write(json.dumps(data, default=str) + "\n")
                    sys.stdout.flush()
                count += 1
                if max_frames and count >= max_frames:
                    break
                if deadline and loop.time() >= deadline:
                    break
    return count


async def _live_quotes_stream(
    cli: CLIContext, agen: Any, *, max_frames: int, for_seconds: float
) -> int:
    """Sticky-header live table: one row per symbol, updated in place.

    Maintains the latest quote per symbol and re-renders a Rich table on each
    frame via ``rich.live.Live``. Returns the number of frames consumed.
    """
    import contextlib

    from rich import box
    from rich.live import Live
    from rich.table import Table

    from tradestation.cli.render import _pnl_style, _sign

    latest: dict[str, dict[str, Any]] = {}
    count = 0
    loop = asyncio.get_event_loop()
    deadline = loop.time() + for_seconds if for_seconds > 0 else None

    def _render() -> Table:
        tbl = Table(box=box.ROUNDED, header_style="ts.header", title="Live Quotes")
        tbl.add_column("Symbol", style="ts.symbol")
        tbl.add_column("Last", justify="right", style="ts.price")
        tbl.add_column("Δ", justify="right")
        tbl.add_column("Bid", justify="right", style="ts.price")
        tbl.add_column("Ask", justify="right", style="ts.price")
        tbl.add_column("Volume", justify="right")
        for sym, q in sorted(latest.items()):
            chg = q.get("NetChange")
            try:
                chg_f = float(chg) if chg else 0.0
            except (TypeError, ValueError):
                chg_f = 0.0
            from rich.text import Text

            tbl.add_row(
                sym,
                str(q.get("Last", "")),
                Text(_sign(chg_f), style=_pnl_style(chg_f)),
                str(q.get("Bid", "")),
                str(q.get("Ask", "")),
                str(q.get("Volume", "")),
            )
        return tbl

    with (
        contextlib.suppress(KeyboardInterrupt),
        Live(_render(), console=cli.console, refresh_per_second=8) as live,
    ):
        async with contextlib.aclosing(agen) as stream:
            async for ev in stream:
                data = ev.raw or {}
                sym = data.get("Symbol")
                if sym:
                    latest[sym] = data
                    live.update(_render())
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
    # Sticky-header live table only in a TTY table view; otherwise stream JSONL.
    live = cli.output_mode == OutputMode.TABLE and cli.console.is_terminal

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            stream = ts.market_data.stream_quotes(syms)
            consumer = _live_quotes_stream if live else _consume_stream
            return await consumer(cli, stream, max_frames=max_frames, for_seconds=for_seconds)

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


@stream_app.command(name="depth-quotes")
def stream_depth_quotes_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Symbol.")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream Level-2 individual market-depth quotes. Ctrl-C to stop.

    Maps to: B14 — ``GET /v3/marketdata/stream/marketdepth/quotes/{symbol}``
    """
    cli = CLIContext.from_typer(ctx)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_depth_quotes(symbol),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")


@stream_app.command(name="depth-agg")
def stream_depth_agg_cmd(
    ctx: typer.Context,
    symbol: Annotated[str, typer.Argument(help="Symbol.")],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream Level-2 aggregate market-depth data. Ctrl-C to stop.

    Maps to: B15 — ``GET /v3/marketdata/stream/marketdepth/aggregates/{symbol}``
    """
    cli = CLIContext.from_typer(ctx)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_depth_aggregates(symbol),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")


@stream_app.command(name="option-chain")
def stream_option_chain_cmd(
    ctx: typer.Context,
    underlying: Annotated[str, typer.Argument(help="Underlying symbol.")],
    expiration: Annotated[
        str,
        typer.Option("--expiration", "-e", help="Expiration date (YYYY-MM-DD)."),
    ],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live option-chain updates for one expiration. Ctrl-C to stop.

    Maps to: B16 — ``GET /v3/marketdata/stream/options/chains/{underlying}``

    For a one-shot rendered snapshot instead, use ``ts md options chain``.
    """
    cli = CLIContext.from_typer(ctx)

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_option_chain(underlying, expiration),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")


@stream_app.command(name="option-quotes")
def stream_option_quotes_cmd(
    ctx: typer.Context,
    leg: Annotated[
        list[str],
        typer.Option("--leg", help="Option leg symbol (e.g. 'AAPL 260619C200'). Repeatable."),
    ],
    max_frames: _MaxOpt = 0,
    for_seconds: _ForOpt = 0,
) -> None:
    """Stream live option quotes for one or more legs. Ctrl-C to stop.

    Maps to: B17 — ``GET /v3/marketdata/stream/options/quotes``
    """
    cli = CLIContext.from_typer(ctx)
    legs = [{"Symbol": s} for s in leg]

    async def _go() -> int:
        async with cli.client.as_async() as ts:
            return await _consume_stream(
                cli,
                ts.market_data.stream_option_quotes(legs),
                max_frames=max_frames,
                for_seconds=for_seconds,
            )

    n = _run_md(cli, _go())
    if cli.output_mode == OutputMode.TABLE:
        cli.console.print(f"[ts.ok]✔ stream closed — {n} frames[/ts.ok]")
