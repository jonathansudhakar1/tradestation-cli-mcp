"""Bare async HTTP callables — one function per operationId in vendor/swagger.yaml.

These are INTERNAL. Users interact with the curated service methods in
``tradestation.services.*`` which wrap these operations.

Every function accepts a ``transport`` (``tradestation.transport.Transport``)
as the first argument and keyword arguments matching the swagger parameters.
Path parameters are required positional-style keyword args; query params and
body params are optional keyword args.

All functions are ``async def`` and return a plain ``dict[str, Any]`` decoded
from the JSON response. Streaming operations return an ``AsyncIterator[bytes]``
of raw newline-delimited frames.

Inventory ID references (from docs/03-endpoint-inventory.md) appear in each
docstring as ``Maps to: <ID> <METHOD> <PATH>``.

DO NOT import or call these directly — use ``tradestation.services.*``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tradestation.transport import Transport

# ---------------------------------------------------------------------------
# A. Authentication  (signin.tradestation.com — handled in auth.py, stubbed here)
# ---------------------------------------------------------------------------


async def authorize(transport: Transport, **params: Any) -> dict[str, Any]:
    """Browser-launched authorization code grant (PKCE supported).

    Maps to: A1 GET /authorize

    Note: This endpoint opens a browser redirect. The actual flow is handled
    by tradestation.auth — this stub exists for inventory coverage.
    """
    return await transport.request("GET", "/authorize", params=params or None)


async def token(
    transport: Transport,
    *,
    grant_type: str,
    code: str | None = None,
    refresh_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Exchange authorization_code or refresh_token for an access token.

    Maps to: A2 POST /oauth/token
    """
    body: dict[str, Any] = {"grant_type": grant_type}
    if code is not None:
        body["code"] = code
    if refresh_token is not None:
        body["refresh_token"] = refresh_token
    if client_id is not None:
        body["client_id"] = client_id
    if client_secret is not None:
        body["client_secret"] = client_secret
    if redirect_uri is not None:
        body["redirect_uri"] = redirect_uri
    body.update(kwargs)
    return await transport.request("POST", "/oauth/token", json=body)


async def revoke(
    transport: Transport,
    *,
    token: str,
    token_type_hint: str | None = None,
) -> dict[str, Any]:
    """Revoke an access or refresh token.

    Maps to: A3 POST /oauth/revoke
    """
    body: dict[str, Any] = {"token": token}
    if token_type_hint is not None:
        body["token_type_hint"] = token_type_hint
    return await transport.request("POST", "/oauth/revoke", json=body)


async def userinfo(transport: Transport) -> dict[str, Any]:
    """OIDC userinfo endpoint; returned claims depend on requested scopes.

    Maps to: A4 GET /userinfo

    Requires scope: openid
    """
    return await transport.request("GET", "/userinfo")


# ---------------------------------------------------------------------------
# B. MarketData  (/v3/marketdata — v3 paths; v2 swagger operationIds mapped here)
# ---------------------------------------------------------------------------


async def get_bars(
    transport: Transport,
    *,
    symbol: str,
    interval: int | None = None,
    unit: str | None = None,
    barsback: int | None = None,
    firstdate: str | None = None,
    lastdate: str | None = None,
    sessiontemplate: str | None = None,
) -> dict[str, Any]:
    """Fetch historical bars for a symbol.

    Maps to: B1 GET /marketdata/barcharts/{symbol}

    Args:
        symbol: The ticker symbol (e.g. "AAPL", "ES.M26").
        interval: Bar interval count (e.g. 1, 5, 15).
        unit: Bar unit ("Minute", "Hour", "Daily", "Weekly", "Monthly").
        barsback: Number of bars to return (counting back from lastdate).
        firstdate: Start date/datetime in ISO 8601 or MM/DD/YYYY format.
        lastdate: End date/datetime in ISO 8601 or MM/DD/YYYY format.
        sessiontemplate: Session template name (e.g. "Default", "USEQPre").
    """
    query: dict[str, Any] = {}
    if interval is not None:
        query["interval"] = interval
    if unit is not None:
        query["unit"] = unit
    if barsback is not None:
        query["barsback"] = barsback
    if firstdate is not None:
        query["firstdate"] = firstdate
    if lastdate is not None:
        query["lastdate"] = lastdate
    if sessiontemplate is not None:
        query["sessiontemplate"] = sessiontemplate
    return await transport.request(
        "GET",
        f"/marketdata/barcharts/{symbol}",
        params=query or None,
    )


