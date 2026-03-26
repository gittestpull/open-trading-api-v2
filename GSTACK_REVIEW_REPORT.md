# GSTACK Comprehensive Review: Deep Dive Investment Platform v2

**Date:** 2026-03-26  
**Reviewer:** 태광비서 (Automated gstack Review)  
**Codebase:** open-trading-api-v2

---

## Executive Summary

Deep Dive is an ambitious **all-in-one Korean stock trading platform** combining a scalper, screener, grid ladder strategy, backtest engine, trade journal, MAGA (Trump tweet) analysis, human sentiment index, and more — all powered by KIS Open API. It's a power-user tool built for one person (회장님), not a SaaS product.

**Overall Grade: 6.2/10** — Strong feature breadth, but critical gaps in security, error handling, and architectural separation. The Grid Ladder is the crown jewel; the rest is useful but scattered.

---

## 1. CEO/Product Review

### What is this product REALLY?
A **personal trading command center** for Korean equities. The core value proposition: automate repetitive trading patterns (grid ladder DCA) and aggregate data from multiple sources (KIS, Naver, YouTube, DART) into a single dashboard.

### The 10-Star Version
| Star Level | Experience |
|---|---|
| 5★ (Current) | Web dashboard with manual trading controls |
| 7★ | Real-time P&L tracking with Telegram alerts on every fill, auto-risk cutoff |
| 8★ | AI that learns from your journal entries and suggests optimal grid parameters |
| 9★ | Voice-controlled trading via Telegram: "50만원 삼전 그리드 걸어" |
| 10★ | Fully autonomous: AI monitors market, adjusts grids, hedges positions, and reports daily |

### Narrowest Wedge
**Grid Ladder Manager** — this is the killer feature. The DCA-on-dip strategy with tick-level precision is the core workflow. Everything else (screener, backtest, journal) is supporting infrastructure.

### Bloat
- **MAGA/Trump tweet panel** — hardcoded tweet parsing with naive keyword→stock mapping. Low value, high maintenance.
- **Trading Simulator** — in-memory only, resets on restart. Not useful for serious analysis.
- **Login modal with Google/GitHub OAuth buttons** — purely decorative (buttons do nothing).

### Missing (Users Desperately Need)
1. **Sell-side grid logic** — only buys, no automated profit-taking
2. **Position-level P&L tracking** — holdings are just (price, qty) tuples, no current price comparison
3. **Stop-loss / circuit breaker** — no automated risk management
4. **Mobile-responsive grid ladder page** — critical for monitoring on-the-go
5. **Persistent alerts** — only logs, no push notifications on fills

### Grades
| Dimension | Grade | Notes |
|---|---|---|
| Product Vision | 7/10 | Clear problem, good feature intuition |
| Feature Completeness | 5/10 | Buy-only grid, no sell logic, no risk mgmt |
| User Value | 7/10 | High for the target user (회장님), low for anyone else |

---

## 2. Engineering Review

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (app.py)                      │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Scalper   │ │ Screener  │ │ Backtest │ │ Journal  │  │
│  │ (Process) │ │ (DB)      │ │ (DB)     │ │ (DB)     │  │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       │              │            │             │        │
│  ┌────┴──────────────┴────────────┴─────────────┴────┐  │
│  │              SQLite (deep_dive.db)                 │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ GridLadderManager   │  │ GridWSEngine (singleton)  │  │
│  │ (threading.Lock)    │  │ (asyncio + websockets)    │  │
│  │ ┌─────┐ ┌─────┐    │  │ KIS WS ──→ Frontend WS   │  │
│  │ │run()│ │poll │    │  │ H0STASP0: orderbook       │  │
│  │ │sync │ │1sec │    │  │ H0STCNI0: execution       │  │
│  │ └─────┘ └─────┘    │  └──────────────────────────┘  │
│  └─────────────────────┘                                │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ KIS Auth (kis_auth.py) — Token + WS Approval    │    │
│  │ Config: ~/KIS/config/kis_devlp.yaml             │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
         │                              │
    KIS REST API                  KIS WebSocket
    (orders, prices)              (realtime quotes)
```

### Data Flow: Grid Ladder Order Lifecycle

```
User clicks Start
  → POST /api/grid-ladder/start
    → GridLadderManager.__init__() [ka.auth(svr="prod")]
    → asyncio.create_task(run_in_executor(mgr.run))
      → _get_current_price() [KIS REST]
      → _place_buy_order() [KIS REST, initial market buy]
      → Loop:
        → _place_grid_orders() [-6, -7, -8 ticks]
        → _monitor_and_wait() [poll every 1s]
          → _check_execution() [KIS REST daily_ccld]
          → If -6 filled: cancel -7/-8, new base price, repeat
        → save_grid_state() [SQLite]
