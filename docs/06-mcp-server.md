# 06 — MCP Server (`tradestation-mcp`)

A local [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the TradeStation API to MCP-capable clients (Claude Code, Claude Desktop, Cursor, Windsurf, VS Code, Gemini CLI, …). Built on **[FastMCP](https://github.com/jlowin/fastmcp)**.

Architecture inspiration: Alpaca's official [alpaca-mcp-server v2](https://github.com/alpacahq/alpaca-mcp-server) — FastMCP + OpenAPI-driven tool registration, toolset allowlists, stdio+HTTP transports, hand-crafted overrides for destructive trading.

We add: persistent **encrypted** on-disk credentials shared with the CLI (Alpaca's MCP is env-only), plus a sharper safety model around order placement.

## Run

```bash
pip install tradestation-mcp
ts-mcp                                       # stdio (default)
ts-mcp --transport http --port 8765          # local HTTP/SSE
ts-mcp --toolsets market,brokerage           # disable trading tools
ts-mcp --profile paper                       # use ~/.tscli/profiles/paper
ts-mcp --env sim                             # force SIM
ts-mcp --read-only                           # disable all D-series tools
ts-mcp --confirm-trades require              # default; ask for explicit confirm token
```

```bash
# uvx-style one-shot (no install)
uvx tradestation-mcp
```

### MCP client config snippets

**Claude Desktop / Claude Code (`claude_desktop_config.json` / similar)**

```json
{
  "mcpServers": {
    "tradestation": {
      "command": "ts-mcp",
      "args": ["--toolsets", "market,brokerage,trading"],
      "env": {
        "TS_PROFILE": "default"
      }
    }
  }
}
```

**Cursor / Windsurf** — same `mcpServers` block.

## Transport

| Mode | When |
|---|---|
| `stdio` (default) | Local desktop / IDE clients. No port, no network. |
| `http` (`streamable-http`) | Browser/web MCP clients. Defaults to **`127.0.0.1`**; refuses non-loopback unless `--allow-remote` is given. Token-gated with `--http-token` (env: `TS_MCP_HTTP_TOKEN`). |

There is no SSE-only mode; FastMCP's streamable HTTP supersedes it.

## Tool surface (one tool per inventory row)

Tools are registered programmatically from the library's services. Tool **names** are snake_case versions of the inventory IDs. Parameter schemas come from `pydantic.BaseModel.model_json_schema()` on the request models.

### Toolset groups (allowlist)

| Toolset | Tools | Default? |
|---|---|---|
| `market` | All B-series (REST + streaming) | ✓ enabled |
| `brokerage` | All C-series (REST + streaming) | ✓ enabled |
| `trading` | All D-series + `auth_status` | ✓ enabled (gated by safety, see below) |
| `auth` | `auth_status` only | ✓ enabled |

Selectable via `--toolsets market,brokerage` (no trading) or `--toolsets all` (default).

### Tool list

#### `auth`
- `auth_status` — reports current environment, expiry, scope (no secrets).

#### `market` (matches inventory B1-B17)
- `market_data_get_bars` (B1), `market_data_get_quotes` (B2), `market_data_get_symbols` (B3)
- `market_data_list_symbol_lists` (B4), `market_data_get_symbol_list` (B5), `market_data_get_symbol_list_symbols` (B6)
- `market_data_list_crypto_pairs` (B7)
- `market_data_get_option_expirations` (B8), `market_data_get_option_strikes` (B9), `market_data_list_option_spread_types` (B10), `market_data_option_risk_reward` (B11)
- Streaming tools (B12–B17): exposed as **`*_collect`** variants that capture N events / T seconds and return a bounded list, plus **`*_subscribe`** variants that return a subscription token usable from a follow-up `stream_poll` tool. MCP doesn't natively support long-lived streams; this pattern matches Alpaca's MCP for the same reason.

#### `brokerage` (matches inventory C1-C13)
- `brokerage_list_accounts` (C1), `brokerage_get_balances` (C2), `brokerage_get_bod_balances` (C3)
- `brokerage_get_positions` (C4), `brokerage_get_orders` (C5), `brokerage_get_orders_by_id` (C6)
- `brokerage_get_historical_orders` (C7), `brokerage_get_historical_orders_by_id` (C8)
- `brokerage_get_wallets` (C9)
- Streaming: `*_collect` / `*_subscribe` for C10–C13.

#### `trading` (matches inventory D1-D8)
- `order_confirm` (D1) — **safe**; never submits.
- `order_place` (D2) — **destructive**; safety gate (see below).
- `order_replace` (D3) — destructive.
- `order_cancel` (D4) — destructive.
- `order_group_confirm` (D5) — safe.
- `order_group_place` (D6) — destructive.
- `order_list_activation_triggers` (D7), `order_list_routes` (D8) — safe.

## Safety model for destructive tools

Three modes via `--confirm-trades {off|require|review}`:

| Mode | Behavior |
|---|---|
| `off` | Tool executes immediately. **Not recommended.** |
| `require` (default) | Tool requires a `confirmation_token` param. Calling without it returns a structured *preview* (mirrors `/orderconfirm`) + a freshly-minted single-use token. The model resubmits with that token to actually place the order. Tokens expire in 60 s. |
| `review` | Tool *only* returns the preview; placement requires an out-of-band CLI step (`ts order place ...`). Useful for "LLM-as-analyst, human-as-trader" setups. |

The confirmation flow is enforced server-side; the LLM cannot bypass it by claiming the user said yes.

Additional safety:

- `--read-only` blocks D-series registration entirely.
- `--max-order-notional 50000` rejects orders whose preview estimate exceeds the cap.
- `--allowed-symbols AAPL,MSFT` whitelist (empty = all allowed).
- All destructive tool invocations are **logged** to `~/.tscli/mcp-audit.log` (one JSON line per call: timestamp, tool, account, preview hash, decision, result).

## Schema strategy

```
Pydantic request model  ──model_json_schema()──►  JSON Schema  ──►  FastMCP tool registration
```

Effect: the tool's parameters in the MCP client's UI mirror exactly the library's types. Adding a parameter to a request model in the library is the only edit needed; the MCP tool surface updates automatically.

Hand-crafted overrides (in `overrides.py`) wrap a small number of tools where the auto-generated UX is poor:

- `order_place` — flattens common shortcuts (`--limit-price`) into the schema, hides advanced fields by default.
- `market_data_option_risk_reward` — accepts a friendlier `legs: list[Leg]` shape rather than the API's flat array.

## Credentials

The server reads from `~/.tscli/credentials` (or `--profile <name>`). On startup it eagerly refreshes the access token, prints a short "✔ Authenticated as ... (env=live, expires in 19m)" banner to stderr, then begins serving. The background refresh task ([02-auth-and-credentials.md §"When we refresh"](02-auth-and-credentials.md)) keeps the token warm for the life of the process.

If `~/.tscli/credentials` is missing or invalid the server exits with code 3 and a message pointing at `ts auth set`. There is no env-only fallback by default (intentional, to keep MCP and CLI on the same secret), but `--allow-env-fallback` re-enables reading from `TS_CLIENT_ID` / `TS_CLIENT_SECRET` / `TS_REFRESH_TOKEN` for CI / containerized cases.

## Discoverable resources & prompts (FastMCP nice-to-haves)

In addition to tools, the server exposes:

- **Resources** (`tradestation://accounts`, `tradestation://positions/{accountID}`, etc.) — the same data as tools but addressable, so the LLM can pin context.
- **Prompts** (slash-commands the LLM can offer to the user):
  - `/research <symbol>` — fetches quote, recent bars, option chain, returns a Rich-tagged summary.
  - `/eod-summary <account>` — pulls positions + today's orders + Δ since BOD.
  - `/option-spread <ticker> <type>` — interactive spread builder.

## Versioning & compat

`tradestation-mcp` pins `tradestation>=x.y.z,<x.(y+1)` to avoid silent breakage when models change.

## Test posture

- Spin up the FastMCP server in-process; drive it with the official `mcp` Python client.
- For each toolset, every tool is called against a fake `TradeStationClient` and the response shape is asserted.
- Confirmation-token flow is its own test class.
