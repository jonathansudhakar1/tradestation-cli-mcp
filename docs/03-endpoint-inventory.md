# 03 — Endpoint Inventory (TradeStation v3)

The canonical list of every endpoint we wrap. Each row maps 1:1 to a library method, a CLI command, and an MCP tool. **Nothing in this table is optional** — full coverage is a release gate.

> Base URLs
> - **Live:** `https://api.tradestation.com/v3`
> - **Sim:**  `https://sim-api.tradestation.com/v3`
> - **Auth:** `https://signin.tradestation.com`

Sources cross-checked: TradeStation API docs site, the [tradestation-api Rust crate](https://docs.rs/tradestation-api) (mirror of the v3 surface), and the [tradestation.github.io/api-docs](https://tradestation.github.io/api-docs/) Swagger UI.

---

## A. Authentication  (`signin.tradestation.com`)

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| A1 | `GET`  | `/authorize` | Browser-launched authorization code grant (PKCE supported). | n/a |
| A2 | `POST` | `/oauth/token` | Exchange `authorization_code` or `refresh_token` for an access token. | n/a |
| A3 | `POST` | `/oauth/revoke` | Revoke an access or refresh token. | n/a |
| A4 | `GET`  | `/userinfo` | OIDC userinfo (returned claims depend on requested scopes). | `openid` |

> A1 + A4 are exposed in `ts auth login` only.
> A2 is internal (the library calls it; `ts auth refresh` is the user-facing trigger).
> A3 backs `ts auth clear --revoke`.

---

## B. MarketData  (`/v3/marketdata`)

### B.1 — REST

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| B1  | `GET` | `/marketdata/barcharts/{symbol}` | Historical bars. Params: `interval`, `unit`, `barsback`, `firstdate`, `lastdate`, `sessiontemplate`. | `MarketData` |
| B2  | `GET` | `/marketdata/quotes/{symbols}` | Quote snapshots for one or many comma-separated symbols. | `MarketData` |
| B3  | `GET` | `/marketdata/symbols/{symbols}` | Symbol metadata (asset type, exchange, currency, contract specs). | `MarketData` |
| B4  | `GET` | `/marketdata/symbollists` | List the user's symbol lists. | `MarketData` |
| B5  | `GET` | `/marketdata/symbollists/{symbolListID}` | A single symbol list. | `MarketData` |
| B6  | `GET` | `/marketdata/symbollists/{symbolListID}/symbols` | Symbols inside a list. | `MarketData` |
| B7  | `GET` | `/marketdata/crypto/symbolnames` | List supported crypto pairs. | `MarketData` |
| B8  | `GET` | `/marketdata/options/expirations/{underlying}` | Expirations available for an underlying. Optional `strikePrice`. | `MarketData`, `OptionSpreads` |
| B9  | `GET` | `/marketdata/options/strikes/{underlying}` | Strikes available for an underlying. Params: `expiration`, `spreadType`. | `MarketData`, `OptionSpreads` |
| B10 | `GET` | `/marketdata/options/spreadtypes` | Supported option spread types (vertical, calendar, butterfly, …). | `MarketData`, `OptionSpreads` |
| B11 | `POST`| `/marketdata/options/riskreward` | Risk/reward analysis for a multi-leg position. Body: legs + entry price. | `MarketData`, `OptionSpreads` |

### B.2 — Streaming (HTTP chunked-transfer; one JSON message per line)

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| B12 | `GET` | `/marketdata/stream/barcharts/{symbol}` | Live bar updates. Same query params as B1 plus session controls. | `MarketData` |
| B13 | `GET` | `/marketdata/stream/quotes/{symbols}` | Live quote stream. | `MarketData` |
| B14 | `GET` | `/marketdata/stream/marketdepth/quotes/{symbol}` | Level-2 individual quote stream. | `MarketData`, `Matrix` |
| B15 | `GET` | `/marketdata/stream/marketdepth/aggregates/{symbol}` | Level-2 aggregate depth stream. | `MarketData`, `Matrix` |
| B16 | `GET` | `/marketdata/stream/options/chains/{underlying}` | Live option chain stream. | `MarketData`, `OptionSpreads` |
| B17 | `GET` | `/marketdata/stream/options/quotes` | Live option quote stream (legs as query). | `MarketData`, `OptionSpreads` |

---

## C. Brokerage  (`/v3/brokerage`)

### C.1 — REST

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| C1 | `GET` | `/brokerage/accounts` | Accounts for the authenticated user. | `ReadAccount` |
| C2 | `GET` | `/brokerage/accounts/{accountIDs}/balances` | Real-time balances. Multi-account via comma list. | `ReadAccount` |
| C3 | `GET` | `/brokerage/accounts/{accountIDs}/balances/bod` | Beginning-of-day balances. | `ReadAccount` |
| C4 | `GET` | `/brokerage/accounts/{accountIDs}/positions` | Open positions. | `ReadAccount` |
| C5 | `GET` | `/brokerage/accounts/{accountIDs}/orders` | Today's orders. | `ReadAccount` |
| C6 | `GET` | `/brokerage/accounts/{accountIDs}/orders/{orderIDs}` | Orders by ID. | `ReadAccount` |
| C7 | `GET` | `/brokerage/accounts/{accountIDs}/historicalorders` | Historical orders since `since` date. | `ReadAccount` |
| C8 | `GET` | `/brokerage/accounts/{accountIDs}/historicalorders/{orderIDs}` | Historical orders by ID. | `ReadAccount` |
| C9 | `GET` | `/brokerage/accounts/{accountIDs}/wallets` | Crypto wallets for an account. | `ReadAccount` |

### C.2 — Streaming

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| C10 | `GET` | `/brokerage/stream/accounts/{accountIDs}/orders` | Live order events for the account(s). | `ReadAccount` |
| C11 | `GET` | `/brokerage/stream/accounts/{accountIDs}/orders/{orderIDs}` | Live order events for specific orders. | `ReadAccount` |
| C12 | `GET` | `/brokerage/stream/accounts/{accountIDs}/positions` | Live position updates. | `ReadAccount` |
| C13 | `GET` | `/brokerage/stream/accounts/{accountIDs}/wallets` | Live wallet updates. | `ReadAccount` |

---

## D. OrderExecution  (`/v3/orderexecution`)

| # | Method | Path | Purpose | Scope |
|---|---|---|---|---|
| D1 | `POST`   | `/orderexecution/orderconfirm` | Preview an order without submitting; returns fees & buying-power impact. | `Trade` |
| D2 | `POST`   | `/orderexecution/orders` | Submit a single order. | `Trade` |
| D3 | `PUT`    | `/orderexecution/orders/{orderID}` | Replace/modify an existing order. | `Trade` |
| D4 | `DELETE` | `/orderexecution/orders/{orderID}` | Cancel an order. | `Trade` |
| D5 | `POST`   | `/orderexecution/ordergroupconfirm` | Preview a grouped order (OCO / OSO / bracket). | `Trade` |
| D6 | `POST`   | `/orderexecution/ordergroups` | Submit a grouped order. | `Trade` |
| D7 | `GET`    | `/orderexecution/activationtriggers` | List conditional activation triggers (e.g., STT for stop on trade). | `Trade` |
| D8 | `GET`    | `/orderexecution/routes` | List available execution routes. | `Trade` |

---

## Coverage matrix

| Category | Endpoints | Library methods | CLI commands | MCP tools |
|---|---:|---:|---:|---:|
| Auth (used internally) | 4 | 4 | 5 (auth set/status/refresh/login/clear/doctor) | 1 (`auth_status`) |
| MarketData (REST) | 11 | 11 | 11 | 11 |
| MarketData (streaming) | 6 | 6 | 6 | 6 |
| Brokerage (REST) | 9 | 9 | 9 | 9 |
| Brokerage (streaming) | 4 | 4 | 4 | 4 |
| OrderExecution | 8 | 8 | 8 | 8 |
| **Total** | **42** | **42** | **43+** | **39+** |

CLI count exceeds library count because of multiple `auth` UX subcommands that all consume the same library primitives. MCP count is lower because some destructive operations are gated behind a single `place_order_unconfirmed` vs. `place_order` flag pattern rather than a separate tool (see [06-mcp-server.md](06-mcp-server.md)).

## Notes & gotchas

- Many endpoints accept **comma-separated** identifiers in path segments (`{accountIDs}`, `{symbols}`, `{orderIDs}`). The library accepts `list[str]` and joins. The CLI accepts repeated `--account` flags **or** a single comma-separated arg.
- Streaming endpoints return `application/vnd.tradestation.streams.v3+json` chunked transfer. The library exposes them as `AsyncIterator[Model]`.
- Heartbeats: TradeStation interleaves heartbeat lines into streams. The library filters these out by default and surfaces them as `StreamHeartbeat` events when `include_heartbeats=True`.
- Rate limits: per [TradeStation rate limiting docs](https://api.tradestation.com/docs/fundamentals/rate-limiting/), the library applies a token-bucket per resource family and parses `Retry-After` headers on 429.
- SIM vs LIVE: a flag at credential-set time, swappable per call via `client.environment("sim")`. The CLI exposes `--sim` on every command and `ts env sim` to flip the default.
