# Nobitex MCP Server

A complete [Model Context Protocol](https://modelcontextprotocol.io) server for the
[Nobitex](https://nobitex.ir) cryptocurrency exchange, built from the official API
documentation at <https://apidocs.nobitex.ir>. It supports **mainnet and testnet**,
both authentication schemes (user token and Ed25519 API key), and **80 tools** covering
every documented API section.

> **Testnet status:** Nobitex support has confirmed that the public testnet
> (`https://testnetapiv2.nobitex.ir`) is **currently disabled**. The server still supports it
> via `NOBITEX_ENV=testnet` and will work when it is re-enabled. Until then, use the built-in
> **paper-trading mode** (`NOBITEX_DRY_RUN=true`) described below to test your agent safely.

---

## Why a new server?

The community server at
[`xmannii/nobitex-mcp-server`](https://github.com/xmannii/nobitex-mcp-server) is not a
complete implementation:

| Check | Result |
|---|---|
| Tools exposed | 2 (`getMarketStats`, `getGlobalStats`) |
| API coverage | Market stats only |
| Base URL | `https://api.nobitex.ir` — **no longer resolves** (the official base is `https://apiv2.nobitex.ir`) |
| Authentication | None (no trading, wallet, withdrawal, or account access) |
| Testnet support | None |
| `getGlobalStats` endpoint | `POST /market/global-stats` is not in the current docs (`GET /market/stats` is) |

So the reference server cannot place orders, read balances, manage withdrawals, or target
the testnet. This project replaces it with a full-coverage implementation generated from
the 15 official OpenAPI specifications plus the documented paths in the API-key guide.

---

## Coverage

| Official API section | Tools |
|---|---|
| Market data (public) | `get_orderbook`, `get_market_depth`, `get_recent_trades`, `get_market_stats`, `get_ohlc_history`, `get_system_options` |
| User data / wallets | `get_profile`, `get_wallets`, `get_selected_wallets`, `get_wallet_balance`, `list_wallet_transactions`, `get_transactions_history`, `list_deposits`, `get_limitations`, `generate_deposit_address`, bank card/account add & delete |
| Deposit addresses | `list_deposit_addresses`, `generate_deposit_address_v2`, `update_deposit_address_title` |
| Spot trading | `place_spot_order`, `get_order_status`, `list_orders`, `cancel_order`, `cancel_old_orders`, `list_user_trades` |
| Margin trading | `list_margin_markets`, `list_liquidity_pools`, `transfer_between_wallets`, `get_margin_delegation_limit`, `place_margin_order`, `list_positions`, `get_position_status`, `close_position`, `edit_position_collateral` |
| Crypto withdrawals | `withdraw_crypto`, `confirm_withdraw`, `cancel_withdraw`, `list_withdrawals`, `get_withdrawal` |
| Rial withdrawals | `request_rial_withdrawal`, `get_rial_withdrawal`, `list_rial_withdraw_banks`, `cancel_rial_withdrawal` |
| Address book / whitelist | `validate_address_network`, `create_address_book_item`, `confirm_address_book_item`, `list_address_book`, `add_address_book`, `delete_address_book`, `activate_whitelist`, `deactivate_whitelist` |
| Security | `get_login_attempts`, `get_emergency_cancel_code`, `activate_emergency_cancel`, `get_anti_phishing`, `set_anti_phishing` |
| Referral | `list_referral_links`, `create_referral_link`, `get_referral_status`, `set_referrer` |
| Authentication | `login`, `resend_login_otp`, `legacy_login`, `logout` |
| API keys | `create_api_key`, `list_api_keys`, `delete_api_key`, `update_api_key` |
| Portfolio / P&L | `get_last_week_daily_profit`, `get_last_week_daily_total_profit`, `get_last_month_total_profit` |
| Websocket | `get_websocket_token`, `get_websocket_info` |
| Paper trading | `paper_reset`, `paper_match_open_orders` |
| Escape hatch | `request` — call any documented path with correct signing |

All tools are prefixed with `nobitex_` (e.g. `nobitex_place_spot_order`). The full list is
available at runtime via MCP `tools/list`.

---

## Install

Requires Python 3.10+.

```bash
git clone <this-repo> nobitex-mcp
cd nobitex-mcp
uv sync --extra dev          # or: python -m venv .venv && pip install -e ".[dev]"
```

Run the server over stdio:

```bash
uv run nobitex-mcp
# or
uv run python -m nobitex_mcp
```

---

## Configuration

Copy `.env.example` to `.env` and fill it in. Environment variables always win over `.env`.

| Variable | Default | Description |
|---|---|---|
| `NOBITEX_ENV` | `mainnet` | `mainnet` or `testnet` |
| `NOBITEX_BASE_URL` | derived | Explicit API base URL (overrides `NOBITEX_ENV`) |
| `NOBITEX_TOKEN` | — | User token for `Authorization: Token <token>` |
| `NOBITEX_PUBLIC_KEY` | — | Ed25519 public key (`key` field of an API key) |
| `NOBITEX_PRIVATE_KEY` | — | Ed25519 private key (URL-safe base64) |
| `NOBITEX_AUTH_MODE` | auto | `token` or `key` when both credential types are set |
| `NOBITEX_READ_ONLY` | `false` | Block all mutating operations when `true` |
| `NOBITEX_DRY_RUN` | `false` | Paper-trading mode: simulate account/trading calls locally |
| `NOBITEX_PAPER_BALANCES` | `{"usdt":"10000","rls":"100000000","btc":"0.5","eth":"5"}` | Starting paper balances (JSON) |
| `NOBITEX_PAPER_FEE_RATE` | `0.001` | Paper trading fee rate |
| `NOBITEX_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http` |
| `NOBITEX_HOST` / `NOBITEX_PORT` | `127.0.0.1` / `8000` | HTTP transport binding |
| `NOBITEX_USER_AGENT` | `TraderBot/nobitex-mcp-1.0.0` | Sent on every request |
| `NOBITEX_TIMEOUT` | `30` | HTTP timeout in seconds |

### Paper trading (recommended while testnet is disabled)

Nobitex support confirmed the testnet is currently down. `NOBITEX_DRY_RUN=true` makes the
server simulate every account and trading call in memory while still fetching **real public
market data** for prices:

```bash
NOBITEX_DRY_RUN=true
NOBITEX_ENV=mainnet          # only public orderbook/stats are fetched
NOBITEX_PAPER_BALANCES={"usdt":"10000","rls":"100000000","btc":"0.5"}
```

What is simulated:

- spot order placement (market fills at the live best bid/ask; limit fills when crossing)
- order status, list, cancel, bulk cancel
- trades, wallets/balances, profile, limitations, transactions, portfolio
- spot ↔ margin transfers, margin order/position/close/collateral
- paper helpers: `nobitex_paper_reset`, `nobitex_paper_match_open_orders`

What is **not** simulated (returns `PaperModeUnsupported`): withdrawals, address book,
API keys, security, referral, authentication. Public market data always goes to the live API.

Every paper response includes `"paper": true`, so your agent (and you) can tell it apart from
a live response. No order or withdrawal ever leaves the machine.

### Testnet (when re-enabled)

The official FAQ lists the test environments:

- Website: <https://testnet.nobitex.ir>
- API: `https://testnetapiv2.nobitex.ir`
- Websocket: `wss://ws.testnet.nobitex.ir`

When Nobitex re-enables the testnet, set:

```bash
NOBITEX_ENV=testnet
```

Every tool then targets `https://testnetapiv2.nobitex.ir`. Public market-data tools need no
credentials. Testnet credentials are created from the testnet website, not the mainnet panel.

Verify the active environment at any time:

```json
{ "tool": "nobitex_server_info", "arguments": {} }
```

```json
{
  "environment": "testnet",
  "base_url": "https://testnetapiv2.nobitex.ir",
  "is_testnet": true,
  "has_credentials": false,
  "read_only": false
}
```

### Authentication

**Option A — user token** (simplest for testing):

```bash
NOBITEX_TOKEN=your-token
```

**Option B — Ed25519 API key** (recommended for bots; supports per-key permissions and IP
allow-lists). Create a key in the Nobitex panel (`Profile → API services`) or with
`nobitex_create_api_key`, then set:

```bash
NOBITEX_PUBLIC_KEY=...
NOBITEX_PRIVATE_KEY=...
NOBITEX_AUTH_MODE=key
```

The client signs exactly what Nobitex documents:

```
message = timestamp + METHOD + full_path + raw_body
signature = url_safe_base64(Ed25519_sign(message))
```

where `full_path` includes the query string and `raw_body` is the exact JSON bytes sent.
Headers: `Nobitex-Key`, `Nobitex-Signature`, `Nobitex-Timestamp`.

> **Iranian IP required.** The FAQ states that API requests must originate from an Iranian
> IP. Paper mode only needs public market data, but that data also comes from the mainnet API,
> so the same network rule applies.

**API-key coverage.** Nobitex accepts API keys on most endpoints, but these paths are
**token-only** (the server returns `code=TokenAuthRequired` when only a key is configured):

`/apikeys/*`, `/security/anti-phishing`, `/users/login-attempts`, `/users/referral/*`,
`/security/validate-address-network`, `/auth/logout`.

Other endpoints additionally require the matching key permission (for example `DEPOSIT` for
deposit-address listing, `ADDRESS_BOOK` for address-book writes, `TRADE` for orders).

---

## Client configuration

### Claude Desktop / Claude Code

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nobitex": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/nobitex-mcp", "run", "nobitex-mcp"],
      "env": {
        "NOBITEX_ENV": "mainnet",
        "NOBITEX_DRY_RUN": "true"
      }
    }
  }
}
```

### Cursor / VS Code / generic MCP client

```json
{
  "mcpServers": {
    "nobitex": {
      "command": "/absolute/path/to/nobitex-mcp/.venv/bin/nobitex-mcp",
      "env": {
        "NOBITEX_ENV": "mainnet",
        "NOBITEX_DRY_RUN": "true",
        "NOBITEX_PUBLIC_KEY": "...",
        "NOBITEX_PRIVATE_KEY": "...",
        "NOBITEX_AUTH_MODE": "key"
      }
    }
  }
}
```

### HTTP transport

```bash
NOBITEX_TRANSPORT=streamable-http NOBITEX_PORT=8000 uv run nobitex-mcp
# MCP endpoint: http://127.0.0.1:8000/mcp
```

---

## Agent workflow example

A safe first session using paper mode (`NOBITEX_DRY_RUN=true`):

1. `nobitex_server_info` — confirm `dry_run: true` and inspect paper balances.
2. `nobitex_get_system_options` — discover currencies, networks, and limits.
3. `nobitex_get_market_stats` with `src_currency="btc"`, `dst_currency="usdt"`.
4. `nobitex_get_orderbook` with `symbol="BTCUSDT"`.
5. `nobitex_get_ohlc_history` with `symbol="BTCUSDT"`, `resolution="60"`, `to=<now>`.
6. `nobitex_get_wallets` — inspect balances.
7. `nobitex_place_spot_order` — e.g. buy 0.001 BTC/USDT at a limit price.
8. `nobitex_list_orders` / `nobitex_get_order_status` — verify the order.
9. `nobitex_cancel_order` — clean up.

All monetary values (`amount`, `price`, `stop_price`, `collateral`, `leverage`) are
**strings** to preserve decimal precision.

### Run the included demo

`examples/agent_demo.py` drives the MCP server through a complete agent loop.

```bash
# Paper mode: live prices, simulated balances, no real orders
uv run python examples/agent_demo.py