async def get_quotes(
    transport: Transport,
    *,
    symbols: str,
) -> dict[str, Any]:
    """Fetch quote snapshots for one or many comma-separated symbols.

    Maps to: B2 GET /marketdata/quotes/{symbols}

    Also maps swagger operationId: getQuotes (v2: GET /v2/data/quote/{symbols})

    Args:
        symbols: Comma-separated ticker symbols (e.g. "AAPL,MSFT,GOOG").
    """
    return await transport.request("GET", f"/marketdata/quotes/{symbols}")


async def get_symbols(
    transport: Transport,
    *,
    symbols: str,
) -> dict[str, Any]:
    """Fetch symbol metadata for one or many comma-separated symbols.

    Maps to: B3 GET /marketdata/symbols/{symbols}

    Args:
        symbols: Comma-separated ticker symbols.
    """
    return await transport.request("GET", f"/marketdata/symbols/{symbols}")


async def get_symbol_lists(transport: Transport) -> dict[str, Any]:
    """List the authenticated user's symbol lists.

    Maps to: B4 GET /marketdata/symbollists

    Also maps swagger operationId: getSymbolLists (v2: GET /v2/data/symbollists)
    """
    return await transport.request("GET", "/marketdata/symbollists")


async def get_symbol_list_by_id(
    transport: Transport,
    *,
    symbol_list_id: str,
) -> dict[str, Any]:
    """Fetch a single symbol list by ID.

    Maps to: B5 GET /marketdata/symbollists/{symbolListID}

    Also maps swagger operationId: getSymbolListByID
    """
    return await transport.request("GET", f"/marketdata/symbollists/{symbol_list_id}")


async def get_symbol_list_symbols(
    transport: Transport,
    *,
    symbol_list_id: str,
) -> dict[str, Any]:
    """Fetch the symbols inside a symbol list.

    Maps to: B6 GET /marketdata/symbollists/{symbolListID}/symbols

    Also maps swagger operationId: getSymbolListSymbolsByID
    """
    return await transport.request("GET", f"/marketdata/symbollists/{symbol_list_id}/symbols")


async def get_crypto_symbol_names(transport: Transport) -> dict[str, Any]:
    """List supported crypto pair names.

    Maps to: B7 GET /marketdata/crypto/symbolnames

    Returns a list of supported cryptocurrency trading pairs (e.g. "BTCUSD").
    """
    return await transport.request("GET", "/marketdata/crypto/symbolnames")


async def get_option_expirations(
    transport: Transport,
    *,
    underlying: str,
    strike_price: float | None = None,
) -> dict[str, Any]:
    """Fetch option expirations available for an underlying symbol.

    Maps to: B8 GET /marketdata/options/expirations/{underlying}

    Args:
        underlying: The underlying ticker symbol (e.g. "AAPL").
        strike_price: Optional strike price filter.
    """
    query: dict[str, Any] = {}
    if strike_price is not None:
        query["strikePrice"] = strike_price
    return await transport.request(
        "GET",
        f"/marketdata/options/expirations/{underlying}",
        params=query or None,
    )


async def get_option_strikes(
    transport: Transport,
    *,
    underlying: str,
    expiration: str | None = None,
    spread_type: str | None = None,
) -> dict[str, Any]:
    """Fetch strikes available for an underlying symbol and expiration.

    Maps to: B9 GET /marketdata/options/strikes/{underlying}

    Args:
        underlying: The underlying ticker symbol.
        expiration: Expiration date in MM/DD/YYYY format.
        spread_type: Spread type filter (e.g. "Single", "Vertical").
    """
    query: dict[str, Any] = {}
    if expiration is not None:
        query["expiration"] = expiration
    if spread_type is not None:
        query["spreadType"] = spread_type
    return await transport.request(
        "GET",
        f"/marketdata/options/strikes/{underlying}",
        params=query or None,
    )


async def get_option_spread_types(transport: Transport) -> dict[str, Any]:
    """Fetch supported option spread types.

    Maps to: B10 GET /marketdata/options/spreadtypes

    Returns a list of supported spread types: Single, Vertical, Calendar,
    Butterfly, Condor, Diagonal, Collar, etc.
    """
    return await transport.request("GET", "/marketdata/options/spreadtypes")


