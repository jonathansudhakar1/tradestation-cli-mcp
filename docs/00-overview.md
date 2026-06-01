# 00 — Overview

## What we are building

Three pip-installable Python packages in a single monorepo:

```
   ┌──────────────────┐       ┌────────────────────┐
   │  tscli (CLI)     │       │  tradestation-mcp  │
   │  entry point: ts │       │  entry: ts-mcp     │
   └────────┬─────────┘       └──────────┬─────────┘
            │                            │
            └────────────┬───────────────┘
                         ▼
              ┌──────────────────────┐
              │  tradestation        │   ← the only HTTP client
              │  (Python library)    │
              └──────────┬───────────┘
                         ▼
            TradeStation v3 REST + streaming
```

All three packages share **one** credential store at `~/.tscli/credentials`. The CLI's `ts auth set` command writes it; the library reads it; the MCP server reads it. The library is the single point of HTTP contact — neither the CLI nor MCP server makes their own HTTP calls.

## Goals

1. **Complete API coverage.** Every endpoint listed in [03-endpoint-inventory.md](03-endpoint-inventory.md) has a library method, a CLI command, and an MCP tool. Nothing is omitted.
2. **One install command per artifact.** `pip install tradestation`, `pip install tscli`, `pip install tradestation-mcp` — no extras, no submodules to learn.
3. **Secure-by-default credentials.** Secrets at rest are encrypted; access tokens are cached and auto-refreshed; nothing is logged.
4. **Beautiful CLI.** Every command uses [Rich](https://rich.readthedocs.io/) tables, progress bars, syntax-highlighted JSON, and a coherent color palette (see [07-output-style.md](07-output-style.md)). No raw curl-style dumps.
5. **LLM-ready.** The MCP server exposes the full surface as discrete tools with JSON Schema, runs over stdio (default) or local HTTP, and ships safety guards around destructive actions.

## Non-goals

- We do **not** re-implement TradeStation EasyLanguage strategies.
- We do **not** provide a backtesting framework. (The library returns clean DataFrames/Pydantic models; do your own analytics.)
- We do **not** broker the initial OAuth code-grant browser flow as a hard requirement. The user supplies a long-lived refresh token (per the user's request). A best-effort `ts auth login` flow is included as a convenience but is optional.
- We do **not** support v2 endpoints — TradeStation marks v3 as recommended.

## Prior art studied

| Repo / Product | What we borrow | What we improve |
|---|---|---|
| [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | Pydantic request/response models; per-asset-class data clients | We unify into one `TradeStationClient` because TS scopes are not asset-class-split. |
| [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) | FastMCP + OpenAPI-driven tool registration; toolset allowlists; stdio + HTTP transports; safety-confirmation overrides for trading | We persist credentials encrypted on disk instead of env-only (per user's request) and reuse the CLI's credential store. |
| [mxcoppell/tradestation-api-python](https://github.com/mxcoppell/tradestation-api-python) | Service-per-category split (`market_data`, `brokerage`, `order_execution`), rate limiter, async-first | We add a sync facade and a CLI/MCP layer. |
| [mxcoppell/tradestation-api-ts](https://github.com/mxcoppell/tradestation-api-ts) | Streaming via EventEmitter pattern; request-client interceptor stack | We use `httpx` + async iterators in Python. |
| [areed1192/tradestation-python-api](https://github.com/areed1192/tradestation-python-api) | Reference for v2→v3 endpoint mapping | Out of date; we target v3 directly. |
| `tradestation-api` Rust crate ([docs.rs](https://docs.rs/tradestation-api)) | Canonical mirror of v3 surface (used to cross-check our inventory) | n/a (read-only reference). |
| [Click](https://click.palletsprojects.com/) / [Typer](https://typer.tiangolo.com/) / [Rich](https://rich.readthedocs.io/) | Typer for command tree, Rich for rendering | — |
| [keyring](https://pypi.org/project/keyring/) + [cryptography](https://cryptography.io/) | OS keychain integration + Fernet symmetric encryption fallback | — |

## How the three packages share code

- The library defines `TradeStationClient`, models, exceptions, streaming iterators, and a `Credentials` helper that knows how to read `~/.tscli/credentials`.
- `tscli` depends on `tradestation` and adds Typer commands + Rich rendering. It also owns the `ts auth set` / `ts auth login` commands (writing the credential file).
- `tradestation-mcp` depends on `tradestation` and adds FastMCP tool registrations. It does **not** depend on `tscli`, so installing only the MCP server does not pull Rich/Typer.

See [01-project-structure.md](01-project-structure.md) for the exact directory layout and `pyproject.toml` strategy.
