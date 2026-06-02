# 04 — CLI Design

The CLI is `ts`. It is the **only** way most users will touch the API. Every endpoint in [03-endpoint-inventory.md](03-endpoint-inventory.md) has a corresponding command — full coverage is enforced by an integration test that introspects the command tree against the inventory.

Shipped as part of the `tradestation-cli-mcp` distribution. `pip install tradestation-cli-mcp` registers the `ts` console script; no separate CLI install. Source lives at `src/tradestation/cli/`.

Built on **Typer** (commands), **Click** (parameter machinery via Typer), and **Rich** (rendering — full palette in [07-output-style.md](07-output-style.md)).

## Top-level command tree

```
ts ──┬── auth                  Credentials & token lifecycle
     │     ├── set             Save client_id / client_secret / refresh_token
     │     ├── status          Show credential state, env, token expiry
     │     ├── refresh         Force an access-token refresh now
     │     ├── login           Browser auth-code flow (PKCE) → refresh token
     │     ├── clear           Wipe credentials + keyring entry
     │     ├── export          Print decrypted payload (requires --yes-i-want-secrets-on-stdout)
     │     └── doctor          Diagnostics
     │
     ├── env                   SIM ↔ LIVE switching
     │     ├── show
     │     ├── live
     │     └── sim
     │
     ├── md                    MarketData
     │     ├── quotes          (B2)
     │     ├── bars            (B1)
     │     ├── symbols         (B3)
     │     ├── lists           (B4/B5/B6 — alias: symbol-lists)
     │     │     ├── ls
     │     │     ├── show
     │     │     └── symbols
     │     ├── crypto
     │     │     └── pairs     (B7)
     │     ├── options
     │     │     ├── expirations  (B8)
     │     │     ├── strikes      (B9)
     │     │     ├── spread-types (B10)
     │     │     └── risk-reward  (B11)
     │     └── stream
     │           ├── quotes        (B13)
     │           ├── bars          (B12)
     │           ├── depth-quotes  (B14)
     │           ├── depth-agg     (B15)
     │           ├── option-chain  (B16)
     │           └── option-quotes (B17)
     │
     ├── brokerage             Account state  (alias: bk)
     │     ├── accounts        (C1)
     │     ├── balances        (C2)
     │     ├── balances-bod    (C3)
     │     ├── positions       (C4)
     │     ├── orders          (C5)
     │     ├── order           (C6 — singular form by ID)
     │     ├── historical-orders   (C7)
     │     ├── historical-order    (C8)
     │     ├── wallets         (C9)
     │     └── stream
     │           ├── orders    (C10)
     │           ├── order     (C11)
     │           ├── positions (C12)
     │           └── wallets   (C13)
     │
     └── order                 OrderExecution
           ├── place           (D2)
           ├── confirm         (D1 — alias of `place --dry-run`)
           ├── replace         (D3)
           ├── cancel          (D4)
           ├── group
           │     ├── place     (D6)
           │     └── confirm   (D5)
           ├── routes          (D8)
           └── triggers        (D7)
```

`ts --help` renders this tree in a Rich-styled panel; every subcommand has its own `--help`.

## Global flags (available on every command)

| Flag | Purpose |
|---|---|
| `--env [live\|sim]` | Override environment for this invocation. |
| `--sim` | Shorthand for `--env sim`. |
| `--profile NAME` | Use `~/.tscli/profiles/NAME` instead of the default credentials file. |
| `--output [table\|json\|jsonl\|csv\|tsv\|yaml]` | Rendering mode. Default `table` (TTY) / `jsonl` (pipe). |
| `--no-color` | Force plain ANSI-free output. Also honors `NO_COLOR=1`. |
| `--quiet` / `-q` | Suppress non-data output (banners, progress). |
| `-v` / `-vv` | Verbose logging (URLs + status / + redacted bodies). |
| `--unsafe-log-secrets` | Disable redaction (dev only; emits red warning banner). |
| `--timeout SECONDS` | Per-request timeout override (default 30 s, streams unlimited). |
| `--retries N` | Retry budget for transient failures (default 3, exp backoff). |
| `--help` | Rich-formatted help. |
| `--version` | `tscli x.y.z (tradestation x.y.z)`. |