async def option_risk_reward(
    transport: Transport,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Compute risk/reward analysis for a multi-leg option position.

    Maps to: B11 POST /marketdata/options/riskreward

    Args:
        body: Request body with legs and entry price details.
    """
    return await transport.request("POST", "/marketdata/options/riskreward", json=body)


# B.2 Streaming endpoints — return AsyncIterator[bytes] of raw frames


async def stream_bars(
    transport: Transport,
    *,
    symbol: str,
    interval: int | None = None,
    unit: str | None = None,
    barsback: int | None = None,
    firstdate: str | None = None,
    lastdate: str | None = None,
    sessiontemplate: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream live bar updates for a symbol.

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

    Also maps swagger operationIds:
    - streamBarchartsFromStartDate
    - streamBarchartsFromStartDateToEndDate
    - streamBarchartsBarsBack
    - streamBarchartsDaysBack

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {}
    if interval is not None:
        query["interval"] = interval
    if unit is not None:
        query["unit"] = unit
    if barsback is not None:
        query["barsback"] = barsback
    if firstdate is not None:
        query["firstdate"] = firstdate
    if lastdate is not None:
        query["lastdate"] = lastdate
    if sessiontemplate is not None:
        query["sessiontemplate"] = sessiontemplate
    return await transport.stream(
        f"/marketdata/stream/barcharts/{symbol}",
        params=query or None,
    )


async def stream_quotes(
    transport: Transport,
    *,
    symbols: str,
) -> AsyncIterator[bytes]:
    """Stream live quote updates for one or many comma-separated symbols.

    Maps to: B13 GET /marketdata/stream/quotes/{symbols}

    Also maps swagger operationIds:
    - streamQuotesChanges (v2: /v2/stream/quote/changes/{symbols})
    - streamQuotesSnapshots (v2: /v2/stream/quote/snapshots/{symbols})

    Args:
        symbols: Comma-separated ticker symbols.

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/marketdata/stream/quotes/{symbols}")


async def stream_market_depth_quotes(
    transport: Transport,
    *,
    symbol: str,
) -> AsyncIterator[bytes]:
    """Stream Level-2 individual market-depth quote updates for a symbol.

    Maps to: B14 GET /marketdata/stream/marketdepth/quotes/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/marketdata/stream/marketdepth/quotes/{symbol}")


async def stream_market_depth_aggregates(
    transport: Transport,
    *,
    symbol: str,
) -> AsyncIterator[bytes]:
    """Stream Level-2 aggregate market-depth updates for a symbol.

    Maps to: B15 GET /marketdata/stream/marketdepth/aggregates/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/marketdata/stream/marketdepth/aggregates/{symbol}")


async def stream_option_chain(
    transport: Transport,
    *,
    underlying: str,
    expiration: str | None = None,
    strike_price_range: str | None = None,
    strike_price_near: float | None = None,
    option_type: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream live option chain updates for an underlying symbol.

    Maps to: B16 GET /marketdata/stream/options/chains/{underlying}

    Args:
        underlying: The underlying ticker symbol.
        expiration: Expiration date filter in MM/DD/YYYY format.
        strike_price_range: Strike price range filter.
        strike_price_near: Strike price center for range filter.
        option_type: "All", "Call", or "Put".

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {}
    if expiration is not None:
        query["expiration"] = expiration
    if strike_price_range is not None:
        query["strikePriceRange"] = strike_price_range
    if strike_price_near is not None:
        query["strikePriceNear"] = strike_price_near
    if option_type is not None:
        query["optionType"] = option_type
    return await transport.stream(
        f"/marketdata/stream/options/chains/{underlying}",
        params=query or None,
    )


async def stream_option_quotes(
    transport: Transport,
    *,
    legs: str,
    underlying: str | None = None,
    expiration: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream live option quote updates for specific legs.

    Maps to: B17 GET /marketdata/stream/options/quotes

    Args:
        legs: Comma-separated option symbols / legs.
        underlying: Optional underlying symbol filter.
        expiration: Optional expiration date filter.

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {"legs": legs}
    if underlying is not None:
        query["underlying"] = underlying
    if expiration is not None:
        query["expiration"] = expiration
    return await transport.stream("/marketdata/stream/options/quotes", params=query)


# ---------------------------------------------------------------------------
# Swagger v2 operationIds — direct wrappers (kept for coverage completeness)
# The v3 equivalents above are the canonical forms.
# ---------------------------------------------------------------------------


async def get_symbol(
    transport: Transport,
    *,
    symbol: str,
) -> dict[str, Any]:
    """Fetch symbol details by symbol name.

    Maps to: B3 GET /marketdata/symbols/{symbol}

    Swagger operationId: getSymbol (v2: GET /v2/data/symbol/{symbol})
    """
    return await transport.request("GET", f"/marketdata/symbols/{symbol}")


async def suggest_symbols(
    transport: Transport,
    *,
    text: str,
    top: int | None = None,
    filter_: str | None = None,
) -> dict[str, Any]:
    """Suggest symbols matching a text prefix.

    Maps to: B3 GET /marketdata/symbols/suggest/{text}

    Swagger operationId: suggestsymbols (v2: GET /v2/data/symbols/suggest/{text})
    """
    query: dict[str, Any] = {}
    if top is not None:
        query["$top"] = top
    if filter_ is not None:
        query["$filter"] = filter_
    return await transport.request(
        "GET",
        f"/marketdata/symbols/suggest/{text}",
        params=query or None,
    )


async def search_symbols(
    transport: Transport,
    *,
    criteria: str,
) -> dict[str, Any]:
    """Search symbols by name/criteria.

    Maps to: B3 GET /marketdata/symbols/search/{criteria}

    Swagger operationId: searchSymbols (v2: GET /v2/data/symbols/search/{criteria})
    """
    return await transport.request("GET", f"/marketdata/symbols/search/{criteria}")


async def stream_tick_bars(
    transport: Transport,
    *,
    symbol: str,
    interval: int,
    bars_back: int,
) -> AsyncIterator[bytes]:
    """Stream live tick bars for a symbol.

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol} (tick variant)

    Swagger operationId: streamTickBars (v2: GET /v2/stream/tickbars/{symbol}/{interval}/{barsBack})

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(
        f"/marketdata/stream/barcharts/{symbol}",
        params={"interval": interval, "unit": "Tick", "barsback": bars_back},
    )


async def stream_barcharts_from_start_date(
    transport: Transport,
    *,
    symbol: str,
    interval: int,
    unit: str,
    start_date: str,
    session_template: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream bar chart data from a start date.

    Swagger operationId: streamBarchartsFromStartDate
    (v2: GET /v2/stream/barchart/{symbol}/{interval}/{unit}/{startDate})

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {"interval": interval, "unit": unit, "firstdate": start_date}
    if session_template is not None:
        query["sessiontemplate"] = session_template
    return await transport.stream(f"/marketdata/stream/barcharts/{symbol}", params=query)


async def stream_barcharts_from_start_date_to_end_date(
    transport: Transport,
    *,
    symbol: str,
    interval: int,
    unit: str,
    start_date: str,
    end_date: str,
    session_template: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream bar chart data between a start date and end date.

    Swagger operationId: streamBarchartsFromStartDateToEndDate
    (v2: GET /v2/stream/barchart/{symbol}/{interval}/{unit}/{startDate}/{endDate})

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {
        "interval": interval,
        "unit": unit,
        "firstdate": start_date,
        "lastdate": end_date,
    }
    if session_template is not None:
        query["sessiontemplate"] = session_template
    return await transport.stream(f"/marketdata/stream/barcharts/{symbol}", params=query)


async def stream_barcharts_bars_back(
    transport: Transport,
    *,
    symbol: str,
    interval: int,
    unit: str,
    bars_back: int,
    last_date: str,
    session_template: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream bar chart data going back a number of bars from a date.

    Swagger operationId: streamBarchartsBarsBack
    (v2: GET /v2/stream/barchart/{symbol}/{interval}/{unit}/{barsBack}/{lastDate}/...)

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {
        "interval": interval,
        "unit": unit,
        "barsback": bars_back,
        "lastdate": last_date,
    }
    if session_template is not None:
        query["sessiontemplate"] = session_template
    return await transport.stream(f"/marketdata/stream/barcharts/{symbol}", params=query)


async def stream_barcharts_days_back(
    transport: Transport,
    *,
    symbol: str,
    interval: int,
    unit: str,
    days_back: int,
    last_date: str | None = None,
    session_template: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream bar chart data going back a number of days.

    Swagger operationId: streamBarchartsDaysBack
    (v2: GET /v2/stream/barchart/{symbol}/{interval}/{unit})

    Maps to: B12 GET /marketdata/stream/barcharts/{symbol}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    query: dict[str, Any] = {"interval": interval, "unit": unit, "daysBack": days_back}
    if last_date is not None:
        query["lastdate"] = last_date
    if session_template is not None:
        query["sessiontemplate"] = session_template
    return await transport.stream(f"/marketdata/stream/barcharts/{symbol}", params=query)


async def stream_quotes_changes(
    transport: Transport,
    *,
    symbols: str,
) -> AsyncIterator[bytes]:
    """Stream live quote change updates.

    Swagger operationId: streamQuotesChanges
    (v2: GET /v2/stream/quote/changes/{symbols})

    Maps to: B13 GET /marketdata/stream/quotes/{symbols}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/marketdata/stream/quotes/{symbols}")


async def stream_quotes_snapshots(
    transport: Transport,
    *,
    symbols: str,
) -> AsyncIterator[bytes]:
    """Stream live quote snapshot updates.

    Swagger operationId: streamQuotesSnapshots
    (v2: GET /v2/stream/quote/snapshots/{symbols})

    Maps to: B13 GET /marketdata/stream/quotes/{symbols}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/marketdata/stream/quotes/{symbols}")


# ---------------------------------------------------------------------------
# C. Brokerage  (/v3/brokerage)
# ---------------------------------------------------------------------------


async def get_accounts_by_user_id(
    transport: Transport,
    *,
    user_id: str,
) -> dict[str, Any]:
    """Fetch accounts for a specific user.

    Maps to: C1 GET /brokerage/accounts

    Swagger operationId: getAccountsByUserID (v2: GET /v2/users/{user_id}/accounts)

    Args:
        user_id: The TradeStation user ID.
    """
    return await transport.request("GET", f"/brokerage/accounts/{user_id}")


async def get_accounts(transport: Transport) -> dict[str, Any]:
    """Fetch all accounts for the authenticated user.

    Maps to: C1 GET /brokerage/accounts
    """
    return await transport.request("GET", "/brokerage/accounts")


async def get_balances(
    transport: Transport,
    *,
    account_ids: str,
) -> dict[str, Any]:
    """Fetch real-time balances for one or more accounts.

    Maps to: C2 GET /brokerage/accounts/{accountIDs}/balances

    Swagger operationId: getBalancesByAccounts
    (v2: GET /v2/accounts/{account_keys}/balances)

    Args:
        account_ids: Comma-separated account IDs.
    """
    return await transport.request("GET", f"/brokerage/accounts/{account_ids}/balances")


async def get_bod_balances(
    transport: Transport,
    *,
    account_ids: str,
) -> dict[str, Any]:
    """Fetch beginning-of-day balances for one or more accounts.

    Maps to: C3 GET /brokerage/accounts/{accountIDs}/balances/bod

    Args:
        account_ids: Comma-separated account IDs.
    """
    return await transport.request("GET", f"/brokerage/accounts/{account_ids}/balances/bod")


async def get_positions(
    transport: Transport,
    *,
    account_ids: str,
    filter_: str | None = None,
) -> dict[str, Any]:
    """Fetch open positions for one or more accounts.

    Maps to: C4 GET /brokerage/accounts/{accountIDs}/positions

    Swagger operationId: getPositionsByAccounts
    (v2: GET /v2/accounts/{account_keys}/positions)

    Args:
        account_ids: Comma-separated account IDs.
        filter_: OData filter expression (e.g. "Symbol eq 'AAPL'").
    """
    query: dict[str, Any] = {}
    if filter_ is not None:
        query["$filter"] = filter_
    return await transport.request(
        "GET",
        f"/brokerage/accounts/{account_ids}/positions",
        params=query or None,
    )


async def get_orders(
    transport: Transport,
    *,
    account_ids: str,
    since: str | None = None,
    page_size: int | None = None,
    page_num: int | None = None,
) -> dict[str, Any]:
    """Fetch today's orders for one or more accounts.

    Maps to: C5 GET /brokerage/accounts/{accountIDs}/orders

    Swagger operationId: getOrdersByAccounts
    (v2: GET /v2/accounts/{account_keys}/orders)

    Args:
        account_ids: Comma-separated account IDs.
        since: Return orders since this date (ISO 8601 or MM/DD/YYYY).
        page_size: Number of results per page.
        page_num: Page number (1-based).
    """
    query: dict[str, Any] = {}
    if since is not None:
        query["since"] = since
    if page_size is not None:
        query["pageSize"] = page_size
    if page_num is not None:
        query["pageNum"] = page_num
    return await transport.request(
        "GET",
        f"/brokerage/accounts/{account_ids}/orders",
        params=query or None,
    )


async def get_orders_by_id(
    transport: Transport,
    *,
    account_ids: str,
    order_ids: str,
) -> dict[str, Any]:
    """Fetch specific orders by order ID for one or more accounts.

    Maps to: C6 GET /brokerage/accounts/{accountIDs}/orders/{orderIDs}

    Args:
        account_ids: Comma-separated account IDs.
        order_ids: Comma-separated order IDs.
    """
    return await transport.request(
        "GET",
        f"/brokerage/accounts/{account_ids}/orders/{order_ids}",
    )


async def get_historical_orders(
    transport: Transport,
    *,
    account_ids: str,
    since: str,
    page_size: int | None = None,
    page_num: int | None = None,
) -> dict[str, Any]:
    """Fetch historical orders for one or more accounts since a date.

    Maps to: C7 GET /brokerage/accounts/{accountIDs}/historicalorders

    Args:
        account_ids: Comma-separated account IDs.
        since: Start date in ISO 8601 or MM/DD/YYYY format (required).
        page_size: Number of results per page.
        page_num: Page number (1-based).
    """
    query: dict[str, Any] = {"since": since}
    if page_size is not None:
        query["pageSize"] = page_size
    if page_num is not None:
        query["pageNum"] = page_num
    return await transport.request(
        "GET",
        f"/brokerage/accounts/{account_ids}/historicalorders",
        params=query,
    )


async def get_historical_orders_by_id(
    transport: Transport,
    *,
    account_ids: str,
    order_ids: str,
) -> dict[str, Any]:
    """Fetch specific historical orders by ID.

    Maps to: C8 GET /brokerage/accounts/{accountIDs}/historicalorders/{orderIDs}

    Args:
        account_ids: Comma-separated account IDs.
        order_ids: Comma-separated order IDs.
    """
    return await transport.request(
        "GET",
        f"/brokerage/accounts/{account_ids}/historicalorders/{order_ids}",
    )


async def get_wallets(
    transport: Transport,
    *,
    account_ids: str,
) -> dict[str, Any]:
    """Fetch crypto wallets for one or more accounts.

    Maps to: C9 GET /brokerage/accounts/{accountIDs}/wallets

    Args:
        account_ids: Comma-separated account IDs.
    """
    return await transport.request("GET", f"/brokerage/accounts/{account_ids}/wallets")


# C.2 Brokerage Streaming endpoints


async def stream_orders(
    transport: Transport,
    *,
    account_ids: str,
) -> AsyncIterator[bytes]:
    """Stream live order events for one or more accounts.

    Maps to: C10 GET /brokerage/stream/accounts/{accountIDs}/orders

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/brokerage/stream/accounts/{account_ids}/orders")


async def stream_orders_by_id(
    transport: Transport,
    *,
    account_ids: str,
    order_ids: str,
) -> AsyncIterator[bytes]:
    """Stream live order events for specific orders.

    Maps to: C11 GET /brokerage/stream/accounts/{accountIDs}/orders/{orderIDs}

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(
        f"/brokerage/stream/accounts/{account_ids}/orders/{order_ids}"
    )


async def stream_positions(
    transport: Transport,
    *,
    account_ids: str,
) -> AsyncIterator[bytes]:
    """Stream live position updates for one or more accounts.

    Maps to: C12 GET /brokerage/stream/accounts/{accountIDs}/positions

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/brokerage/stream/accounts/{account_ids}/positions")


async def stream_wallets(
    transport: Transport,
    *,
    account_ids: str,
) -> AsyncIterator[bytes]:
    """Stream live wallet updates for one or more accounts.

    Maps to: C13 GET /brokerage/stream/accounts/{accountIDs}/wallets

    Yields:
        Raw UTF-8 bytes for each newline-delimited JSON frame.
    """
    return await transport.stream(f"/brokerage/stream/accounts/{account_ids}/wallets")


# ---------------------------------------------------------------------------
# D. OrderExecution  (/v3/orderexecution)
# ---------------------------------------------------------------------------


async def post_order_confirm(
    transport: Transport,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Preview an order without submitting; returns fees and buying-power impact.

    Maps to: D1 POST /orderexecution/orderconfirm

    Swagger operationId: postOrderConfirm (v2: POST /v2/orders/confirm)

    Args:
        body: Order request body (same shape as postOrder).
    """
    return await transport.request("POST", "/orderexecution/orderconfirm", json=body)


async def post_order(
    transport: Transport,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Submit a single order.

    Maps to: D2 POST /orderexecution/orders

    Swagger operationId: postOrder (v2: POST /v2/orders)

    WARNING: This endpoint is NEVER auto-retried — POST to order execution
    is a destructive, non-idempotent operation.

    Args:
        body: Order request body (AccountID, Symbol, Quantity, OrderType, etc.).
    """
    return await transport.request("POST", "/orderexecution/orders", json=body)


async def cancel_replace_order(
    transport: Transport,
    *,
    order_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Replace / modify an existing order.

    Maps to: D3 PUT /orderexecution/orders/{orderID}

    Swagger operationId: cancelReplaceOrder (v2: PUT /v2/orders/{order_id})

    Args:
        order_id: The order ID to replace.
        body: Replacement order details.
    """
    return await transport.request(
        "PUT",
        f"/orderexecution/orders/{order_id}",
        json=body,
    )


async def cancel_order(
    transport: Transport,
    *,
    order_id: str,
) -> dict[str, Any]:
    """Cancel an existing order.

    Maps to: D4 DELETE /orderexecution/orders/{orderID}

    Swagger operationId: cancelOrder (v2: DELETE /v2/orders/{order_id})

    Args:
        order_id: The order ID to cancel.
    """
    return await transport.request("DELETE", f"/orderexecution/orders/{order_id}")


async def post_order_groups_confirm(
    transport: Transport,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Preview a grouped order (OCO / OSO / bracket) without submitting.

    Maps to: D5 POST /orderexecution/ordergroupconfirm

    Swagger operationId: postOrderGroupsConfirm (v2: POST /v2/orders/groups/confirm)

    Args:
        body: Group order request body.
    """
    return await transport.request(
        "POST",
        "/orderexecution/ordergroupconfirm",
        json=body,
    )


async def post_order_group(
    transport: Transport,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Submit a grouped order (OCO / OSO / bracket).

    Maps to: D6 POST /orderexecution/ordergroups

    Swagger operationId: postOrderGroup (v2: POST /v2/orders/groups)

    WARNING: This endpoint is NEVER auto-retried — POST to order execution
    is a destructive, non-idempotent operation.

    Args:
        body: Group order request body (Type, Orders list, etc.).
    """
    return await transport.request("POST", "/orderexecution/ordergroups", json=body)


async def get_activation_triggers(transport: Transport) -> dict[str, Any]:
    """Fetch available conditional activation triggers.

    Maps to: D7 GET /orderexecution/activationtriggers

    Swagger operationId: getActivationTriggers
    (v2: GET /v2/orderexecution/activationtriggers)

    Returns a list of supported triggers (e.g. STT — Stop on Trade,
    STST — Stop on Specific Trade, etc.).
    """
    return await transport.request("GET", "/orderexecution/activationtriggers")


async def get_routes(transport: Transport) -> dict[str, Any]:
    """Fetch available execution routes.

    Maps to: D8 GET /orderexecution/routes

    Returns a list of available routes (e.g. "Intelligent", "NYSE", "NASDAQ").
    """
    return await transport.request("GET", "/orderexecution/routes")


async def get_exchanges(transport: Transport) -> dict[str, Any]:
    """Fetch available exchanges.

    Maps to: D8 GET /orderexecution/routes (exchanges variant)

    Swagger operationId: getExchanges (v2: GET /v2/orderexecution/exchanges)
    """
    return await transport.request("GET", "/orderexecution/routes")
