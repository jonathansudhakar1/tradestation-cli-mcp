# 09 — Codegen Strategy

How we get from the upstream OpenAPI spec to fully-typed library, CLI, and MCP surfaces — without silently dropping fields when the API evolves.

## TL;DR

**Hybrid.** Generator owns the schema layer (models, enums, basic HTTP callables). Humans own the service-method names, error semantics, streaming parsers, CLI commands, and MCP tool ergonomics. Generated code is committed (not gitignored) so diffs surface in PR review.

```
swagger.yaml  ──►  datamodel-code-generator  ──►  src/tradestation/_generated/models.py
                                                            │
                                                            ▼
            ┌──────────── hand-written ────────────────────────────────────────┐
            │  services/*.py     (calls generated models, owns method names)   │
            │  streaming.py      (frame parsing; not in OpenAPI)               │
            │  cli/commands/*    (UX, prompts, renderers)                      │
            │  mcp/tools/*       (FastMCP registration; reads model_json_schema│
            │                     of generated request models)                 │
            └──────────────────────────────────────────────────────────────────┘
```

## The spec situation, honestly

There are **two** TradeStation specs in the wild and neither is a perfect fit:

| Source | Version | Public? | Status |
|---|---|---|---|
| [`github.com/tradestation/api-docs/spec/swagger.yaml`](https://github.com/tradestation/api-docs/blob/master/spec/swagger.yaml) | **v2** (Swagger 2.0, `https://api.tradestation.com/v2`) | ✓ public | Vendored at `vendor/swagger.yaml` (commit `edc6c1e1`, last touched **2024-05-30** — effectively frozen). |
| `https://api.tradestation.com/v3/swagger.json` | **v3** (OpenAPI 3.x, presumably) | ✗ requires Bearer token (401 unauth) | Fetched on-demand once credentials are wired. |

TradeStation marks **v3 as recommended**, so v3 is what we wrap. But the public spec is v2 only — and **upstream has been static since May 2024**, so we treat it as a vendored fossil, not a moving target. The strategy:

1. **Default codegen run:** uses `vendor/swagger.yaml` (v2). Produces a baseline model layer.
2. **One-shot authenticated fetch:** as soon as a developer has a working refresh token, `scripts/fetch_v3_spec.py` GETs `https://api.tradestation.com/v3/swagger.json` and writes `vendor/swagger.v3.json`. This is committed and from that point on becomes the primary source. Re-runs are manual (typically only when TradeStation announces a v3 change).
3. **Overlay layer:** `vendor/overlay.yaml` adds v3 paths/fields that the v3 spec omits or describes loosely. Stripe and Twilio both do this. The generator merges overlay on top of the upstream spec.

The pin file `vendor/swagger.commit.txt` records exactly which upstream commit we're vendoring + a sha256 of the file. CI checks the sha256 on every PR (one-second sanity check, no cron); if a developer manually re-vendors, the pin file is updated in the same PR.

## What we generate vs hand-write

| Concern | Source | Why |
|---|---|---|
| Pydantic v2 models for every request body, response body, definition, enum | **Generated** — `datamodel-code-generator` ➜ `src/tradestation/_generated/models.py` (and `_generated/enums.py`) | Hundreds of fields. The spec is the only source of truth. Regenerating is cheap; drift detection catches upstream change. |
| Bare HTTP "operations" (one async function per swagger operationId) | **Generated** — `_generated/operations.py` | A 1:1 typed translation layer. Hidden from users; the curated services wrap these. |
| Curated **service methods** with ergonomic names, kwargs, and overloads (e.g. `get_quotes(symbols: list[str])` joining the comma-list) | **Hand-written** in `services/*.py` | The name `get_quotes` is a product decision, not a translation. Multi-account list-joins, default param values, datetime parsing, and `pandas` integration are human ergonomics on top of generated primitives. |
| Streaming parsers (`AsyncIterator[Bar]`, `AsyncIterator[Quote]`, heartbeat filtering, reconnect) | **Hand-written** in `streaming.py` — uses generated event models | The chunk-framing protocol isn't in OpenAPI. Generated stream operations return raw bytes; we wrap them. |
| `errors.py` exception hierarchy + `human_message()` | **Hand-written** | Mapping from TS error payload shapes to our exception classes is a human contract. |
| Token refresh / auth (`auth.py`, `credentials.py`) | **Hand-written** | Spec doesn't describe credentials at rest; that's our design ([docs/02](02-auth-and-credentials.md)). |
| CLI commands (`cli/commands/*`) | **Hand-written** | Typer commands, Rich renderers, confirm prompts — entirely human ergonomics. |
| MCP tool registration | **Programmatic** — at runtime, walks the service objects and registers a FastMCP tool per method, deriving parameter schemas from `pydantic.BaseModel.model_json_schema()` on the generated request models | Free coverage: a new generated model = a new MCP tool with the right schema. |
| MCP tool *overrides* (order placement, multi-leg risk-reward, anything where the auto-shape is awkward for LLMs) | **Hand-written** in `mcp/overrides.py` | A small number of tools warrant bespoke schemas for LLM ergonomics. |

## Layout

```
vendor/
├── swagger.yaml             # upstream v2, pinned (vendored)
├── swagger.commit.txt       # pin metadata (sha256, commit SHA, fetch date)
├── swagger.v3.json          # upstream v3, vendored after first authed fetch
└── overlay.yaml             # our additions/corrections; merged on top

scripts/
├── codegen.py               # entry point: regen models from vendor/*
├── fetch_v3_spec.py         # auth + GET /v3/swagger.json + write to vendor/
└── verify_pin.py            # CI check: sha256(vendor/swagger.yaml) matches pin file

src/tradestation/_generated/
├── __init__.py              # auto-gen header: "DO NOT EDIT — generated by scripts/codegen.py from vendor/{file}@{sha}"
├── models.py                # Pydantic models for every definition
├── enums.py                 # one StrEnum per swagger enum
└── operations.py            # bare async HTTP callables — hidden from users
```

We **commit** all of `_generated/`. Pros: diffs visible in PR review (you can see what the spec change actually altered), no codegen step needed at install time. Cons: PRs that bump the spec churn a lot of lines — we accept this in exchange for transparency. A `tool.ruff.format` + `tool.ruff.lint` exclusion makes ruff leave generated files alone.

## Re-export rules

Users **never** import from `tradestation._generated` directly. The `tradestation.models` package re-exports curated names:

```python
# src/tradestation/models/__init__.py  (hand-written)
from tradestation._generated.models import (
    QuoteSnapshot as Quote,
    BarChartBar as Bar,
    AccountInfo as Account,
    # …
)
from .orders import MarketOrderRequest, LimitOrderRequest, ...  # hand-curated subclasses
```

This lets us:
- Give the public API friendly names even if upstream uses verbose ones.
- Keep generated names as a compat shim when upstream renames a definition.
- Add hand-written request models (e.g. our `MarketOrderRequest` with `frozen=True` discriminator) without polluting the generated file.

## Codegen tooling choice

**Primary: [`datamodel-code-generator`](https://github.com/koxudaxi/datamodel-code-generator).**

- Best-in-class swagger 2.0 + OpenAPI 3.x support.
- Outputs Pydantic v2 models, with discriminators, enums, optional+required correctness, and field aliases (important — TS uses PascalCase JSON keys).
- Configurable via `pyproject.toml`:

```toml
[tool.datamodel-codegen]
input-file-type            = "openapi"      # works for swagger 2.0 too
output-model-type          = "pydantic_v2.BaseModel"
field-constraints          = true
use-annotated              = true
use-standard-collections   = true
use-union-operator         = true
use-double-quotes          = true
target-python-version      = "3.10"
snake-case-field           = true            # PascalCase JSON keys → snake_case attrs
strict-nullable            = true
```

**Considered and rejected:**

- `openapi-python-client` — generates a full client (incl. operations); too opinionated about layout, harder to wire its operations into our hand-curated services.
- `swagger-codegen` / `openapi-generator` — Java toolchain dependency, ergonomic friction.
- Hand-write everything — works for v2's ~30 definitions, fails for v3's likely 100+. Maintenance debt grows without bound.

## CI integration

```
.github/workflows/
├── ci.yml                  # standard test + lint
└── verify-pin.yml          # runs scripts/verify_pin.py — fails if vendored
                            # file's sha256 doesn't match pin file
                            # (one-second sanity check; runs on every PR)
```

No cron-based auto-update workflow. The upstream public spec hasn't moved since May 2024, so polling weekly would be busywork and bot-noise in the repo. If TradeStation ever resumes publishing changes, we re-vendor manually (one `make vendor` invocation) and commit. The v3 spec — the only thing we expect to actually move — is fetched on-demand by `scripts/fetch_v3_spec.py` and committed in the PR that consumes it; it does not need a workflow.

## Coverage guarantee test

```
tests/test_inventory_coverage.py
```

Loads `vendor/swagger.yaml` (and `swagger.v3.json` if present), enumerates every `operationId`, and asserts:

1. A method exists in one of `tradestation.services.{market_data,brokerage,order_execution}` whose docstring contains a `Maps to: …operationId…` line.
2. A Typer command exists whose docstring contains the same `Maps to:` reference.
3. An MCP tool is registered (either auto or via override) with a `_ts_op_id` attribute matching.

A spec change that introduces a new operationId fails this test until all three faces (library / CLI / MCP) cover it. **This is how "don't miss anything" stays true forever.**

## Drift detection

On every `codegen` run, we emit `_generated/MANIFEST.txt` listing:

```
generated_at:    2026-06-01T08:00:23Z
generator:       datamodel-code-generator 0.25.5
source:          vendor/swagger.yaml
source_sha:      edc6c1e1e825895797e456be3264a27cd3b7903a
source_sha256:   061b6b092458c906fbd7413abf79b07cbbe484b9c3de2142e5d8b134479b03b4
overlay:         vendor/overlay.yaml
overlay_sha256:  <hash>
operations:      42        # count from operationId scan
models:          138
enums:           17
```

CI's `verify-pin.yml` confirms `_generated/MANIFEST.txt` matches what would be regenerated from the current `vendor/`. Stale generated code fails CI.

## What ships in `vendor/` today

| File | Size | Source | Notes |
|---|---:|---|---|
| `swagger.yaml` | 183,438 bytes | `tradestation/api-docs@edc6c1e1` | Swagger 2.0, v2 endpoints. Sole authoritative public spec at present. |
| `swagger.commit.txt` | — | hand-written | Pin metadata. |
| `swagger.v3.json` | (future) | `https://api.tradestation.com/v3/swagger.json` once auth is available | The real target. |
| `overlay.yaml` | (future) | hand-written | Corrections / additions for v3 quirks. |

## Risks & mitigations

- **v3 spec never gets published openly.** Mitigation: build manual v3 overlay against v2 baseline; service methods are hand-written anyway, so this is incremental work, not blocking. The auth-gated `/v3/swagger.json` is plan B; the manual overlay is plan C.
- **Generator pins.** `datamodel-code-generator` updates can shift output formatting. Pin the version in `[dev]` extras and the CI Docker image.
- **Hand-written overrides drift from generated.** Mitigated by the coverage test — any unreferenced operationId fails CI.
- **Upstream resumes publishing.** Low-probability (no commits since 2024-05-30) but possible. The manual `make vendor` path stays available; we'd notice via TradeStation's developer-portal announcements before we'd notice via any cron.
