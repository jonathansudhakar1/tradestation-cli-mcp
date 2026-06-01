"""Hand-crafted MCP tool ergonomic overrides.

See docs/06-mcp-server.md §"Hand-crafted overrides" and
docs/09-codegen-strategy.md §"MCP tool overrides".
Phase 0 placeholder — implementation in Phase 2.

Overrides are needed for tools where auto-generated schemas are poor for LLMs:
    order_place          — flatten common shortcuts (--limit-price, etc.)
    option_risk_reward   — friendlier legs shape
"""

from __future__ import annotations
