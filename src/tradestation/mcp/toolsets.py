"""Toolset allowlist groups for the MCP server.

See docs/06-mcp-server.md §"Toolset groups (allowlist)".
Phase 0 placeholder — implementation in Phase 2.

Toolsets:
    market    — all B-series tools (B1-B17)
    brokerage — all C-series tools (C1-C13)
    trading   — all D-series tools + auth_status
    auth      — auth_status only
    all       — all of the above (default)
"""

from __future__ import annotations

#: Canonical toolset names accepted by --toolsets.
VALID_TOOLSETS: frozenset[str] = frozenset({"market", "brokerage", "trading", "auth", "all"})
