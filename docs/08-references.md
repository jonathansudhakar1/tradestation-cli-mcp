# 08 — References

Everything we read while designing this. Grouped, annotated.

## TradeStation — official

- [Developer Portal](https://developer.tradestation.com/) — landing page; account setup, plan tiers.
- [API Docs root](https://api.tradestation.com/docs/) — current v3 documentation site (SPA, requires JS).
- [Specification page](https://api.tradestation.com/docs/specification/) — link to the OpenAPI spec download.
- [tradestation.github.io/api-docs/](https://tradestation.github.io/api-docs/) — Swagger UI mirror. Hosts both v2 and v3.
- [HTTP Requests](https://api.tradestation.com/docs/fundamentals/http-requests/) — base URLs, headers, conventions.
- [HTTP Streaming](https://api.tradestation.com/docs/fundamentals/http-streaming/) — chunked-transfer JSON streams.
- [SIM vs. LIVE](https://api.tradestation.com/docs/fundamentals/sim-vs-live/) — environment switching.
- [Rate Limiting](https://api.tradestation.com/docs/fundamentals/rate-limiting/) — per-resource buckets.
- [Auth Overview](https://api.tradestation.com/docs/fundamentals/authentication/auth-overview/)
- **[Refresh Tokens](https://api.tradestation.com/docs/fundamentals/authentication/refresh-tokens)** — the page we explicitly studied; canonical for §02.
- [Scopes](https://api.tradestation.com/docs/fundamentals/authentication/scopes/) — `openid offline_access MarketData ReadAccount Trade OptionSpreads Matrix`.

## Prior-art client libraries

- [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) — gold-standard Python broker SDK. Pydantic models, per-asset-class clients, asyncio streams.
- [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) — production-quality MCP server. FastMCP + OpenAPI registration + toolset allowlists + safety overrides.
- [mxcoppell/tradestation-api-python](https://github.com/mxcoppell/tradestation-api-python) — community Python wrapper. Service-per-category split.
- [mxcoppell/tradestation-api-ts](https://github.com/mxcoppell/tradestation-api-ts) — same author, TypeScript. Useful for cross-checking the streaming pattern.
- [areed1192/tradestation-python-api](https://github.com/areed1192/tradestation-python-api) — older wrapper, partial v2.
- [tradestation-api Rust crate](https://docs.rs/tradestation-api/latest/tradestation_api/) — canonical mirror of the v3 surface; we used it to cross-check the endpoint inventory.
- [pattertj/ts-api](https://github.com/pattertj/ts-api) — older Python wrapper; not directly used.

## Python tooling we'll lean on

- [httpx](https://www.python-httpx.org/) — HTTP/2 client with streaming.
- [pydantic v2](https://docs.pydantic.dev/) — models, validation, JSON Schema.
- [Typer](https://typer.tiangolo.com/) — CLI framework.
- [Click](https://click.palletsprojects.com/) — Typer's underlying machinery; we touch it for shell completion + custom param types.
- [Rich](https://rich.readthedocs.io/) — tables, live, prompts, JSON syntax, themes.
- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework; `pip install fastmcp`.
- [cryptography](https://cryptography.io/) — Fernet, PBKDF2.
- [keyring](https://pypi.org/project/keyring/) — OS keychain.
- [uv](https://docs.astral.sh/uv/) — workspace + lockfile.
- [hatchling](https://hatch.pypa.io/) — package backend.
- [vcrpy](https://github.com/kevin1024/vcrpy) — recorded HTTP fixtures.

## MCP

- [Model Context Protocol — Spec](https://modelcontextprotocol.io)
- [Anthropic MCP overview](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
- [FastMCP docs](https://gofastmcp.com/)

## Misc trading-domain reading

- [Alpaca MCP Server v2 announcement](https://alpaca.markets/blog/alpaca-launches-mcp-server-v2/) — design rationale we mirror (tools, toolsets, safety).
- [Build an MCP Server for Trading With Python and AI — Quantinsti](https://www.quantinsti.com/articles/mcp-server-trading-python-ai/) — informal walkthrough of the architecture pattern.
