# 02 — Auth & Credentials

## Source of truth

[TradeStation — Refresh Tokens](https://api.tradestation.com/docs/fundamentals/authentication/refresh-tokens)

> Access Tokens have a lifetime of **20 minutes**. Refresh Tokens, by default, are valid indefinitely. (Optional rotation: 30-minute rotation with a 24-hour absolute lifetime; off by default.)

The `offline_access` scope must be requested to receive a refresh token.

## What the user provides

Per the task spec, we **assume** the user already has:

| Field | Purpose |
|---|---|
| `client_id` | OAuth client identifier (from TradeStation developer dashboard) |
| `client_secret` | OAuth client secret (only required for confidential clients — Auth Code Flow with secret. PKCE clients omit this.) |
| `refresh_token` | Long-lived token previously issued during a one-time `authorize` flow |

These three values are entered once via `ts auth set` and never have to be re-entered.

## The `ts auth set` command

### UX

```
$ ts auth set
TradeStation credential setup

  Client ID         > <paste>       ← prompted; not echoed (Rich masked input)
  Client secret     > <paste>       ← masked; can be empty for public/PKCE clients
  Refresh token     > <paste>       ← masked
  Scope (optional)  > openid offline_access MarketData ReadAccount Trade
  Environment       > [live|sim]    ← default: live
  Encrypt at rest?  > [Y/n]         ← default: Y

✔ Verifying refresh token...  acquired access token (expires in 19m 58s)
✔ Encrypted with system keyring (backend: SecretService)
✔ Saved → /home/jonathan/.tscli/credentials  (perms 0600)
```

### Non-interactive form

```
ts auth set \
  --client-id $TS_CLIENT_ID \
  --client-secret $TS_CLIENT_SECRET \
  --refresh-token $TS_REFRESH_TOKEN \
  --scope "openid offline_access MarketData ReadAccount Trade" \
  --env live \
  --no-encrypt           # opt out (not recommended; writes plaintext)
```

`ts auth set` performs an end-to-end test by exchanging the refresh token for an access token (see §"Refresh exchange"). On success it writes the file; on failure it aborts and writes nothing.

## File location & permissions

| Path | What |
|---|---|
| `~/.tscli/` | Created with mode `0700` |
| `~/.tscli/credentials` | Created with mode `0600` |
| `~/.tscli/state.json` | Non-secret runtime state (last refresh attempt timestamp, environment, etc.) — `0600` |

`TS_CREDENTIALS` env var, if set, overrides the path (CI / containers).

## Encryption-at-rest scheme

Default: **Fernet** symmetric encryption (AES-128-CBC + HMAC-SHA256) from `cryptography`.

```
~/.tscli/credentials  (UTF-8 JSON)
├── version: 1
├── scheme: "fernet-v1" | "plaintext"
├── kdf: {                            # present when scheme == "fernet-v1"
│     name: "pbkdf2_hmac_sha256",
│     iterations: 600000,
│     salt_b64: "<24 random bytes, base64>"
│   }
├── ciphertext_b64: "<Fernet token>"  # decrypts to the secret payload below
└── (no other fields)
```

Decrypted payload (never on disk in plaintext unless `--no-encrypt`):

```json
{
  "client_id":                  "<opaque>",
  "client_secret":              "<opaque>",
  "refresh_token":              "<opaque>",
  "scope":                      "openid offline_access MarketData ReadAccount Trade",
  "environment":                "live",
  "access_token":               "<opaque or null>",
  "access_token_expires_at":    "2026-06-01T15:30:00Z",
  "id_token":                   "<JWT or null>",
  "saved_at":                   "2026-06-01T15:10:02Z"
}
```

### Where does the key come from?

Two-tier strategy, picked at `set` time and recorded in `state.json`:

1. **`keyring`** (preferred). The Fernet key is stored in the OS keyring (macOS Keychain, GNOME `libsecret`, Windows Credential Locker) under service `tscli`, account `credentials-key-v1`. The on-disk file holds *only* the ciphertext + KDF metadata; the key never touches the disk.
2. **`passphrase`** (fallback when keyring is unavailable, e.g. headless Linux without `libsecret`). On first save the user enters a passphrase; PBKDF2 derives the Fernet key (salt stored in the file). Every subsequent read prompts for the passphrase — or the user can export `TSCLI_PASSPHRASE` in the env.

Both modes round-trip the **same** on-disk format. The mode is recorded so the loader knows which path to take.

`--no-encrypt` writes `scheme: "plaintext"` with the payload inlined as `payload` instead of `ciphertext_b64`. We warn loudly and require `--i-understand-the-risk` to suppress.

## Refresh exchange

Per the docs page:

```
POST https://signin.tradestation.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id=<client_id>
&client_secret=<client_secret>     ← omitted for PKCE clients
&refresh_token=<refresh_token>
```

Response:

```json
{
  "access_token": "...",
  "id_token": "...",
  "token_type": "Bearer",
  "expires_in": 1200,
  "scope": "...",
  "refresh_token": "..."   // only present when rotation is enabled
}
```

### When we refresh

The library refreshes the access token **proactively**, never reactively in the hot path:

1. **Eager check.** Every authenticated request calls `auth.ensure_fresh()` which returns the cached token if `expires_at - now > skew (60s)`, else triggers a refresh first.
2. **Background tick.** When a `TradeStationClient` is held long-running (CLI streaming, MCP server), a background asyncio task wakes every `(expires_in − 90s)` to refresh ahead of expiry. Streams thus do not stall on token rotation.
3. **Rotation aware.** If the response carries a new `refresh_token`, we atomically rewrite `~/.tscli/credentials` with the new value (decrypt → swap → re-encrypt → temp-write → `fsync` → rename). Lockfile (`~/.tscli/credentials.lock`) prevents two processes (CLI + MCP) clobbering each other.
4. **Failure mode.** A 401 on `/oauth/token` ⇒ raise `tradestation.errors.RefreshTokenExpired` with a human message: *"Run `ts auth login` or supply a new refresh token via `ts auth set`."*

## Other `ts auth …` subcommands

| Command | Behavior |
|---|---|
| `ts auth status` | Prints (a) credential path, (b) scheme, (c) environment, (d) `client_id` last-4, (e) refresh-token last-4, (f) access-token expiry as a relative time + absolute UTC. **Never** prints secrets in full. Exit 0 iff a valid token can be acquired. |
| `ts auth refresh` | Forces a refresh now; prints new expiry. Useful before kicking off a long script. |
| `ts auth login` | Optional convenience: opens the browser to TradeStation's `/authorize` endpoint with `response_type=code`, captures the redirect on `http://127.0.0.1:<random>/callback`, exchanges for a refresh token, then runs the same write path as `ts auth set`. Requires PKCE-capable client. |
| `ts auth clear` | Wipes `~/.tscli/credentials` and the keyring entry. Asks for confirmation. |
| `ts auth export` | Prints the **decrypted** payload as JSON to stdout (refuses unless `--yes-i-want-secrets-on-stdout`). For one-shot migration to another machine. |
| `ts auth doctor` | Diagnostics: writes/reads a test file in `~/.tscli/`, checks keyring backend, exchanges a token, prints which scopes the response actually contains vs. requested. |

## Library API (preview — full spec in 05-python-library.md)

```python
from tradestation import TradeStationClient, Credentials

# Default: read ~/.tscli/credentials
ts = TradeStationClient.from_default_credentials()

# Or build explicitly (e.g., CI)
ts = TradeStationClient(Credentials(
    client_id="…", client_secret="…", refresh_token="…", environment="live"
))

# Or from env vars
ts = TradeStationClient.from_env()  # reads TS_CLIENT_ID / TS_CLIENT_SECRET / TS_REFRESH_TOKEN
```

## Logging

The transport layer (`transport.py`) uses a redacting `logging.Filter` so that no `Authorization` header, `client_secret`, or `refresh_token` value is ever emitted at any log level. CLI verbose mode (`-v`/`-vv`) logs request URLs + method + status only; bodies/headers redacted unless `--unsafe-log-secrets` is passed (with a big red warning).

## Security checklist

- [x] `0600` perms on the credentials file.
- [x] `0700` perms on `~/.tscli/`.
- [x] Keyring-first encryption.
- [x] Passphrase fallback with PBKDF2 (≥ 600 000 iterations, NIST-aligned).
- [x] Atomic refresh-token rotation (tempfile + rename).
- [x] Cross-process file lock for concurrent CLI / MCP refreshes.
- [x] Redaction filter in logs.
- [x] No secrets in `state.json`.
- [x] `ts auth status` shows last-4 only.
- [x] `--no-encrypt` requires an explicit "yes-I-understand" flag.
