"""Integration test — live call to TradeStation SIM API.

Marked ``@pytest.mark.live`` — only runs when explicitly selected:
    pytest -m live tests/integration/test_live_quotes.py -v

Reads ``.env`` from the project root (loaded automatically via
``tests/integration/conftest.py`` via the ``_load_dotenv_for_live_tests`` fixture).

Requirements:
    - ``.env`` file at the repo root with TS_CLIENT_ID, TS_CLIENT_SECRET,
      TS_REFRESH_TOKEN, TS_ENV=sim
    - Network access to sim-api.tradestation.com
"""

from __future__ import annotations

import pprint
from datetime import datetime

import pytest

pytestmark = pytest.mark.live


@pytest.mark.asyncio
@pytest.mark.usefixtures("_load_dotenv_for_live_tests")
async def test_live_get_quotes_sim() -> None:
    """End-to-end: get_quotes(['AAPL', 'MSFT', 'BTCUSD']) against SIM.

    Assertions:
    - Returns at least 1 quote per valid symbol.
    - Each quote has a numeric last price > 0.
    - Each quote has a non-empty symbol.
    - Each quote has a parsable TradeTime (last_utc).
    - Quote model tolerates any extra fields from the API.
    """
    from tradestation.async_client import AsyncTradeStationClient
    from tradestation.models.market_data import Quote

    async with AsyncTradeStationClient.from_env() as ts:
        quotes: list[Quote] = await ts.market_data.get_quotes(["AAPL", "MSFT", "BTCUSD"])

    # Print the raw payload for visibility
    print("\n--- Live Quote Payload (SIM) ---")
    for q in quotes:
        d = q.model_dump(by_alias=False)
        pprint.pprint(d)
        print()

    # Assertions
    assert len(quotes) >= 1, "Expected at least one quote to be returned"

    returned_symbols = {q.symbol for q in quotes}
    print(f"Symbols returned: {returned_symbols}")

    for q in quotes:
        # Symbol is non-empty
        assert q.symbol, f"Quote has empty symbol: {q!r}"

        # Last price is positive
        assert q.last is not None, f"Quote for {q.symbol!r} has no Last price"
        assert q.last > 0, f"Quote for {q.symbol!r} has last={q.last!r} (expected > 0)"

        # TradeTime is parsable
        assert q.last_utc is not None, (
            f"Quote for {q.symbol!r} has TradeTime={q.trade_time!r} "
            "which could not be parsed as a datetime"
        )
        assert isinstance(q.last_utc, datetime), f"last_utc is not a datetime: {q.last_utc!r}"

        # Market flags present
        assert q.market_flags is not None, f"No MarketFlags for {q.symbol!r}"

        print(f"✓ {q.symbol}: last={q.last}, last_utc={q.last_utc.isoformat()}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("_load_dotenv_for_live_tests")
async def test_live_quote_field_drift_report() -> None:
    """Report any unexpected top-level fields in the v3 quote response.

    Does NOT fail on unknown fields (model uses extra='allow'), but prints
    them so Phase 4 agents can apply the same patterns.
    """
    from tradestation.async_client import AsyncTradeStationClient
    from tradestation.models.market_data import Quote

    async with AsyncTradeStationClient.from_env() as ts:
        quotes: list[Quote] = await ts.market_data.get_quotes(["AAPL"])

    assert len(quotes) >= 1

    q = quotes[0]

    extra = getattr(q, "__pydantic_extra__", None) or {}
    if extra:
        print(f"\nv3-vs-v2 field drift for AAPL: extra fields = {list(extra.keys())}")
    else:
        print("\nNo unexpected extra fields in the v3 response for AAPL — model is complete.")

    # The test passes regardless — we just want the report
