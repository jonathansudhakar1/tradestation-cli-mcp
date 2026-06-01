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
from typing import Annotated

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
        "symbol", "last", "net_change", "net_change_pct", "bid", "bid_size",
        "ask", "ask_size", "volume", "open", "high", "low",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    writer.writerow(fields)
    for q in quotes:
        assert isinstance(q, Quote)
        writer.writerow([
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
        ])
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
