# 01 — Project Structure

**One** PyPI distribution: `tradestation-cli-mcp`. **One** import root: `tradestation`. Two console scripts: `ts` (CLI) and `ts-mcp` (MCP server). The library is usable on its own via `import tradestation`.

## Repository layout

```
tradestation-cli-mcp/
├── README.md
├── LICENSE                            # MIT
├── pyproject.toml                     # the only one — single distribution
├── uv.lock
├── .python-version                    # >= 3.10
├── .github/workflows/
│   ├── ci.yml                         # lint + type + unit tests
│   └── release.yml                    # PyPI publish on tag
│
├── src/tradestation/                  # the importable Python package
│   │
│   ├── __init__.py                    # re-exports TradeStationClient, models, errors
│   ├── _version.py                    # __version__ = "0.1.0"
│   │
│   ├── client.py                      # TradeStationClient (sync facade)
│   ├── async_client.py                # AsyncTradeStationClient
│   ├── credentials.py                 # load/save/encrypt ~/.tscli/credentials
│   ├── auth.py                        # refresh-token exchange, token cache
│   ├── transport.py                   # httpx wrapper, retries, rate limit, logging
│   ├── streaming.py                   # async iterator for HTTP chunked transfer
│   ├── errors.py                      # AuthError, RateLimitError, OrderRejectedError…
│   ├── enums.py                       # Side, OrderType, TimeInForce, BarUnit…
│   │
│   ├── services/                      # one module per API category
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseService (shared transport handle)
│   │   ├── market_data.py             # quotes, bars, options, crypto, lists, streams
│   │   ├── brokerage.py               # accounts, balances, positions, orders, wallets, streams
│   │   └── order_execution.py         # place/replace/cancel/group/routes/triggers
│   │
│   ├── models/                        # Pydantic v2 request + response models
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── market_data.py
│   │   ├── brokerage.py
│   │   └── orders.py
│   │
│   ├── cli/                           # Typer + Rich CLI; entry point: ts
│   │   ├── __init__.py
│   │   ├── __main__.py                # python -m tradestation.cli
│   │   ├── app.py                     # root Typer app; `def main()`
│   │   ├── theme.py                   # Rich theme (colors, styles)
│   │   ├── render.py                  # table/quote/order renderers
│   │   ├── prompts.py                 # confirmation prompts for destructive actions
│   │   ├── ctx.py                     # shared CLI context (client, theme)
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── auth.py                # ts auth set | status | refresh | login | clear
│   │       ├── market_data.py         # ts md …
│   │       ├── brokerage.py           # ts brokerage …
│   │       ├── order.py               # ts order …
│   │       └── completions.py         # shell completion install
│   │
│   └── mcp/                           # FastMCP server; entry point: ts-mcp
│       ├── __init__.py
│       ├── __main__.py                # python -m tradestation.mcp
│       ├── server.py                  # FastMCP server, transport selection; `def main()`
│       ├── toolsets.py                # allowlist groups: market, brokerage, trading
│       ├── safety.py                  # confirm flags for destructive tools
│       ├── overrides.py               # hand-crafted tool ergonomics for trading
│       └── tools/
│           ├── __init__.py
│           ├── market_data.py
│           ├── brokerage.py
│           └── order_execution.py
│
├── docs/                              # this design doc tree
└── tests/
    ├── unit/                          # library unit tests (models, auth, transport)
    ├── cli/                           # CLI tests vs. fake TradeStationClient
    ├── mcp/                           # MCP tests via in-process mcp client
    ├── integration/                   # vcrpy cassettes against TS SIM
    └── conftest.py
```

## Import rules (enforced by lint)

```
tradestation.cli  → may import from tradestation.*          (library)  ✓
tradestation.mcp  → may import from tradestation.*          (library)  ✓
tradestation.*    → may NOT import from tradestation.cli              ✗
tradestation.*    → may NOT import from tradestation.mcp              ✗
tradestation.cli  → may NOT import from tradestation.mcp              ✗
tradestation.mcp  → may NOT import from tradestation.cli              ✗
```

This keeps the library distributable concept alive even though we ship a single package. Enforced via `ruff`'s `flake8-tidy-imports` rules. CI fails on violations.