When output is piped (`isatty == False`), the CLI auto-switches to `jsonl` so it remains script-friendly. Tables only appear in TTYs.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic failure |
| 2 | Bad CLI usage (Typer/Click) |
| 3 | Auth error (refresh failed / no credentials) |
| 4 | Rate-limited (429 after retries exhausted) |
| 5 | API error (4xx/5xx with TS payload) |
| 6 | Order rejected (D-series validation failure) |
| 130 | Interrupted (Ctrl-C in a stream) |

---

## Section A — Auth

### `ts auth set`

Interactive by default; flag-driven for scripts. See [02-auth-and-credentials.md](02-auth-and-credentials.md) for the full lifecycle.

```
ts auth set [--client-id ID] [--client-secret SECRET] [--refresh-token TOKEN]
            [--scope "openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access"]
            [--env live|sim] [--encrypt/--no-encrypt]
            [--keyring/--no-keyring] [--passphrase-stdin]
            [--i-understand-the-risk]      # required with --no-encrypt
```

Side effects: writes `~/.tscli/credentials` (`0600`) and `~/.tscli/state.json`. Aborts with no writes on auth failure.

### `ts auth status`

```
$ ts auth status
┌──── TradeStation credentials ─────────────────────────────┐
│ Path           /home/jonathan/.tscli/credentials          │
│ Scheme         fernet-v1   (keyring: SecretService)       │
│ Environment    live                                       │
│ Client ID      ******M3xQ                                 │
│ Refresh token  ******t9pK   (rotation: off)               │
│ Access token   valid   (expires in 17m 02s — 15:30 UTC)   │
│ Scope          openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access │
└───────────────────────────────────────────────────────────┘
```

### `ts auth refresh`

```
$ ts auth refresh
⠋ Refreshing access token…
✔ New access token acquired   (expires in 20m 00s — 15:48 UTC)
```

### `ts auth login`

Opens browser, captures redirect, exchanges code, writes credentials. Same final state as `ts auth set`.

### `ts auth clear`

```
$ ts auth clear
This will delete /home/jonathan/.tscli/credentials and remove the keyring entry.
  --revoke    additionally call POST /oauth/revoke on the refresh token

Type DELETE to confirm: DELETE
✔ Credentials removed.
```

### `ts auth doctor` / `ts auth export`

`doctor` prints a Rich tree of diagnostics; `export` dumps decrypted JSON with a yelling warning.

---

## Section B — MarketData

### `ts md quotes`  →  `GET /v3/marketdata/quotes/{symbols}` (B2)

```
ts md quotes AAPL MSFT NVDA
ts md quotes AAPL,MSFT,NVDA                # comma form
ts md quotes -f symbols.txt                # one per line
```

Rendered as a Rich table; columns: Symbol · Last · Δ · Δ% · Bid · BidSize · Ask · AskSize · Volume · Open · High · Low · Halted · LastUTC. Δ/Δ% green/red.

### `ts md bars`  →  `GET /v3/marketdata/barcharts/{symbol}` (B1)

```
ts md bars AAPL --interval 1 --unit Minute --barsback 200
ts md bars AAPL --interval 5 --unit Minute --first 2026-05-01 --last 2026-05-23
ts md bars AAPL --interval 1 --unit Daily --barsback 250 --session UseExtended
ts md bars AAPL --interval 1 --unit Daily --barsback 250 --output csv > aapl.csv
```

Flags: `--interval`, `--unit` (`Minute|Daily|Weekly|Monthly`), `--barsback`, `--first` (ISO date), `--last`, `--session` (`Default|Extended|UseExtended`).

### `ts md symbols`  →  `GET /v3/marketdata/symbols/{symbols}` (B3)

```
ts md symbols AAPL ES.M26 BTCUSD
```

Renders one Rich panel per symbol with grouped fields (asset class, exchange, contract specs, tick size, multiplier…).

### `ts md lists`  →  symbol lists

```
ts md lists ls                          # B4 — list all
ts md lists show <listID>               # B5 — list metadata
ts md lists symbols <listID>            # B6 — symbols inside
```

### `ts md crypto pairs`  →  `GET /v3/marketdata/crypto/symbolnames` (B7)

```
ts md crypto pairs
ts md crypto pairs --search BTC         # client-side filter
```

### `ts md options expirations`  →  (B8)

```
ts md options expirations AAPL
ts md options expirations AAPL --strike 200
```

### `ts md options strikes`  →  (B9)

```
ts md options strikes AAPL --expiration 2026-06-20
ts md options strikes AAPL --expiration 2026-06-20 --spread-type Vertical
```

### `ts md options chain`  →  (B16 snapshot)

