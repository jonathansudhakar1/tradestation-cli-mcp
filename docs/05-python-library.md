# 05 — Python Library (`tradestation`)

The library is the `tradestation` Python package: `client.py`, `services/`, `models/`, `auth.py`, `transport.py`, `streaming.py`, `errors.py`, `enums.py`. It lives at `src/tradestation/` (excluding the `cli/` and `mcp/` sub-packages, which depend on it).

Distributed as part of `tradestation-cli-mcp`. `pip install tradestation-cli-mcp` makes it importable as `import tradestation`. (The distribution name and import name differ — same pattern as `scikit-learn` → `import sklearn`.) Users who want only the library simply don't invoke the `ts` or `ts-mcp` console scripts; nothing else changes.

## Design principles

1. **Sync facade over an async core.** The wire protocol is async (`httpx.AsyncClient`); we expose both a sync `TradeStationClient` and an `AsyncTradeStationClient`. Each sync method is a 3-line `anyio.from_thread` shim over the async implementation. One source of truth, two ergonomic surfaces.
2. **One client, three service properties.** `client.market_data`, `client.brokerage`, `client.order_execution`. Matches TradeStation's own grouping and the scope split (`MarketData` / `ReadAccount` / `Trade`).
3. **Pydantic v2 models for everything.** Requests and responses. No raw dicts cross the API boundary. JSON-Schema generation is free, which the MCP server uses.
4. **Pluggable transport.** The HTTP layer is a single `Transport` class; tests inject a fake. No global state, no module-level singletons.
5. **No async/sync function-color tax for streams.** Streams are `AsyncIterator[T]` on the async client and a generator on the sync client (background thread + queue). Both close cleanly.

## Public surface (entry points)

```python
from tradestation import (
    TradeStationClient,           # sync facade
    AsyncTradeStationClient,      # native async
    Credentials,                  # credential dataclass + loaders
    Environment,                  # Enum: LIVE | SIM
)

from tradestation.models import (
    Quote, Bar, Symbol, SymbolList, CryptoPair,
    OptionExpiration, OptionStrike, OptionSpreadType, OptionRiskReward,
    Account, Balances, BeginningOfDayBalances, Position, Order, HistoricalOrder, Wallet,
    OrderRequest, MarketOrderRequest, LimitOrderRequest, StopOrderRequest, StopLimitOrderRequest,
    OptionOrderRequest, OrderGroupRequest, OrderConfirmation,
    ActivationTrigger, ExecutionRoute,
)

from tradestation.errors import (
    TradeStationError,
    AuthError, RefreshTokenExpired,
    RateLimitError, NetworkError, TimeoutError,
    ApiError,                 # 4xx with TS payload
    OrderRejectedError,
    StreamError, StreamHeartbeat,
)
```

## Construction

```python
# 1. Default credentials at ~/.tscli/credentials
ts = TradeStationClient.from_default_credentials()

# 2. Explicit
ts = TradeStationClient(Credentials(
    client_id="...", client_secret="...", refresh_token="...",
    scope="openid profile MarketData ReadAccount Trade Matrix Crypto OptionSpreads offline_access",
    environment=Environment.LIVE,
))

# 3. From env vars (TS_CLIENT_ID, TS_CLIENT_SECRET, TS_REFRESH_TOKEN, TS_ENV)
ts = TradeStationClient.from_env()

# 4. Explicit profile under ~/.tscli/profiles/<name>/
ts = TradeStationClient.from_profile("paper")

# 5. With overrides
ts = TradeStationClient.from_default_credentials(
    timeout=60.0, retries=5, environment=Environment.SIM,
    user_agent="my-strategy/0.3",
)
```

Same constructors exist on `AsyncTradeStationClient`. The two share zero state — pick one per process.

## Service surface (1 method per inventory row)

```python
# B. MarketData
ts.market_data.get_bars(symbol, interval=1, unit=BarUnit.MINUTE, barsback=200)   # B1
ts.market_data.get_quotes(["AAPL","MSFT"])                                       # B2
ts.market_data.get_symbols(["AAPL","ES.M26"])                                    # B3
ts.market_data.list_symbol_lists()                                               # B4
ts.market_data.get_symbol_list(list_id)                                          # B5
ts.market_data.get_symbol_list_symbols(list_id)                                  # B6
ts.market_data.list_crypto_pairs()                                               # B7
ts.market_data.get_option_expirations("AAPL", strike=None)                       # B8
ts.market_data.get_option_strikes("AAPL", expiration=..., spread_type=None)      # B9
ts.market_data.list_option_spread_types()                                        # B10
ts.market_data.option_risk_reward(legs=[...], entry=3.30)                        # B11

# Streaming — async iterator
async for bar  in ts.market_data.stream_bars("AAPL", ...):           ...        # B12
async for q    in ts.market_data.stream_quotes(["AAPL"]):           ...        # B13
async for d    in ts.market_data.stream_depth_quotes("AAPL"):       ...        # B14
async for d    in ts.market_data.stream_depth_aggregates("AAPL"):   ...        # B15
async for c    in ts.market_data.stream_option_chain("AAPL", exp): ...        # B16
async for q    in ts.market_data.stream_option_quotes(legs):       ...        # B17

# C. Brokerage
ts.brokerage.list_accounts()                                                     # C1
ts.brokerage.get_balances(["11111111"])                                          # C2
ts.brokerage.get_bod_balances(["11111111"])                                      # C3
ts.brokerage.get_positions(["11111111"])                                         # C4
ts.brokerage.get_orders(["11111111"])                                            # C5
ts.brokerage.get_orders_by_id(["11111111"], ["835711"])                          # C6
ts.brokerage.get_historical_orders(["11111111"], since=date(2026,1,1))           # C7
ts.brokerage.get_historical_orders_by_id(["11111111"], ["835711"])               # C8
ts.brokerage.get_wallets(["11111111"])                                           # C9

async for o    in ts.brokerage.stream_orders(["11111111"]):     ...             # C10
async for o    in ts.brokerage.stream_orders_by_id(...):        ...             # C11
async for p    in ts.brokerage.stream_positions(["11111111"]): ...              # C12
async for w    in ts.brokerage.stream_wallets(["11111111"]):    ...             # C13

# D. OrderExecution
ts.order_execution.confirm_order(req)                                            # D1
ts.order_execution.place_order(req)                                              # D2
ts.order_execution.replace_order(order_id, req)                                  # D3
ts.order_execution.cancel_order(order_id)                                        # D4
ts.order_execution.confirm_order_group(req)                                      # D5
ts.order_execution.place_order_group(req)                                        # D6
ts.order_execution.list_activation_triggers()                                    # D7
ts.order_execution.list_routes()                                                 # D8
```