# Live read-only: real credentials, verifies reads and the trade guard
NOBITEX_PUBLIC_KEY=... NOBITEX_PRIVATE_KEY=... \
  uv run python examples/agent_demo.py --mode readonly
```

Paper output: orderbook → market buy → two limit orders → list → cancel → trades →
balances → reset. Read-only output: profile, wallets, open orders, positions,
transactions, and a blocked `place_spot_order`.

---

## Extra endpoints (escape hatch)

The API-key guide references paths that are not part of the public OpenAPI bundle. Use
`nobitex_request` for those, with the same authentication and signing:

| Path | Purpose |
|---|---|
| `POST /v2/otp/request` | Request an OTP (e.g. `usage=address_book`) |
| `POST /users/wallets/convert` | Convert between wallet balances |
| `POST /market/orders/batch-add` | Batch place spot orders |
| `POST /market/orders/cancel-batch` | Batch cancel spot orders |
| `GET /users/preferences` | User preferences |
| `GET /users/verification/status` | KYC verification status |
| `GET /notifications/list` | Notifications |
| `GET /credit/plan`, `/credit/debt-detail`, `/credit/transactions` | VIP credit |
| `POST /credit/lend`, `/credit/repay` | VIP credit operations |
| `GET /credit/lend-calculator`, `/credit/withdraw-calculator` | Credit calculators |
| `POST /users/generate-public-id` | Public deposit identifier |
| `GET /margin/fee-rates`, `/margin/my-delegation-limit-details` | Margin metadata |
| `GET /positions/active-count` | Active position count |

Example:

```json
{
  "tool": "nobitex_request",
  "arguments": {
    "method": "POST",
    "path": "/v2/otp/request",
    "body": { "usage": "address_book" }
  }
}
```

Pass `"auth": "none"` for public paths when no credentials are configured.

---

## Safety

- **Use paper mode while developing.** `NOBITEX_DRY_RUN=true` simulates all trading locally
  and is the safest option while the testnet is disabled.
- **Use testnet when available.** `NOBITEX_ENV=testnet` targets the official test environment.
- **`NOBITEX_READ_ONLY=true`** blocks every mutating request (orders, cancels, transfers,
  withdrawals, address-book changes, API-key changes) while leaving read-only POST
  endpoints such as wallet listing and order status working.
- Tools return the raw Nobitex response, including `status`, `code`, and `backOff` on
  errors. Rate-limit errors surface `retry_after` so the agent can back off.
- Withdrawals require the correct wallet id, network, and (when applicable) `X-TOTP`.
  Double-check the environment and destination before calling them.
- Never commit `.env` or private keys. `.gitignore` excludes them.

---

## Testing

```bash
uv run pytest                        # 24 unit tests (signing, auth, errors, read-only, paper, tools)
NOBITEX_LIVE_TEST=1 uv run pytest    # + 4 live public-endpoint tests
```

The unit tests verify the Ed25519 signature against the documented
`timestamp + METHOD + full_path + raw_body` construction using a real key pair, exercise the
client through `httpx.MockTransport` (no network), and cover the paper broker (fills,
balances, limits, cancels, transfers, unsupported paths).

---

## Architecture

```
src/nobitex_mcp/
├── config.py    # env/.env settings, mainnet/testnet base URLs
├── errors.py    # NobitexError hierarchy (API, auth, read-only)
├── client.py    # HTTP client, Token + Ed25519 auth, signing, read-only guard
├── paper.py     # in-memory paper broker for NOBITEX_DRY_RUN=true
├── server.py    # 80 MCP tools + entry point
└── __main__.py  # python -m nobitex_mcp

