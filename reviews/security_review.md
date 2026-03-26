# 🔒 Security Review — Open Trading API v2

**Date:** 2026-03-26  
**Reviewer:** CSO Agent (Automated Security Audit)  
**Security Posture Grade: 3/10 🔴 CRITICAL**

---

## 1. OWASP Top 10 Audit

### A01: Broken Access Control — 🔴 CRITICAL
- **Most endpoints have NO authentication.** The `verify_password` dependency exists but is **never applied** to any route. All `/api/*` endpoints (scalper, grid-ladder, admin, journal, simulator, etc.) are publicly accessible.
- Admin endpoints (`/api/admin/scheduler/start`, `/api/admin/collect`, `/api/admin/load-stocks`) are completely unprotected.
- **Grid Ladder start/stop** (real money trading!) requires zero auth.

### A02: Cryptographic Failures — 🔴 CRITICAL
- **All secrets committed to repo in plaintext:**
  - `.env`: OpenAI key (`sk-proj-z8Kf...`), YouTube key, Telegram token, Gemini key, `DASHBOARD_PASSWORD=trading123`
  - `kis_devlp.yaml`: KIS app key, app secret, account numbers, HTS ID, Telegram credentials
- Token files stored on local filesystem with no encryption.
- KIS WebSocket uses unencrypted `ws://` (not `wss://`) for production connections.

### A03: Injection — 🟡 MEDIUM
- SQL queries use parameterized queries (`?` placeholders) — good.
- **However**, the screener endpoint builds `ORDER BY` dynamically with `sort_by` input. While it validates against a whitelist (`sort_map`), the pattern of string interpolation (`f" ORDER BY {db_col} {sort_order}"`) is risky.
- `grid_ladder_manager.py` uses raw `sqlite3` with parameterized queries — acceptable.

### A04: Insecure Design — 🔴 CRITICAL
- No concept of user sessions, roles, or multi-tenancy. Single-user system with no auth boundary.
- Real-money trading operations (buy/sell/cancel) exposed as unauthenticated HTTP endpoints.
- No transaction signing or confirmation flow for financial operations.

### A05: Security Misconfiguration — 🔴 CRITICAL
- `docker-compose.yml` sets `DASHBOARD_PASSWORD=trading123` as the **default** — same as the honeypot password in `app.py`, meaning the default config triggers the honeypot on login.
- `.env` file has `DASHBOARD_PASSWORD=trading123` (same honeypot value).
- FastAPI docs (`/docs`) is publicly accessible (Swagger UI exposes all endpoints).
- Source code mounted into Docker container as writable volumes in production.
- No CORS configuration — any origin can call the API.

### A06: Vulnerable and Outdated Components — 🟡 MEDIUM
- No `requirements.txt` or lockfile visible; dependency versions unknown.
- Uses `pycryptodome` for AES — acceptable but version unverified.
- `yaml.load(f, Loader=yaml.FullLoader)` — safe (uses FullLoader, not `yaml.load()` without Loader).

### A07: Identification and Authentication Failures — 🔴 CRITICAL
- HTTP Basic Auth only (credentials sent in cleartext per request unless HTTPS enforced).
- No session tokens, JWTs, or OAuth. No MFA.
- Rate limiting is IP-based only (easily bypassed via proxies).
- Login attempts stored in-memory (`login_attempts` dict) — lost on restart.

### A08: Software and Data Integrity Failures — 🟡 MEDIUM
- Docker image not pinned to digest. No image signing.
- `/api/simulator/import` accepts arbitrary `dict` — no schema validation.

### A09: Security Logging and Monitoring Failures — 🟡 MEDIUM
- Login failures logged to stdout (`print()`) — not to structured logging.
- No audit trail for trading operations (who placed which order).
- Blocked IPs saved to JSON file but no alerting mechanism.

### A10: Server-Side Request Forgery (SSRF) — 🟢 LOW
- No user-controlled URL fetching observed. External API calls go to fixed KIS endpoints.

---

## 2. STRIDE Threat Model — Grid Ladder Feature

| Threat | Risk | Finding |
|--------|------|---------|
| **Spoofing** | 🔴 HIGH | Anyone can call `/api/grid-ladder/start` — no auth. Attacker can start real-money trades on victim's KIS account. |
| **Tampering** | 🔴 HIGH | `/api/grid-ladder/config/{ticker}` allows changing budget/levels with no auth. Attacker can modify running strategy. SQLite DB writable. |
| **Repudiation** | 🟡 MED | Trade logs exist but no cryptographic audit trail. Logs stored in mutable deque/DB — can be altered. |
| **Information Disclosure** | 🔴 HIGH | `/api/grid-ladder/status` exposes account holdings, investment amounts, order numbers. KIS credentials in config files. |
| **Denial of Service** | 🟡 MED | No rate limiting on any endpoint. Attacker can flood `/api/grid-ladder/start` to spawn unlimited asyncio tasks. |
| **Elevation of Privilege** | 🔴 HIGH | No auth = instant admin. All admin endpoints accessible. Can start/stop scheduler, trigger data collection, reset simulator. |

---

## 3. Credential Exposure Assessment