## `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tradestation-cli-mcp"
version = "0.1.0"
description = "TradeStation v3 Python library + CLI (`ts`) + MCP server (`ts-mcp`)."
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [{ name = "Jonathan", email = "jonathan@getangler.ai" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Financial and Insurance Industry",
  "Intended Audience :: Developers",
  "Programming Language :: Python :: 3 :: Only",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Office/Business :: Financial :: Investment",
  "License :: OSI Approved :: MIT License",
]
dependencies = [
  # --- library core ---
  "httpx>=0.27",
  "pydantic>=2.7",
  "cryptography>=42",         # Fernet for credentials at rest
  "keyring>=24",              # OS-keychain backend (optional at runtime)
  "anyio>=4",
  "filelock>=3.13",           # cross-process refresh lock

  # --- CLI ---
  "typer>=0.12",
  "rich>=13.7",
  "click>=8.1",

  # --- MCP server ---
  "fastmcp>=2.0",
]

[project.optional-dependencies]
pandas = ["pandas>=2.2"]      # to_frame() helpers on bar/quote responses
dev    = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5",
  "vcrpy>=6",
  "hypothesis>=6.100",
  "ruff>=0.5",
  "mypy>=1.11",
  "types-cryptography",
]

[project.scripts]
ts     = "tradestation.cli.app:main"
ts-mcp = "tradestation.mcp.server:main"

[project.urls]
Homepage = "https://github.com/jonathansudhakar1/tradestation-cli-mcp"
Issues   = "https://github.com/jonathansudhakar1/tradestation-cli-mcp/issues"

[tool.hatch.version]
path = "src/tradestation/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/tradestation"]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E","F","W","I","UP","B","TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"tradestation.cli".msg  = "Library code must not depend on the CLI layer."
"tradestation.mcp".msg  = "Library code must not depend on the MCP layer."
# The blanket bans above are scoped to library files via per-file ignores below.

[tool.ruff.lint.per-file-ignores]
"src/tradestation/cli/**" = []
"src/tradestation/mcp/**" = []

[tool.mypy]
strict = true
files = ["src/tradestation"]
```

> Why bundle Typer / Rich / FastMCP into the core dependencies instead of `[cli]` / `[mcp]` extras?
> The distribution name **promises** all three faces (`tradestation-cli-mcp`). A user typing `pip install tradestation-cli-mcp` should not have to remember a follow-up `[cli]` modifier just to make the `ts` binary work. We accept the small dep-size cost in exchange for a single, predictable install command. If a future library-only user wants a slim install, they can pin a different package name we publish later (e.g. a hypothetical `tradestation-lite`).

## Entry points

`pip install tradestation-cli-mcp` registers:

| Console script | Resolves to | Purpose |
|---|---|---|
| `ts` | `tradestation.cli.app:main` | The CLI. |
| `ts-mcp` | `tradestation.mcp.server:main` | The MCP server. |

Both are also runnable as modules:

```bash
python -m tradestation.cli  …   # equivalent to `ts …`
python -m tradestation.mcp  …   # equivalent to `ts-mcp …`
```

The library is importable independently:

```python
import tradestation
from tradestation import TradeStationClient
from tradestation.models import MarketOrderRequest
```

## Workspace tooling

- **Build / lockfile:** [`uv`](https://docs.astral.sh/uv/) — single package, single lockfile.
- **Package backend:** `hatchling`.
- **Lint / format:** `ruff` (lint + format). Import-direction rules above enforce the internal layering.
- **Types:** `mypy --strict` on the entire `src/tradestation` tree.
- **Tests:** `pytest` + `pytest-asyncio` + `vcrpy` for recorded HTTP fixtures (no live calls in CI).
- **Coverage gate:** 80 % overall.

## Versioning

- Semver, one number per release.
- `0.x.y` until the API surface stabilizes.
- Breaking changes to **any** of {library, CLI, MCP} bump the same version. There is no scenario where the three drift.

## Release flow

```
git tag v0.2.0 && git push --tags
   └─→ GH Actions: build sdist+wheel, run tests, twine upload to PyPI as tradestation-cli-mcp
   └─→ GH Release with changelog auto-generated from conventional commits
```

## Why a monorepo-style single package?

- **Single source of truth** for the endpoint inventory, shared test fixtures, and the shared credential format.
- **One PR** can ship a library change + CLI surface + MCP tool together with no inter-package version dance.
- **Atomic cross-layer refactors.**
- **No publishing dance** at release time — one `twine upload` and you're done.