Async client: identical method names, all `async def`. Streams use `await` + `async for`. Sync streams are regular generators.

## Models (sketch)

```python
# tradestation/models/orders.py
from pydantic import BaseModel, Field
from .enums import Side, TimeInForce, OrderType

class _BaseOrderRequest(BaseModel):
    account_id: str
    symbol: str
    quantity: int
    side: Side
    time_in_force: TimeInForce = TimeInForce.DAY
    route: str = "AUTO"
    all_or_none: bool = False
    duration: dict | None = None         # gtd date when TIF=GTD
    activation_trigger: str | None = None

class MarketOrderRequest(_BaseOrderRequest):
    type: OrderType = Field(default=OrderType.MARKET, frozen=True)

class LimitOrderRequest(_BaseOrderRequest):
    type: OrderType = Field(default=OrderType.LIMIT, frozen=True)
    limit_price: float

class StopOrderRequest(_BaseOrderRequest):
    type: OrderType = Field(default=OrderType.STOP, frozen=True)
    stop_price: float

class StopLimitOrderRequest(_BaseOrderRequest):
    type: OrderType = Field(default=OrderType.STOP_LIMIT, frozen=True)
    stop_price: float
    limit_price: float
```

All models have a `model_dump_api()` method that emits the exact JSON shape TradeStation expects (PascalCase field names where the API uses them). The MCP server serializes its tools from `model_json_schema()`.

## Streaming primitives

```python
class StreamEvent(BaseModel):
    """Envelope for streaming responses."""
    raw: dict | None = None      # always present
    is_heartbeat: bool = False
    error: str | None = None     # set on error frames

# Concrete event types subclass for each stream — Quote, Bar, OrderEvent, etc.
```

The iterator emits typed events. By default heartbeats are filtered; pass `include_heartbeats=True` to receive `StreamHeartbeat`. On error frame, an exception is raised; the user can catch `StreamError` and resume.

## Errors

```
TradeStationError                  (base)
├── AuthError
│   ├── NoCredentialsError
│   └── RefreshTokenExpired
├── NetworkError
│   ├── TimeoutError
│   └── ConnectionResetError
├── RateLimitError
├── ApiError                        (4xx with TS body)
│   ├── ValidationError             (400 with field-level messages)
│   ├── NotFoundError               (404)
│   └── ServerError                 (5xx)
├── OrderRejectedError              (D-series rejections)
└── StreamError                     (mid-stream failure)
```

Each error includes `request_id` (from TS's `X-Request-Id`), `status`, `payload`, and a `human_message()` that the CLI surfaces verbatim.

## Concurrency, rate limiting, retries

- **Connection pooling** via `httpx.AsyncClient` (one per `AsyncTradeStationClient`).
- **Token-bucket rate limiter** per endpoint family (matches TS's documented buckets) with peek-ahead. 429 `Retry-After` honored.
- **Retries**: idempotent verbs (`GET`, `PUT`/`DELETE` on order endpoints are *not* retried automatically — too dangerous; only on explicit opt-in) with exponential backoff + jitter. `POST` to `/orderexecution/orders` is **never** auto-retried.
- **Timeouts**: 30 s default for REST; streams have read-timeout = `keep-alive interval × 2` (currently 35 s) with auto-reconnect bounded by `max_reconnects`.

## Logging

`tradestation` uses a logger named `tradestation`. By default it logs `INFO`-level lifecycle events (auth refresh, stream connect/disconnect) and `DEBUG`-level request lines (URL + status, no bodies). A redaction filter wipes `Authorization`, `client_secret`, `refresh_token` everywhere. CLI `-v` and `-vv` raise the level.

## Optional `pandas` integration

```python
df = ts.market_data.get_bars("AAPL", interval=1, unit=BarUnit.MINUTE, barsback=200).to_frame()
df_quotes = ts.market_data.get_quotes(["AAPL","MSFT"]).to_frame()
```

Only available when `pip install "tradestation-cli-mcp[pandas]"`.

## Testing posture

- **Unit:** every model round-trips through `model_dump_api()` → `model_validate`.
- **Recorded HTTP:** `vcrpy` cassettes captured against TS SIM, redacted of tokens; replayed offline in CI.
- **Streaming:** an in-process fake HTTP/2 server feeds canned chunked frames.
- **Property tests:** `hypothesis` strategies for orders ensure no invalid combination passes validation.
- **Coverage:** ≥ 80 % overall, 100 % on `auth.py`, `credentials.py`, `errors.py`.
