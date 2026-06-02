# tradestation-cli-mcp

[![CI](https://github.com/jonathansudhakar1/tradestation-cli-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jonathansudhakar1/tradestation-cli-mcp/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/tradestation-cli-mcp.svg)](https://pypi.org/project/tradestation-cli-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/tradestation-cli-mcp.svg)](https://pypi.org/project/tradestation-cli-mcp/)
[![Downloads](https://img.shields.io/pypi/dm/tradestation-cli-mcp.svg)](https://pypi.org/project/tradestation-cli-mcp/)
[![License: MIT](https://img.shields.io/pypi/l/tradestation-cli-mcp.svg)](LICENSE)

**A Python library, command-line interface (CLI), and Model Context Protocol (MCP) server for the [TradeStation v3 REST API](https://api.tradestation.com/docs/)** — real-time and streaming market data for stocks, options, futures, and crypto, plus brokerage accounts, balances, positions, and order execution. One `pip install` gives you all three on top of TradeStation:

| Use it as… | What it gives you | How to invoke |
|---|---|---|
| A **Python library** | `TradeStationClient` (sync & async), Pydantic models, streaming iterators | `import tradestation` |
| A **CLI** | `ts` — Rich-formatted, colorful command-line tool covering every endpoint | `ts …` |
| An **MCP server** | `ts-mcp` — local Model Context Protocol server for Claude Code, Cursor, Windsurf, … | `ts-mcp` |

**One install gives you all three:**

```bash
pip install tradestation-cli-mcp
```

Prefer an isolated install for the `ts` / `ts-mcp` command-line tools:

```bash
pipx install tradestation-cli-mcp        # or: uv tool install tradestation-cli-mcp
```

Optional pandas support (DataFrame helpers): `pip install "tradestation-cli-mcp[pandas]"`.
Requires **Python 3.10+**.

The package distributes the **library** (`tradestation/…`), a **CLI** built on top of it (`tradestation/cli/…`), and an **MCP server** also built on top of it (`tradestation/mcp/…`). The library is the only thing that speaks HTTP — the CLI and MCP server are thin layers over it.

---

## Status

**Implemented and tested.** All **42** TradeStation v3 endpoints are wrapped across the library, CLI, and MCP server:

| Category | Endpoints | Live-verified vs SIM |
|---|---|---|
| MarketData (REST) | 11 — quotes, bars, symbols, symbol lists, crypto pairs, option expirations/strikes/spread-types/risk-reward | ✓ |
| MarketData (streaming) | 6 — quotes, bars, market depth ×2, option chain, option quotes | ✓ |
| Brokerage (REST) | 9 — accounts, balances, BOD balances, positions, orders, orders-by-id, historical orders ×2, wallets | ✓ |
| Brokerage (streaming) | 4 — orders, orders-by-id, positions, wallets | ✓ |
| OrderExecution | 8 — confirm, place, replace, cancel, group confirm/place, activation triggers, routes | ✓ (read-only + previews; placement mock-tested) |
| Auth | refresh-token exchange, encrypted credential store, proactive refresh | ✓ |

- **~550 unit/CLI/MCP tests + live SIM integration tests**, CI on Python 3.10–3.13 (lint, types, full suite).
- Equities, **futures**, and **crypto** all supported.
- Default environment is **sim** (paper trading) — safe by default.

## Quick start

```bash
# Configure credentials once (prompts; stores encrypted under ~/.tscli/credentials)
ts auth set
ts auth status

# Market data
ts md quotes AAPL MSFT BTCUSD          # equities + crypto
ts md bars AAPL --barsback 100
ts md options expirations AAPL
ts md options chain AAPL --dte 30 --strikes 16   # calls │ strike │ puts, ATM-centered
ts md crypto pairs

# Account data
ts brokerage accounts
ts brokerage balances <account-id>
ts brokerage positions <account-id>

# Orders (always previews first; --dry-run never submits)
ts order place --account <id> --symbol AAPL --side buy --type market --qty 1 --dry-run
ts order routes
ts order triggers

# Live streaming (sticky-header table in a TTY; Ctrl-C to stop)
ts md stream quotes AAPL MSFT --for 30

# Any command: choose output format (works before or after the subcommand)
ts brokerage accounts --output json
ts --output csv md quotes AAPL
```

### MCP server

```bash
ts-mcp                                  # stdio (default) — for Claude Desktop / Code / Cursor
ts-mcp --transport http --port 8765     # local HTTP
ts-mcp --toolsets market,brokerage      # disable trading tools
ts-mcp --read-only                      # block all order-placement tools
```

Example Claude Desktop config:

```json
{
  "mcpServers": {
    "tradestation": { "command": "ts-mcp", "args": ["--toolsets", "market,brokerage,trading"] }
  }
}
```

### Library

```python
from tradestation import TradeStationClient
from tradestation.enums import Side
from tradestation.models import MarketOrderRequest

ts = TradeStationClient.from_default_credentials()   # reads ~/.tscli/credentials
# or: TradeStationClient.from_env()   (TS_CLIENT_ID / TS_CLIENT_SECRET / TS_REFRESH_TOKEN / TS_ENV)

quotes = ts.market_data.get_quotes(["AAPL", "MSFT"])
accounts = ts.brokerage.list_accounts()

# Preview an order without submitting it
preview = ts.order_execution.confirm_order(
    MarketOrderRequest(account_id=accounts[0].account_id, symbol="AAPL", quantity=1, side=Side.BUY)
)
```

Async + streaming:

```python
from tradestation.async_client import AsyncTradeStationClient

async with AsyncTradeStationClient.from_env() as ts:
    async for event in ts.market_data.stream_quotes(["AAPL"]):
        print(event.raw)
```

## Command reference

Every command supports `--output table|json|jsonl|csv|tsv|yaml` and `--help`. Run `ts --help`, `ts md --help`, `ts brokerage --help`, `ts order --help` to explore.

| Group | Commands |
|---|---|
| `ts auth` | `set` · `status` · `refresh` · `export` · `clear` · `doctor` · `login` |
| `ts md` | `quotes` · `bars` · `symbols` |
| `ts md crypto` | `pairs` |
| `ts md options` | `expirations` · `strikes` · `spread-types` · `chain` · `risk-reward` |
| `ts md stream` | `quotes` · `bars` · `depth-quotes` · `depth-agg` · `option-chain` · `option-quotes` |
| `ts brokerage` (alias `bk`) | `accounts` · `balances` · `bod` · `positions` · `orders` · `order` · `historical` · `wallets` |
| `ts brokerage stream` | `orders` · `order` · `positions` · `wallets` |
| `ts order` | `confirm` · `place` · `replace` · `cancel` · `routes` · `triggers` |
| `ts order group` | `confirm` · `place` (OCO / bracket / OSO, JSON spec) |
| `ts env` | `show` · `live` · `sim` |

Streaming commands accept `--max N` (stop after N frames) and `--for SECONDS` (timed run). See [docs/04-cli-design.md](docs/04-cli-design.md) for the full surface.

## Credentials

`ts auth set` stores credentials at `~/.tscli/credentials`, encrypted with Fernet (key in the OS keyring, with a PBKDF2 passphrase fallback). Access tokens (20-min lifetime) are cached and refreshed proactively; rotating refresh tokens are persisted atomically. See [docs/02-auth-and-credentials.md](docs/02-auth-and-credentials.md).

For CI / containers, set `TS_CLIENT_ID`, `TS_CLIENT_SECRET`, `TS_REFRESH_TOKEN`, `TS_ENV=sim` and use `from_env()` / `ts-mcp --allow-env-fallback`.

## Development

```bash
git clone git@github.com:jonathansudhakar1/tradestation-cli-mcp.git
cd tradestation-cli-mcp
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

make test        # pytest -m "not live"
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict

# Live tests hit sim-api.tradestation.com using .env (see .env.example)
pytest -m live
```

Models are partly generated from the vendored TradeStation OpenAPI spec; see [docs/09-codegen-strategy.md](docs/09-codegen-strategy.md).

## Design docs

1. [docs/00-overview.md](docs/00-overview.md) — architecture, goals, prior art.
2. [docs/01-project-structure.md](docs/01-project-structure.md) — layout, packaging, entry points.
3. [docs/02-auth-and-credentials.md](docs/02-auth-and-credentials.md) — refresh-token flow, encrypted store.
4. [docs/03-endpoint-inventory.md](docs/03-endpoint-inventory.md) — every v3 endpoint wrapped.
5. [docs/04-cli-design.md](docs/04-cli-design.md) — full CLI surface.
6. [docs/05-python-library.md](docs/05-python-library.md) — services, models, sync/async, streaming.
7. [docs/06-mcp-server.md](docs/06-mcp-server.md) — FastMCP tools, transports, safety.
8. [docs/07-output-style.md](docs/07-output-style.md) — Rich palette and table formats.
9. [docs/08-references.md](docs/08-references.md) — TradeStation docs + prior art.
10. [docs/09-codegen-strategy.md](docs/09-codegen-strategy.md) — codegen + spec pinning.

## License

MIT — see [LICENSE](LICENSE).
