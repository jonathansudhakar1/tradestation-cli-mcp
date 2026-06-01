"""Code generation entry point.

Regenerates ``src/tradestation/_generated/`` from ``vendor/swagger.yaml``
(and ``vendor/swagger.v3.json`` when present) using datamodel-code-generator.

See docs/09-codegen-strategy.md for the full codegen strategy.

Usage::

    python scripts/codegen.py
    # or via Makefile:
    make codegen

Phase 0 stub — prints a message and exits 0.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Entry point — stub for Phase 0."""
    print("codegen: not implemented yet (Phase 1 task)")
    sys.exit(0)


if __name__ == "__main__":
    main()
