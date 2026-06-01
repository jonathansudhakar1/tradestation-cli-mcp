"""Safety guards for destructive MCP tools.

See docs/06-mcp-server.md §"Safety model for destructive tools".
Phase 0 placeholder — implementation in Phase 2.

Modes (--confirm-trades):
    off     — execute immediately (not recommended)
    require — require a confirmation token (default)
    review  — preview only; placement requires out-of-band CLI step
"""

from __future__ import annotations
