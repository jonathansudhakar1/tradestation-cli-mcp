"""Shared CLI context object.

Holds the Rich Console and (eventually) the TradeStationClient so every
command has a single place to get them.  Phase 0 placeholder.

Phase 2+: implement CliContext dataclass with client, console, and env-override.
"""

from __future__ import annotations
