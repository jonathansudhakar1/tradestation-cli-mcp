# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] — 2026-06-01

### Added

- Wired every documented CLI command that existed in the library but was
  missing from the CLI — so the documented surface is now actually runnable:
  - `ts md options strikes` (B9), `ts md options risk-reward` (B11)
  - `ts md stream depth-quotes` (B14), `depth-agg` (B15), `option-chain` (B16),
    `option-quotes` (B17)
  - `ts brokerage stream order <id>` (C11)
  - `ts order group confirm` / `ts order group place` (D5/D6) — OCO / bracket /
    OSO groups from a JSON spec (`--file`, `--json`, or stdin)
- README command-reference table and a test guarding the full command surface.

### Fixed

- CI lint/format failures on the 0.2.0 commit (`_DEFAULT_SCOPE` wrapping and an
  unused `noqa`) that prevented the release build from going green.
- Python 3.10 `StrEnum` backport didn't override `__str__`/`__format__`, so
  `str(member)` returned `"Environment.SIM"` instead of `"sim"` — corrupting the
  serialized credentials `environment` field on 3.10. Now matches native 3.11+
  `enum.StrEnum`, with `environment` serialized from `.value` explicitly.

## [0.2.0] — 2026-06-01

### Security

- **`ts auth set` now encrypts credentials at rest by default.** Previously the
  CLI always wrote the credentials file in plaintext, silently ignoring the
  `--encrypt` flag (which defaulted to on). Credentials are now Fernet-encrypted
  via the OS keyring (or `TSCLI_PASSPHRASE`); plaintext requires an explicit
  `--no-encrypt --i-understand-the-risk`, and setup fails with a clear message
  when no key source is available rather than writing plaintext. `status`,
  `refresh`, `export`, and `doctor` decrypt transparently.

### Added

- **`ts md options chain`** — full option chain snapshot for one expiration,
  rendered as `◀ CALLS │ Strike │ PUTS ▶` with the ATM strike highlighted.
  Selects the nearest expiration by default, or `--date` / `--dte`; `--strikes`
  centers N strikes on the money; `--columns` chooses the per-side fields.

### Changed

- Default OAuth scopes broadened to
  `openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access`
  so quotes, market depth, crypto, and option-spread data work out of the box.
- `tomli` is now a declared dependency on Python < 3.11 (was relied on but
  undeclared).

### Fixed

- `ts brokerage accounts` showed Equity / BuyingPower as `0.00`: those fields
  come from the C2 balances endpoint, not C1. The accounts view now merges
  balances and shows real figures (or `—` when unavailable).
- Stale docstrings that described shipped MarketData/Brokerage/streaming code as
  unimplemented "Phase 2" scaffolding.

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
