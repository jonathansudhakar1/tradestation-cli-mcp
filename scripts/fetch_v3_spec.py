"""Fetch the TradeStation v3 OpenAPI spec and save to vendor/swagger.v3.json.

Requires a working refresh token in ~/.tscli/credentials (or env vars).
The v3 spec endpoint is auth-gated (401 without Bearer token).

See docs/09-codegen-strategy.md §"The spec situation" for background.

Usage::

    python scripts/fetch_v3_spec.py
    # or via Makefile:
    make vendor

Phase 0 stub — not yet implemented.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Entry point — stub for Phase 0."""
    print("fetch_v3_spec: not implemented yet (Phase 1 task)")
    sys.exit(0)


if __name__ == "__main__":
    main()