examples/
└── agent_demo.py  # paper + live read-only agent loop
```

The client is transport-agnostic and can be reused directly:

```python
from nobitex_mcp import NobitexClient

with NobitexClient(base_url="https://testnetapiv2.nobitex.ir") as client:
    print(client.get("/v3/orderbook/BTCUSDT", auth=False))
```

---

## Disclaimer

This software is provided **"as is"**, without warranty of any kind, express or implied,
including but not limited to the warranties of merchantability, fitness for a particular
purpose, and non-infringement.

**Use at your own risk.** Cryptocurrency trading involves substantial risk and you can
lose some or all of your funds. Nothing in this project is financial, investment, or
trading advice.

The author and contributors are **not responsible or liable** for any loss, damage, missed
profit, API misuse, account restriction, or other harm arising from the use of this
software, whether caused by bugs, incorrect data, network failures, exchange behavior, or
user error. You are solely responsible for every order, transfer, withdrawal, and API key
used with this server.

Always start in paper mode (`NOBITEX_DRY_RUN=true`) or on the exchange testnet, use
read-only or IP-restricted API keys where possible, and never trade more than you can
afford to lose.

This project is not affiliated with or endorsed by Nobitex.

## License

MIT — see [LICENSE](LICENSE).

*Built from the official Nobitex API documentation (<https://apidocs.nobitex.ir>) and the
FAQ test-environment details (<https://apidocs.nobitex.ir/faq>).*
