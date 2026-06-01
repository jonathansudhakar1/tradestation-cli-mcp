# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-06-01

First release. Full coverage of the TradeStation v3 API across a library, a
CLI, and an MCP server — all in one pip-installable distribution.

### Added

- **Library (`tradestation`)** — sync `TradeStationClient` + `AsyncTradeStationClient`,
  Pydantic v2 models, and `httpx`-based transport with retries, token-bucket
  rate limiting, and secret redaction.
  - MarketData (B1–B11): quotes, bars, symbols, symbol lists, crypto pairs,
    option expirations / strikes / spread-types / risk-reward.
  - Brokerage (C1–C9): accounts, balances, BOD balances, positions, orders,
    orders-by-id, historical orders (×2), wallets.
  - OrderExecution (D1–D8): confirm, place, replace, cancel, group confirm/place,
    activation triggers, routes.
  - Streaming (B12–B17, C10–C13): quotes, bars, market depth (×2), option chain,
    option quotes, order/position/wallet events — NDJSON chunked-transfer with
    heartbeat filtering and deterministic close.
- **CLI (`ts`)** — Rich-formatted commands for every endpoint, with
  `table`/`json`/`jsonl`/`csv`/`tsv`/`yaml` output (accepted before or after the
  subcommand), a sticky-header live table for quote streams, and confirm-token
  prompts for destructive order actions.
- **MCP server (`ts-mcp`)** — FastMCP server exposing 38 tools over stdio or
  local HTTP, with toolset allowlists, a confirm-token safety gate for trading
  tools, notional caps, and a symbol allowlist. Streaming endpoints exposed as
  bounded *collect* tools.
- **Auth** — `ts auth set/status/refresh/clear/doctor`; encrypted credential
  store at `~/.tscli/credentials` (Fernet + OS keyring, PBKDF2 passphrase
  fallback); proactive access-token refresh and atomic refresh-token rotation.
- **Codegen** — Pydantic models partly generated from the vendored, pinned
  TradeStation OpenAPI spec; `scripts/verify_pin.py` guards the pin in CI.
- Default environment is **sim** (paper trading). Equities, futures, and crypto
  supported.

### Verified

- ~550 unit/CLI/MCP tests plus live integration tests against
  `sim-api.tradestation.com`. CI runs lint, type-check, and the full suite on
  Python 3.10–3.13.

[Unreleased]: https://github.com/jonathansudhakar1/tradestation-cli-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jonathansudhakar1/tradestation-cli-mcp/releases/tag/v0.1.0