Full chain for one expiration, rendered as a classic `◀ CALLS │ Strike │ PUTS ▶`
table (collected from the streaming endpoint into a one-shot snapshot; the
ATM strike is highlighted).

```
ts md options chain AAPL                         # nearest expiration
ts md options chain AAPL --dte 30                # nearest to 30 days out
ts md options chain AAPL --date 2026-06-19       # specific expiration
ts md options chain AAPL --strikes 16            # 16 strikes centered on ATM
ts md options chain SPY --columns bid,ask,iv,delta   # choose columns per side
```

- `--strikes N` / `-n N`: number of strikes to show, centered on the money (default 20).
- `--columns`: comma-separated, applied to each side. Choices: `bid, ask, mid, last, volume, oi, iv, delta, gamma, theta, vega` (default `bid,ask,last,volume,oi,iv,delta`).
- `--dte N` picks the expiration nearest N days out; `--date` selects an exact date; default is the soonest upcoming expiration.
- `--timeout` bounds how long the snapshot collection runs (default 10s).

### `ts md options spread-types`  →  (B10)

```
ts md options spread-types
```

Renders the supported spread types in a single colored chip-grid.

### `ts md options risk-reward`  →  (B11)

```
ts md options risk-reward \
  --leg "AAPL 250620C200,buy,1,5.40" \
  --leg "AAPL 250620C210,sell,1,2.10" \
  --entry 3.30
```

Legs accept the form `<OCC symbol>,<buy|sell>,<qty>,<price>`. May be repeated; or a single `--legs-json '[...]'` for scripts.

### `ts md stream …`

All streams print live updates with a sticky header and per-row Δ color. `Ctrl-C` terminates cleanly with a one-line summary `(N messages, M heartbeats over T seconds)`.

```
ts md stream quotes AAPL MSFT
ts md stream bars AAPL --interval 1 --unit Minute
ts md stream depth-quotes AAPL
ts md stream depth-agg AAPL
ts md stream option-chain AAPL --expiration 2026-06-20
ts md stream option-quotes \
    --leg "AAPL 250620C200" --leg "AAPL 250620C210"
```

Flag common to streams: `--max N` (auto-stop after N rows), `--for 30s` (timed run), `--out file.jsonl` (also write JSONL).

---

## Section C — Brokerage  (alias `bk`)

### `ts brokerage accounts`  →  (C1)

```
$ ts brokerage accounts
┌────────────┬─────────┬──────────────┬─────────┬───────────┬─────────────┐
│ Account    │ Type    │ Status       │ Currency│ Equity    │ BuyingPower │
├────────────┼─────────┼──────────────┼─────────┼───────────┼─────────────┤
│ 11111111   │ Margin  │ Active       │ USD     │ 124,308.41│ 248,616.82  │
│ 22222222   │ Cash    │ Active       │ USD     │   5,002.11│   5,002.11  │
└────────────┴─────────┴──────────────┴─────────┴───────────┴─────────────┘
```

### `ts brokerage balances 11111111`  →  (C2)

Multi-account: `ts bk balances 11111111 22222222`.

### `ts brokerage balances-bod 11111111`  →  (C3)

### `ts brokerage positions 11111111`  →  (C4)

Columns: Symbol · Asset · Qty · AvgEntry · Last · MV · UnrealPnL ($) · UnrealPnL (%) · Day Δ · Side. PnL colored.

### `ts brokerage orders 11111111`  →  (C5)

Columns: ID · Time · Symbol · Side · Type · Qty · Filled · Price · Status. Status colored (filled=green, working=cyan, rejected=red).

### `ts brokerage order 11111111 835711`  →  (C6)

Single-order detail panel with leg breakdown, fills, fees.

### `ts brokerage historical-orders 11111111`  →  (C7)

```
ts bk historical-orders 11111111 --since 2026-01-01
ts bk historical-orders 11111111 --since 2026-01-01 --status filled
```

### `ts brokerage historical-order 11111111 835711`  →  (C8)

### `ts brokerage wallets 11111111`  →  (C9)

### `ts brokerage stream …`  →  (C10–C13)

```
ts bk stream orders 11111111
ts bk stream order 11111111 835711
ts bk stream positions 11111111
ts bk stream wallets 11111111
```

Same `--max`/`--for`/`--out` flags as md streams.

---

## Section D — OrderExecution

### `ts order place`  →  (D2)

The flagship destructive command. **Always** prints the preview from `/orderconfirm` first and prompts unless `--yes` is supplied. `--dry-run` runs the preview only and exits.