| Secret | Location | Committed? | Risk |
|--------|----------|-----------|------|
| KIS App Key | `kis_devlp.yaml` | ✅ YES | 🔴 Brokerage API access |
| KIS App Secret | `kis_devlp.yaml` | ✅ YES | 🔴 Brokerage API access |
| KIS Account Numbers | `kis_devlp.yaml` | ✅ YES | 🔴 Account identification |
| OpenAI API Key | `.env` | ✅ YES | 🟡 Cost exposure |
| Telegram Bot Token | `.env` + `kis_devlp.yaml` | ✅ YES | 🟡 Bot hijacking |
| Gemini API Key | `.env` | ✅ YES | 🟡 Cost exposure |
| YouTube API Key | `.env` | ✅ YES | 🟢 Low (read-only) |
| Dashboard Password | `.env` | ✅ YES (`trading123`) | 🔴 Default = honeypot value |

**Docker volumes mount `kis_devlp.yaml` as read-only** — good, but the file itself is in the repo.

---

## 4. Input Validation Audit

| Endpoint | Validated? | Notes |
|----------|-----------|-------|
| `POST /api/scalper/start` | ✅ Pydantic | `StartScalperRequest` model |
| `POST /api/screener` | ✅ Pydantic | `ScreenerRequest` with defaults |
| `POST /api/grid-ladder/start` | ⚠️ Partial | Pydantic model but no bounds check on `total_budget`, `order_amount` |
| `PUT /api/grid-ladder/config/{ticker}` | ⚠️ Partial | Optional fields, no min/max validation |
| `POST /api/backtest/run` | ⚠️ Partial | No date format validation on `start_date`/`end_date` |
| `POST /api/simulator/import` | 🔴 NONE | Accepts raw `dict` — no schema |
| `GET /api/scalper/logs/{ticker}` | ⚠️ Partial | `lines` param unbounded (can request billions of lines) |
| `GET /api/stocks/search?q=` | ⚠️ Partial | `q` passed directly to service — depends on downstream validation |
| Path params (`{ticker}`) | 🔴 NONE | No regex validation — any string accepted |

---

## 5. Rate Limiting

- **Login rate limiting exists** (5 attempts → permanent IP block) — but only for login.
- **Zero rate limiting on ALL API endpoints** — trading, admin, data collection.
- An attacker can:
  - Start unlimited grid ladder instances (memory/CPU exhaustion)
  - Trigger unlimited data collections
  - Flood KIS API (may cause account lockout by broker)

---

## 6. WebSocket Security

| WS Endpoint | Auth? | Risk |
|-------------|-------|------|
| `/ws/logs/{ticker}` | ❌ None | Info disclosure |
| `/ws/collection-logs` | ❌ None | Info disclosure |
| `/ws/maga` | ❌ None | Low |
| `/ws/grid-ladder/orderbook/{ticker}` | ❌ None | Real-time market data leak |
| `/ws/grid-ladder/events/{ticker}` | ❌ None | 🔴 Order fills/cancels visible to anyone |

**KIS WebSocket** (`grid_ws_engine.py`):
- Uses `ws://` (unencrypted) for production — credentials transmitted in cleartext.
- Approval key obtained via API call then sent over unencrypted WS.

---

## 7. Top 10 Security Fixes (Ranked by Risk)

| # | Fix | Severity | Effort |
|---|-----|----------|--------|
| **1** | **Add authentication to ALL endpoints** — Apply `verify_password` dependency globally or use a middleware. Grid Ladder and Admin endpoints are highest priority. | 🔴 CRITICAL | Medium |
| **2** | **Rotate ALL compromised credentials immediately** — KIS keys, OpenAI key, Telegram token are exposed in committed files. Rotate through each provider's dashboard. | 🔴 CRITICAL | Low |
| **3** | **Remove secrets from repo** — Add `.env` and `kis_devlp.yaml` to `.gitignore`. Use Docker secrets or external secret manager. Run `git filter-branch` or BFG to purge history. | 🔴 CRITICAL | Medium |
| **4** | **Fix DASHBOARD_PASSWORD default** — Docker-compose defaults to `trading123` which is the honeypot password. Remove default, require explicit setting. | 🔴 CRITICAL | Low |
| **5** | **Add rate limiting** — Use `slowapi` or custom middleware. Critical for trading endpoints (max 1 request/sec for orders) and admin endpoints. | 🔴 HIGH | Low |
| **6** | **WebSocket authentication** — Require token in initial WS handshake (query param or first message). Especially for `/ws/grid-ladder/events`. | 🔴 HIGH | Medium |
| **7** | **Use HTTPS/WSS exclusively** — KIS WS connections should use `wss://`. Enforce HTTPS on all API endpoints via reverse proxy (nginx/traefik). | 🟡 HIGH | Medium |
| **8** | **Disable Swagger UI in production** — Set `docs_url=None, redoc_url=None` when `ENV_TYPE=prod`. | 🟡 MEDIUM | Low |
| **9** | **Add input validation bounds** — Ticker regex (`^\d{6}$`), budget min/max, date format validation, `lines` param cap. | 🟡 MEDIUM | Low |
| **10** | **Implement audit logging** — Structured JSON logs for all trading operations with timestamps, IP, action. Ship to persistent storage. | 🟡 MEDIUM | Medium |

---

## Summary

This is a **live trading platform handling real money** with essentially **zero authentication** on its API. The most critical finding is that anyone with network access can start/stop/modify real-money trading strategies on the KIS brokerage account. All credentials are committed to the repository in plaintext.

**Immediate actions required:**
1. Take the service offline or restrict to localhost/VPN until auth is implemented
2. Rotate all exposed credentials (KIS, OpenAI, Telegram, Gemini)
3. Apply `Depends(verify_password)` to every route

**Grade: 3/10** — Has basic HTTP auth mechanism and parameterized SQL, but auth is never enforced and all secrets are exposed.
