# 07 — Output Style (Rich)

The CLI must be visually distinctive and easy to skim. Default output is **never** a raw dict dump. Every command picks a renderer from `tscli/render.py` and emits via a single Rich `Console`.

## Tooling

- **Rich** ([docs](https://rich.readthedocs.io/)) for tables, panels, syntax highlighting, progress, markdown, live displays, prompts.
- Single `Console` per process, themed via `tscli/theme.py`.
- `Console.is_terminal` switches output: TTY → tables/panels; pipe → JSONL (overridable by `--output`).
- `NO_COLOR=1` and `--no-color` strip styles globally.

## Color palette (`tscli/theme.py`)

Named styles applied semantically — never raw hex in command code.

| Style name | Color | Used for |
|---|---|---|
| `ts.header` | bold cyan | Section headings, panel borders |
| `ts.label` | dim white | Field labels in detail panels |
| `ts.value` | white | Field values |
| `ts.mono` | bright_black | Inline `code`, account IDs, order IDs |
| `ts.symbol` | bold yellow | Ticker symbols |
| `ts.price` | white | Numeric prices |
| `ts.up` | bold green | Positive Δ, Δ%, fill |
| `ts.down` | bold red | Negative Δ, Δ%, rejected |
| `ts.flat` | dim white | Zero Δ |
| `ts.warn` | bold yellow | Warnings (preview banners, halted symbol) |
| `ts.danger` | bold red on default | Destructive prompts, `--unsafe-log-secrets` banner |
| `ts.ok` | bold green | "✔" markers, healthy auth |
| `ts.bad` | bold red | "✖" markers, expired auth |
| `ts.muted` | dim | Timestamps, secondary data |
| `ts.kbd` | reverse | Keys to press in confirmation prompts |
| `ts.heartbeat` | bright_black | Stream heartbeat lines (suppressed unless `--show-heartbeats`) |
| `ts.json.key` | cyan | JSON output keys (when `--output json`) |
| `ts.json.string` | green | JSON strings |
| `ts.json.number` | magenta | JSON numbers |

The palette is designed to render legibly on both light and dark terminals: bold + saturated for actionable info, dim for context. We never rely on color *alone* — every colored value also carries a sign, icon, or label.

## Table conventions

- Header row: bold cyan, dim border (`box=ROUNDED`).
- Right-align numeric columns; right-align timestamps too.
- Truncate long IDs to last-4 with `…` prefix in tables; full ID available in single-row detail panels.
- Δ columns show sign explicitly (`+1.23` / `-0.84`).
- Δ% columns show one decimal and a percent sign (`+0.7%`).
- Currency: locale-aware thousands separator, two decimals; positive prices use `ts.price` (white), negatives use `ts.down`.

### Example: `ts md quotes AAPL MSFT NVDA`

```
Quotes  •  3 symbols  •  live  •  15:32:07 UTC
╭────────┬─────────┬────────┬────────┬─────────┬───────┬─────────┬───────┬───────────┬─────────┬─────────┬─────────┬────────╮
│ Symbol │   Last  │    Δ   │   Δ%   │   Bid   │  BidSz│   Ask   │  AskSz│  Volume   │   Open  │   High  │   Low   │ Halted │
├────────┼─────────┼────────┼────────┼─────────┼───────┼─────────┼───────┼───────────┼─────────┼─────────┼─────────┼────────┤
│ AAPL   │ 178.45  │  +1.27 │ +0.72% │ 178.44  │   400 │ 178.46  │   300 │ 42,113,800│ 177.10  │ 179.02  │ 176.81  │   no   │
│ MSFT   │ 431.10  │  -0.85 │ -0.20% │ 431.09  │   220 │ 431.12  │   190 │ 18,402,140│ 432.00  │ 432.90  │ 430.55  │   no   │
│ NVDA   │ 1198.00 │ +12.40 │ +1.05% │1197.95  │   110 │1198.05  │   140 │ 26,910,773│1183.21  │1201.10  │1181.40  │   no   │
╰────────┴─────────┴────────┴────────┴─────────┴───────┴─────────┴───────┴───────────┴─────────┴─────────┴─────────┴────────╯
```

### Example: `ts brokerage positions 11111111`

```
Positions  •  account 11111111  •  6 open
╭────────┬───────┬──────┬──────────┬─────────┬───────────┬───────────┬───────────┬─────────╮
│ Symbol │ Asset │  Qty │  AvgEntry│   Last  │     MV    │  UPnL ($) │  UPnL (%) │  Side   │
├────────┼───────┼──────┼──────────┼─────────┼───────────┼───────────┼───────────┼─────────┤
│ AAPL   │   EQ  │  500 │   162.10 │  178.45 │  89,225.00│ +8,175.00 │   +10.09% │   LONG  │
│ MSFT   │   EQ  │  200 │   438.40 │  431.10 │  86,220.00│ -1,460.00 │    -1.66% │   LONG  │
│ ES.M26 │   FUT │    2 │  5,300.00│ 5,318.50│ 531,850.00│ +1,850.00 │    +0.35% │   LONG  │
│ AAPL …C200│ OPT│   −5 │     5.40 │    3.30 │  -1,650.00│ +1,050.00 │    +38.9% │  SHORT  │
│ BTCUSD │ CRYPTO│ 0.50 │ 68,000.00│71,200.00│  35,600.00│ +1,600.00 │    +4.71% │   LONG  │
╰────────┴───────┴──────┴──────────┴─────────┴───────────┴───────────┴───────────┴─────────╯
Totals  •  MV $740,245.00  •  UPnL +$9,215.00  ( +1.26% )
```

UPnL rendered in `ts.up` / `ts.down`. Footer is bold; MV is `ts.price`; UPnL inherits.

## Detail panel convention

Used for single-row endpoints (B5 `symbol_list_show`, C6 `order_show`, D1 preview, A `auth_status`).

```
╭── Order 835711 ────────────────────────────────────────────╮
│ Account     11111111                                       │
│ Symbol      AAPL                       Side    BUY         │
│ Type        Limit       Limit price    178.00              │
│ Qty         100         Filled         0    (working)      │
│ TIF         DAY         Route          AUTO                │
│ Opened      2026-05-23 09:30:17 UTC                        │
│ Last upd    2026-05-23 09:30:18 UTC                        │
├─── Legs ───────────────────────────────────────────────────┤
│ #1  AAPL  BUY  100  LMT 178.00                             │
├─── Fills ──────────────────────────────────────────────────┤
│ (none)                                                     │
╰────────────────────────────────────────────────────────────╯
```

## Progress & spinners

- `rich.progress.Progress` for long-running multi-call ops (e.g., paginated historical orders) — bar with ETA and rate.
- `rich.spinner.Spinner` for one-shot waits (`ts auth refresh`).
- All progress is auto-suppressed under `--quiet` or non-TTY.

## Streaming output

For `ts md stream …` and `ts bk stream …` commands:

- Sticky **header row** painted via `rich.live.Live` keeps the column titles visible while rows scroll under it.
- Each row's price/qty/status column animates a brief background flash (`ts.up` / `ts.down`) on change.
- Heartbeats are silent by default. `--show-heartbeats` reveals them as dimmed marginalia.
- `Ctrl-C` triggers a clean shutdown that prints a one-line footer:

```
✔ stream closed   ⟂  events: 1,402   heartbeats: 38   duration: 03m 17s
```

## Confirmation prompts (destructive actions)

```
╔══════════════════════════════════════════════════════════════╗
║   ⚠  CANCEL ORDER                                            ║
║                                                              ║
║   Order        835711                                        ║
║   Status       Working                                       ║
║   Detail       AAPL  BUY 100  @ LMT 178.00                   ║
╚══════════════════════════════════════════════════════════════╝

  Type the order ID to confirm cancellation:  > 835711_
```

The required-token prompt (for `cancel`, `place`) defeats accidental Enter-spam. For `ts auth clear` we require typing `DELETE` literally.

## JSON / structured outputs

- `--output json`: pretty-printed, syntax-highlighted (Rich's `JSON.from_data`) — for humans.
- `--output jsonl`: one object per line, no color — for scripts / pipelines. **This is the default when output is piped.**
- `--output csv` / `--output tsv`: flattened (nested objects stringified). Headers row included unless `--no-header`.
- `--output yaml`: optional, pulls in `pyyaml`.

## Error rendering

```
✖ AUTH 401   refresh token rejected
  endpoint     POST https://signin.tradestation.com/oauth/token
  request id   8b2a3c8e-…
  detail       invalid_grant
  next step    Run `ts auth login` to obtain a new refresh token,
               or supply one via `ts auth set --refresh-token …`.
```

Errors always include: severity glyph, short title, three-line metadata, and a "next step" hint. Stack traces appear only with `-vv`.

## Banners & headers

Every command prints a one-line context banner above the data:

```
Quotes  •  3 symbols  •  live  •  15:32:07 UTC
```

Banner sections (separated by `•`): operation, scope, environment, when. Banner is omitted under `--quiet`.

## Theming hooks

Users can override via `~/.tscli/theme.toml`:

```toml
[styles]
"ts.up" = "bold cyan"
"ts.down" = "bold magenta"
"ts.symbol" = "yellow"
```

Useful for colorblind users and personal preference. `ts theme show` prints the active palette as a swatch grid; `ts theme reset` wipes the override.
