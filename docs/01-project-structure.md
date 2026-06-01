# 01 — Project Structure

## Repository layout

```
tradestationcli/
├── README.md
├── LICENSE                            # MIT
├── pyproject.toml                     # workspace root (uv/hatch workspace)
├── uv.lock                            # one lockfile for the workspace
├── .python-version                    # >= 3.10
├── .github/workflows/
│   ├── ci.yml                         # lint + type + unit tests
│   └── release.yml                    # per-package PyPI publish on tag
│
├── packages/
│   ├── tradestation/                  # ─── pip install tradestation
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── src/tradestation/
│   │   │   ├── __init__.py            # re-exports TradeStationClient, models, errors
│   │   │   ├── client.py              # TradeStationClient (sync facade)
│   │   │   ├── async_client.py        # AsyncTradeStationClient
│   │   │   ├── credentials.py         # load/save/encrypt ~/.tscli/credentials
│   │   │   ├── auth.py                # refresh-token exchange, token cache
│   │   │   ├── transport.py           # httpx wrapper, retries, rate limit, logging
│   │   │   ├── streaming.py           # async iterator for HTTP chunked transfer
│   │   │   ├── errors.py              # AuthError, RateLimitError, OrderRejectedError…
│   │   │   ├── enums.py               # Side, OrderType, TimeInForce, BarUnit…
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # BaseService (shared transport handle)
│   │   │   │   ├── market_data.py     # quotes, bars, options, crypto, lists, streams
│   │   │   │   ├── brokerage.py       # accounts, balances, positions, orders, wallets, streams
│   │   │   │   └── order_execution.py # place/replace/cancel/group/routes/triggers
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── common.py
│   │   │   │   ├── market_data.py
│   │   │   │   ├── brokerage.py
│   │   │   │   └── orders.py
│   │   │   └── _version.py
│   │   └── tests/                     # unit + recorded HTTP fixtures (vcr.py)
│   │
│   ├── tscli/                         # ─── pip install tscli
│   │   ├── pyproject.toml             # depends on tradestation>=X.Y
│   │   ├── README.md
│   │   ├── src/tscli/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py            # python -m tscli
│   │   │   ├── app.py                 # root Typer app
│   │   │   ├── theme.py               # Rich theme (colors, styles)
│   │   │   ├── render.py              # table/quote/order renderers
│   │   │   ├── prompts.py             # confirmation prompts for destructive actions
│   │   │   ├── ctx.py                 # shared CLI context (client, theme)
│   │   │   └── commands/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py            # ts auth set | status | refresh | login | clear
│   │   │       ├── market_data.py     # ts md …
│   │   │       ├── brokerage.py       # ts brokerage …
│   │   │       ├── order.py           # ts order …
│   │   │       └── completions.py     # shell completion install
│   │   └── tests/
│   │
│   └── tradestation-mcp/              # ─── pip install tradestation-mcp
│       ├── pyproject.toml             # depends on tradestation>=X.Y, fastmcp
│       ├── README.md
│       ├── src/tradestation_mcp/
│       │   ├── __init__.py
│       │   ├── __main__.py            # python -m tradestation_mcp
│       │   ├── server.py              # FastMCP server, transport selection
│       │   ├── toolsets.py            # allowlist groups: market, brokerage, trading
│       │   ├── safety.py              # confirm flags for destructive tools
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   ├── market_data.py
│       │   │   ├── brokerage.py
│       │   │   └── order_execution.py
│       │   └── schemas/               # JSON Schemas (generated from Pydantic)
│       └── tests/
│
└── docs/                              # this design doc tree
```

## Workspace tooling

- **Build / lockfile:** [`uv`](https://docs.astral.sh/uv/) workspace at the repo root. One lockfile, three editable installs.
- **Package backend:** `hatchling` for each package's `pyproject.toml`.
- **Lint / format:** `ruff` (lint + format) + `mypy --strict` for the library, `mypy` (regular) for CLI/MCP.
- **Tests:** `pytest` + `pytest-asyncio` + `vcrpy` for recorded HTTP fixtures (no live calls in CI).
- **Coverage gate:** 80 % on the library; CLI/MCP exercised via integration tests against a fake `TradeStationClient`.

## `pyproject.toml` strategy (per package)

Each package is independently versioned and independently releasable. The library's version is the source of truth; CLI and MCP pin a compatible range.

### `packages/tradestation/pyproject.toml` (sketch)

```toml
[project]
name = "tradestation"
version = "0.1.0"
description = "Typed Python client for the TradeStation v3 API."
requires-python = ">=3.10"
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.7",
  "cryptography>=42",      # Fernet for credentials at rest
  "keyring>=24",           # optional, OS-keychain backend
  "anyio>=4",
]
classifiers = ["License :: OSI Approved :: MIT License", "Programming Language :: Python :: 3"]

[project.optional-dependencies]
pandas = ["pandas>=2.2"]   # to_frame() helpers on bar/quote responses
```

### `packages/tscli/pyproject.toml` (sketch)

```toml
[project]
name = "tscli"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "tradestation>=0.1.0,<0.2",
  "typer>=0.12",
  "rich>=13.7",
  "click>=8.1",
]

[project.scripts]
ts = "tscli.app:main"
```

### `packages/tradestation-mcp/pyproject.toml` (sketch)

```toml
[project]
name = "tradestation-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "tradestation>=0.1.0,<0.2",
  "fastmcp>=2.0",
]

[project.scripts]
ts-mcp = "tradestation_mcp.server:main"
```

## Versioning

- Semver per package.
- Library breaking change → major bump on `tradestation`, simultaneous compatibility-pin update on `tscli` and `tradestation-mcp`.
- CI's `release.yml` reads a tag like `tradestation-v0.2.0` / `tscli-v0.2.0` / `tradestation-mcp-v0.2.0` and publishes only the matching package.

## Release flow

```
git tag tradestation-v0.2.0 && git push --tags
   └─→ GH Actions: build sdist+wheel, run tests, twine upload to PyPI
   └─→ GH Release with changelog auto-generated from conventional commits
```

## Why three packages, not one with extras?

- LLM hosts installing only the MCP server should not download Typer + Rich.
- Library consumers (algorithmic traders) should not download FastMCP.
- Independent release cadence: CLI cosmetic tweaks shouldn't force a library version bump.

## Why a monorepo (workspace), not three repos?

- Single source of truth for the endpoint inventory + shared test fixtures.
- One PR can ship a library change + CLI surface + MCP tool together.
- Cross-package refactors are atomic.
