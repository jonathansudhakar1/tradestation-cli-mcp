# tradestationcli — TradeStation Python Library, CLI & MCP Server

A monorepo containing three pip-installable, independently versioned packages built on top of the [TradeStation v3 REST API](https://api.tradestation.com/docs/):

| Package | Purpose | Install |
|---|---|---|
| `tradestation` | Typed Python client library (sync + async, streaming, models) | `pip install tradestation` |
| `tscli` | Rich-formatted CLI wrapping the library | `pip install tscli` |
| `tradestation-mcp` | Local MCP server exposing the API to LLM tools (Claude, Cursor, …) | `pip install tradestation-mcp` |

The CLI and MCP server depend on the library; the library has zero opinions about how it is consumed.

---

## Status

**Design phase.** No code has been written. This repo currently contains the design docs only.

## Design docs

Read in this order:

1. **[docs/00-overview.md](docs/00-overview.md)** — architecture, goals, non-goals, prior art studied.
2. **[docs/01-project-structure.md](docs/01-project-structure.md)** — monorepo layout, packaging, versioning, release flow.
3. **[docs/02-auth-and-credentials.md](docs/02-auth-and-credentials.md)** — refresh-token flow, `~/.tscli/credentials` format, encryption, refresh policy.
4. **[docs/03-endpoint-inventory.md](docs/03-endpoint-inventory.md)** — canonical list of **every** TradeStation v3 endpoint we wrap.
5. **[docs/04-cli-design.md](docs/04-cli-design.md)** — full CLI surface, one command per endpoint, examples.
6. **[docs/05-python-library.md](docs/05-python-library.md)** — service split, models, sync/async, streaming, errors.
7. **[docs/06-mcp-server.md](docs/06-mcp-server.md)** — FastMCP tool layout, transport, toolsets, safety guards.
8. **[docs/07-output-style.md](docs/07-output-style.md)** — Rich color palette, table formats, progress, prompts.
9. **[docs/08-references.md](docs/08-references.md)** — links to TradeStation docs, prior art repos.

## Quick example (target UX)

```bash
# One-time credential setup (prompts for everything; stores encrypted)
ts auth set

# Verify
ts auth status

# Get a quote
ts md quotes AAPL MSFT NVDA

# List accounts and balances
ts brokerage accounts
ts brokerage balances 11111111

# Place a market order (dry-run shows the confirm preview)
ts order place --account 11111111 --symbol AAPL --qty 100 --side buy --type market --dry-run

# Stream live quotes (Ctrl-C to stop)
ts md stream quotes AAPL MSFT
```

```bash
# Run the MCP server (stdio by default)
ts-mcp                                  # stdio
ts-mcp --transport http --port 8765     # local HTTP for browser-based clients
```

```python
# Library
from tradestation import TradeStationClient
from tradestation.models import MarketOrderRequest

ts = TradeStationClient.from_default_credentials()  # reads ~/.tscli/credentials
quotes = ts.market_data.get_quotes(["AAPL", "MSFT"])
order = ts.order_execution.place_order(MarketOrderRequest(
    account_id="11111111", symbol="AAPL", quantity=100, side="Buy"
))
```