```
ts order place \
  --account 11111111 \
  --symbol AAPL \
  --side buy \
  --type market \
  --qty 100 \
  --tif day
```

Other type-specific flags:

| Type | Required additional flags |
|---|---|
| `market` | — |
| `limit` | `--limit-price` |
| `stop` | `--stop-price` |
| `stop-limit` | `--stop-price`, `--limit-price` |

Common flags: `--tif` (`day|gtc|gtd|ioc|fok|opg|cls`), `--gtd <date>`, `--route AUTO`, `--all-or-none`, `--trail-amount`, `--trail-percent`, `--activation-trigger STT`, `--show NN`, `--peg-value 0.01`.

For options (single-leg): `--option-symbol "AAPL 250620C200"` instead of `--symbol`, with `--option-type` auto-detected.

For multi-leg options or complex orders, prefer `ts order group place` (see below) — but `--leg "...,buy,1"` is accepted up to 4 legs as a shortcut.

Preview output:

```
┌── Order preview (Confirm) ────────────────────────────────────┐
│ Account 11111111  •  AAPL  •  BUY 100  •  Market  •  DAY     │
│ Est cost           $16,743.00                                  │
│ Commission         $0.00                                       │
│ Buying-power after $231,873.82  (was $248,616.82 — Δ −$16,743) │
│ Route              AUTO                                        │
│ Warnings           (none)                                      │
└────────────────────────────────────────────────────────────────┘
Submit this order? [y/N]:
```

### `ts order confirm` / `ts order place --dry-run`  →  (D1)

Identical to the preview block above; never submits.

### `ts order replace 835711`  →  (D3)

```
ts order replace 835711 --account 11111111 --limit-price 178.50 --qty 100
```

Diff is rendered as before/after: green for new values, red for removed.

### `ts order cancel 835711`  →  (D4)

```
$ ts order cancel 835711 --account 11111111
This will cancel order 835711 (AAPL BUY 100 @ LMT 178.00 — Working).
Proceed? [y/N]:
```

`--yes` for non-interactive; `--all-working --account 11111111` to bulk-cancel all working orders on an account (multiple sequential `DELETE` calls, with a confirmation count).

### `ts order group place`  →  (D6) and `ts order group confirm`  →  (D5)

Groups: OCO, OSO, bracket. Construct via repeatable `--child` flag or JSON file.

```
ts order group place --type OCO --account 11111111 \
  --child '{"symbol":"AAPL","side":"sell","qty":100,"type":"limit","limit":190}' \
  --child '{"symbol":"AAPL","side":"sell","qty":100,"type":"stop","stop":170}'

ts order group place --type bracket --file bracket.json
```

`confirm` is the dry-run equivalent.

### `ts order routes`  →  (D8)

```
$ ts order routes --asset equity
Route        Asset    Exchange       Capabilities
AUTO         Equity   *              Smart-routed
ARCA         Equity   ARCA           Lit
NSDQ         Equity   NASDAQ         Lit, MakerTaker
...
```

### `ts order triggers`  →  (D7)

Lists activation trigger codes (e.g., `STT`) with descriptions.

---

## Shell completions

```
ts completions install bash
ts completions install zsh
ts completions install fish
ts completions install powershell
```

(Typer ships these via Click.)

## Configuration profiles

Default credentials live at `~/.tscli/credentials`. Multiple profiles:

```
~/.tscli/profiles/<name>/credentials
~/.tscli/profiles/<name>/state.json
```

```
ts --profile prod brokerage accounts
ts --profile paper order place ...
```

`ts auth set --profile paper` saves to the paper profile. `ts profile ls`, `ts profile use <name>`, `ts profile rm <name>` round out management.

## Help text style

Each command's `--help` shows:

1. A one-line description.
2. A **Maps to:** line citing the inventory ID and endpoint (e.g., *Maps to: B1 — `GET /v3/marketdata/barcharts/{symbol}`*).
3. Arguments / options in two Rich tables.
4. Two example invocations (basic + advanced) in a copyable code block.
5. A "See also" line pointing to related commands.

## Test for completeness

A CI test `tests/test_cli_inventory_coverage.py` reads `docs/03-endpoint-inventory.md`, parses the IDs (A1–D8), and asserts each one is referenced in **exactly one** Typer command's docstring `Maps to:` line. Drift = build break. This is how we guarantee "don't miss anything" remains true forever.