```

### Critical Issues

1. **Thread/Async Mismatch**: `GridLadderManager.run()` is synchronous (uses `time.sleep`, `threading.Event`) but wrapped in `asyncio.create_task(run_in_executor)`. The `_grid_lock` is a `threading.Lock` accessed from both async handlers and sync code — this works but is fragile.

2. **Blocking Event Loop**: `_recalc_saved_pending()` in the API handler does a synchronous KIS API call (`ka.auth()` + `ds.inquire_price()`) which blocks the entire FastAPI event loop during `/api/grid-ladder/status` calls.

3. **Global `sys.path` Manipulation**: `grid_ladder_manager.py` inserts paths into `sys.path` at import time. This is brittle and can cause import conflicts.

4. **No Graceful Shutdown**: `_grid_cleanup()` tries to cancel orders but catches all exceptions silently. Pending real-money orders could be left hanging.

5. **SQLite Concurrent Access**: Multiple threads write to `deep_dive.db` via raw `sqlite3.connect()` without WAL mode or connection pooling. Risk of `database is locked` errors.

### Grades
| Dimension | Grade | Notes |
|---|---|---|
| Architecture | 5/10 | Monolithic, thread/async mixing, no clear layers |
| Error Handling | 4/10 | Silent catches everywhere, no structured error reporting |
| Code Quality | 6/10 | Well-commented Korean+English, but lots of duplication |

---

## 3. Design Review

### index.html
- **Layout (7/10)**: Clean dark theme, GitHub-inspired color palette. Tab navigation works but 14 tabs is too many — needs grouping.
- **Typography (6/10)**: Consistent Tailwind defaults. No custom font hierarchy; everything feels same-weight.
- **Color (8/10)**: Excellent dark palette with semantic accent colors (green=buy, red=sell, blue=info, purple=AI).
- **Spacing (7/10)**: Consistent use of Tailwind spacing utilities.
- **Responsiveness (4/10)**: `md:grid-cols-X` used but no mobile-specific layouts. 14-tab nav bar overflows on mobile.
- **Accessibility (2/10)**: No ARIA labels, no keyboard navigation, no screen reader support, no focus indicators beyond browser defaults.
- **Interaction Design (5/10)**: No loading states, no optimistic updates, no error toasts. Actions feel disconnected.

### grid_ladder.html
- **Layout (8/10)**: Excellent 4-column layout. Orderbook rendering is professional-grade with bar charts and "MY order" tags.
- **Real-time UX (8/10)**: Flash animations on fills/cancels, WS status indicators, auto-reconnect.
- **Information Density (9/10)**: Impressive amount of data in a clean layout. The orderbook + grid overlay is the standout feature.
- **Mobile (2/10)**: 4-column grid completely breaks on mobile. The orderbook is unusable below 1200px.

### AI Slop Detection
- **Login modal**: Google/GitHub buttons that do nothing — classic AI-generated boilerplate.
- **Forgot password link**: Goes nowhere.
- **i18n system**: `data-i18n` attributes suggest translation support, but no actual translation file was found. Likely auto-generated and never completed.

### Grades
| Dimension | Grade | Notes |
|---|---|---|
| Overall Design | 7/10 | Professional dark theme, good for power users |
| Mobile UX | 3/10 | Completely unusable on mobile |
| Information Hierarchy | 6/10 | Too many features at same level; needs progressive disclosure |

---

## 4. Code Review

### [AUTO-FIX] Bugs & Issues

1. **`_recalc_saved_pending` blocks event loop** (grid status API)
   - `ka.auth(svr="prod")` and `ds.inquire_price()` are synchronous HTTP calls inside an async endpoint
   - Fix: Move to `run_in_executor` or cache with TTL

2. **`logger` used but never imported in `app.py`**
   - Line refs: `logger.error(f"[WS orderbook] Error: {e}")` — will crash on first WS error
   - Fix: Add `import logging; logger = logging.getLogger(__name__)`

3. **`self.ticker` referenced in `GridWSEngine._kis_connect()` but doesn't exist**
   - Line: `logger.info(f"[GridWSEngine] KIS WS loop ended for {self.ticker}")` 
   - Fix: Remove `self.ticker` or replace with `"engine"`

4. **Unbounded `login_attempts` dict** — never cleaned up for IPs that don't reach the block threshold
   - Fix: Add TTL or periodic cleanup

5. **`history_collector` used without import guard** — if `get_history_collector` fails, the entire app fails to start

6. **`on_event("startup")` uses deprecated FastAPI pattern** — should use lifespan context manager

### [ASK] Needs Discussion

1. **Grid Ladder has no sell logic** — is manual selling intended? Or should auto-sell be added?

2. **SQLite for production trading** — acceptable for single-user, but WAL mode should be enabled at minimum

3. **KIS token stored in plaintext file** (`~/KIS/config/KIS20260326`) — acceptable given single-user deployment?

4. **No rate limiting on public endpoints** — `verify_password` dependency is not applied to any endpoint. All APIs are publicly accessible.

5. **`max_rounds = 20` hardcoded** — should this be configurable per instance?

---

## 5. Security Review

### OWASP Top 10 Assessment

| # | Vulnerability | Status | Details |
|---|---|---|---|
| A01 | Broken Access Control | 🔴 CRITICAL | `verify_password` dependency exists but is **never used** — all endpoints are public |
| A02 | Cryptographic Failures | 🟡 MEDIUM | KIS tokens in plaintext files |
| A03 | Injection | 🟢 LOW | SQLite queries use parameterized queries consistently |
| A04 | Insecure Design | 🟡 MEDIUM | No CSRF protection, no Content-Security-Policy |
| A05 | Security Misconfiguration | 🔴 HIGH | Default password printed to stdout if not set |
| A06 | Vulnerable Components | 🟡 MEDIUM | CDN-loaded Tailwind/Chart.js (supply chain risk) |
| A07 | Auth Failures | 🔴 CRITICAL | Auth mechanism exists but is never applied to routes |
| A08 | Data Integrity | 🟢 LOW | N/A |
| A09 | Logging Failures | 🟡 MEDIUM | Failed auth logged, but no structured security event log |
| A10 | SSRF | 🟡 MEDIUM | Stock ticker input directly used in KIS API calls — no whitelist |

### STRIDE Threat Model: Grid Ladder

| Threat | Risk | Mitigation |
|---|---|---|
| **Spoofing** | Anyone can call `/api/grid-ladder/start` | No auth on endpoints |
| **Tampering** | Modify running config via PUT API | No auth |
| **Repudiation** | Trade logs in deque, lost on restart | DB persistence exists but incomplete |
| **Info Disclosure** | Account number, API keys in KIS responses | Logs may contain sensitive data |
| **Denial of Service** | Start unlimited grid instances | No resource limits |
| **Elevation** | N/A (single-user) | Low risk |

### Security Grade: 3/10
The auth system was built but never wired to any endpoint. This is the single biggest security gap.

---

## 6. QA Report

### User Flows & Breakpoints

| Flow | Breakpoint Risk | Notes |
|---|---|---|
| Start Grid Ladder | 🟡 | If KIS auth fails, pauses with user action needed |
| Grid order execution | 🟡 | 1-second polling may miss rapid fills |
| Grid stop | 🔴 | Pending orders may not cancel if KIS API is slow |
| View orderbook (WS) | 🟢 | Graceful reconnect logic |
| Screener search | 🟢 | Parameterized queries, handles empty results |
| Deep Dive analysis | 🟡 | On-demand Naver fetch may timeout |
| MAGA tweets | 🔴 | File-based, crashes if file not found (returns empty) |
| Backtest | 🟢 | Self-contained |
| Journal CRUD | 🟢 | Standard DB operations |
| Simulator trade | 🔴 | In-memory only, lost on restart |

### Edge Cases

| Scenario | Result |
|---|---|
| Market closed (after 15:30) | Grid stops monitoring (correct) |
| KIS API down | Grid pauses, user must retry/skip/stop |
| Budget = 0 | `_calculate_quantity` returns 1 (buys 1 share regardless) |
| Negative price | `price_n_ticks_below` could go below 0, clamped to tick size |
| Empty ticker | KIS API returns empty DataFrame, raises RuntimeError |
| 100+ concurrent grid instances | No limit, memory grows unboundedly |
| WebSocket disconnect during order | Order remains pending on KIS side, lost locally |
| DB locked (concurrent writes) | sqlite3.OperationalError, silent failure in `save_grid_state` |

### Top 10 Bugs by Severity

| # | Severity | Bug |
|---|---|---|
| 1 | 🔴 Critical | **No auth on any API endpoint** — anyone with URL can start trades |
| 2 | 🔴 Critical | **`logger` not imported in app.py** — WS endpoints will crash on first error |
| 3 | 🔴 Critical | **`self.ticker` AttributeError** in GridWSEngine._kis_connect() |
| 4 | 🔴 High | **Blocking KIS calls in async endpoints** — freezes entire server |
| 5 | 🔴 High | **No sell/profit-taking logic** — can only accumulate, never exit |
| 6 | 🟡 Medium | **Simulator state lost on restart** — in-memory only |
| 7 | 🟡 Medium | **SQLite concurrent write failures** — no WAL mode |
| 8 | 🟡 Medium | **Unbounded `login_attempts` dict** — memory leak |
| 9 | 🟡 Medium | **14 tabs in nav** — UX overload, breaks on mobile |
| 10 | 🟡 Medium | **MAGA panel hardcoded keyword→stock mapping** — stale data |

---

## Scorecard Summary

| Category | Grade |
|---|---|
| Product Vision | 7/10 |
| Feature Completeness | 5/10 |
| User Value | 7/10 |
| Architecture | 5/10 |
| Error Handling | 4/10 |
| Code Quality | 6/10 |
| Overall Design | 7/10 |
| Mobile UX | 3/10 |
| Information Hierarchy | 6/10 |
| Security Posture | 3/10 |
| **Weighted Average** | **5.3/10** |

---

## Top 20 Improvements (Ranked by Impact/Effort)

| # | Improvement | Impact | Effort | Ratio |
|---|---|---|---|---|
| 1 | **Apply `verify_password` to all API routes** | 🔴 Critical | 30 min | ★★★★★ |
| 2 | **Add `import logging; logger = ...` to app.py** | 🔴 Critical | 5 min | ★★★★★ |
| 3 | **Fix `self.ticker` → remove in grid_ws_engine.py** | 🔴 Critical | 5 min | ★★★★★ |
| 4 | **Move `_recalc_saved_pending` to run_in_executor** | 🔴 High | 30 min | ★★★★★ |
| 5 | **Enable SQLite WAL mode** | 🟡 Medium | 10 min | ★★★★★ |
| 6 | **Add sell/take-profit logic to Grid Ladder** | 🔴 High | 4 hr | ★★★★ |
| 7 | **Add resource limits (max 5 grid instances)** | 🟡 Medium | 30 min | ★★★★ |
| 8 | **Mobile-responsive grid_ladder.html** | 🟡 Medium | 2 hr | ★★★★ |
| 9 | **Group 14 tabs into categories (Trading / Analysis / Admin)** | 🟡 Medium | 1 hr | ★★★★ |
| 10 | **Add Telegram notifications on grid fills** | 🟢 Feature | 1 hr | ★★★★ |
| 11 | **Persist simulator state to DB** | 🟡 Medium | 1 hr | ★★★ |
| 12 | **Add loading spinners & error toasts** | 🟡 Medium | 2 hr | ★★★ |
| 13 | **Replace deprecated `on_event` with lifespan** | 🟢 Low | 30 min | ★★★ |
| 14 | **Add stop-loss / circuit breaker to Grid Ladder** | 🔴 High | 4 hr | ★★★ |
| 15 | **Clean up `sys.path` manipulation** — use proper packages | 🟡 Medium | 2 hr | ★★★ |
| 16 | **Remove fake OAuth buttons from login modal** | 🟢 Low | 10 min | ★★★ |
| 17 | **Add TTL cleanup to `login_attempts` dict** | 🟡 Medium | 30 min | ★★★ |
| 18 | **Replace MAGA hardcoded parsing with LLM analysis** | 🟡 Medium | 4 hr | ★★ |
| 19 | **Add ARIA labels & keyboard nav for accessibility** | 🟡 Medium | 4 hr | ★★ |
| 20 | **Add integration tests for Grid Ladder lifecycle** | 🟡 Medium | 8 hr | ★★ |

---

## Conclusion

The platform is a **impressive personal trading tool** with genuinely useful features — the Grid Ladder + real-time orderbook overlay is production-quality work. However, the **complete absence of authentication on API endpoints** is a showstopper for any network-exposed deployment. Items #1-5 should be fixed before the next trading day.

The biggest strategic gap is the **lack of sell-side automation**. A grid that only buys is half a strategy. Adding take-profit levels (e.g., sell at +3 ticks from average cost) would double the product's value.

*Report generated by 태광비서 gstack review engine.*
