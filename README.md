# tradestation-cli-mcp

A single Python package that provides three things on top of the [TradeStation v3 REST API](https://api.tradestation.com/docs/):

| Use it as… | What it gives you | How to invoke |
|---|---|---|
| A **Python library** | `TradeStationClient` (sync & async), Pydantic models, streaming iterators | `import tradestation` |
| A **CLI** | `ts` — Rich-formatted, colorful command-line tool covering every endpoint | `ts …` |
| An **MCP server** | `ts-mcp` — local Model Context Protocol server for Claude Code, Cursor, Windsurf, … | `ts-mcp` |

**One install gives you all three:**

```bash
pip install tradestation-cli-mcp
```

The package distributes the **library** (`tradestation/…`), a **CLI** built on top of it (`tradestation/cli/…`), and an **MCP server** also built on top of it (`tradestation/mcp/…`). The library is the only thing that speaks HTTP — the CLI and MCP server are thin layers over it.

---

## Status

**Design phase.** No code has been written. This repo currently contains the design docs only.

## Design docs

Read in this order:

1. **[docs/00-overview.md](docs/00-overview.md)** — architecture, goals, non-goals, prior art studied.
2. **[docs/01-project-structure.md](docs/01-project-structure.md)** — single-package layout, packaging, entry points, release flow.
3. **[docs/02-auth-and-credentials.md](docs/02-auth-and-credentials.md)** — refresh-token flow, `~/.tscli/credentials` format, encryption, refresh policy.
4. **[docs/03-endpoint-inventory.md](docs/03-endpoint-inventory.md)** — canonical list of **every** TradeStation v3 endpoint we wrap.
5. **[docs/04-cli-design.md](docs/04-cli-design.md)** — full CLI surface, one command per endpoint, examples.
6. **[docs/05-python-library.md](docs/05-python-library.md)** — service split, models, sync/async, streaming, errors.
7. **[docs/06-mcp-server.md](docs/06-mcp-server.md)** — FastMCP tool layout, transport, toolsets, safety guards.
8. **[docs/07-output-style.md](docs/07-output-style.md)** — Rich color palette, table formats, progress, prompts.
9. **[docs/08-references.md](docs/08-references.md)** — links to TradeStation docs, prior art repos.

## Quick example (target UX)

```bash
# One-time install
pip install tradestation-cli-mcp

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

## Why one package and not three?

A single distribution means one version to pin, one release to cut, one install command, and one credential store guaranteed to be in sync across the library, CLI, and MCP server. The internal layering (library → CLI / library → MCP) is preserved as sub-packages, so the architecture story is unchanged — only the packaging is unified. See [docs/01-project-structure.md](docs/01-project-structure.md) for the layout.
