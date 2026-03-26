# Engineering Review — Open Trading API v2

**Date:** 2026-03-26  
**Reviewer:** Engineering Review Agent  
**Scope:** Core backend (FastAPI app, Grid Ladder strategy, KIS WebSocket, auth, process management)

---

## 1. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                              │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │  trading-web (prod)  │  │ trading-staging      │                 │
│  │  :30800 → :8080      │  │ :8082 → :8080        │                 │
│  └──────────┬──────────┘  └──────────┬──────────┘                  │
└─────────────┼────────────────────────┼──────────────────────────────┘
              │                        │
              ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Application (app.py)                    │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐             │
│  │ REST API │ │ WS /ws/* │ │ Security │ │ Static    │             │
│  │ 50+ endpt│ │ 4 WS     │ │ BasicAuth│ │ HTML/JS   │             │
│  └────┬─────┘ └────┬─────┘ │ Honeypot │ └───────────┘             │
│       │             │       │ IP Block │                            │
│       │             │       └──────────┘                            │
│       ▼             ▼                                               │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              Service Layer (Singletons)               │          │
│  │  DB · StockMaster · Scheduler · HumanIndex ·          │          │
│  │  AIAnalyst · Backtest · GlobalMarket · Journal ·       │          │
│  │  Simulator · Telegram · MAGA · TradeStats · Naver     │          │
│  └──────────────────────┬───────────────────────────────┘          │
│                         │                                           │
│  ┌──────────────────────┼───────────────────────────────┐          │
│  │          Strategy Engines (in-process)                 │          │
│  │                      │                                 │          │
│  │  ┌───────────────────▼──────────┐  ┌───────────────┐  │          │
│  │  │  GridLadderManager           │  │ ProcessManager│  │          │
│  │  │  (threading.Lock + Event)    │  │ (subprocess)  │  │          │
│  │  │  run() in ThreadPoolExecutor │  │ Scalper procs │  │          │
│  │  └──────────┬───────────────────┘  └───────┬───────┘  │          │
│  │             │                              │           │          │
│  │  ┌──────────▼───────────────┐              │           │          │
│  │  │  GridWSEngine (Singleton)│              │           │          │
│  │  │  KIS WebSocket → asyncio │              │           │          │
│  │  │  Orderbook broadcast     │              │           │          │
│  │  └──────────────────────────┘              │           │          │
│  └────────────────────────────────────────────┘          │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │ SQLite DB  │ │ KIS REST   │ │ KIS WS     │
    │ deep_dive  │ │ API (prod) │ │ (realtime) │
    │ .db        │ │ orders/    │ │ orderbook/ │
    └────────────┘ │ prices     │ │ execution  │
                   └────────────┘ └────────────┘
```

**Data Flow:**
1. Browser → FastAPI REST/WS → Service singletons → SQLite / KIS API
2. Grid Ladder: FastAPI POST → `asyncio.Task(run_in_executor(mgr.run))` → KIS REST (polling)
3. Grid WS: KIS WebSocket → `GridWSEngine` → `asyncio.Queue` → Frontend WebSocket
4. Scalper: FastAPI POST → `ProcessManager.subprocess.Popen` → separate Python process

---

## 2. API Consistency Audit

### Naming Issues
| Issue | Examples | Severity |
|-------|----------|----------|
| Mixed verb styles | `POST /start`, `POST /stop/{ticker}`, `POST /collect` vs `GET /status` | Medium |
| Inconsistent pluralization | `/api/journal/entry/{id}` vs `/api/journal/entries` | Low |
| Non-RESTful patterns | `POST /api/scalper/stop/{ticker}` should be `DELETE` or `PATCH` | Medium |
| Prefix inconsistency | `/api/grid-ladder/*` (kebab) vs `/api/scalper/*` | Low |
| Auth not applied | Security middleware (`verify_password`) defined but **never used** on any endpoint | **CRITICAL** |

### Error Handling Patterns
- **Inconsistent**: Some endpoints raise `HTTPException`, others return `{"error": ...}` in 200 responses
- `get_maga_latest()` catches all exceptions and returns 200 with `{"tweets": [], "error": str(e)}`
- `simulator.buy()`/`sell()` return error dicts checked manually; no unified error model
- `delete_journal_entry` returns `{"status": "deleted"}` even if entry doesn't exist (no check on `success`)

---

## 3. Race Condition Analysis

### CRITICAL: `threading.Lock` + `asyncio` Mixing

**`_grid_lock` (threading.Lock) used inside async endpoints:**
```python
@app.post("/api/grid-ladder/start")
async def start_grid_ladder(req):
    with _grid_lock:          # ← BLOCKS the asyncio event loop!
        if key in _grid_tasks...
```

Every `with _grid_lock:` in an `async def` endpoint **blocks the entire event loop** while waiting. If `GridLadderManager.run()` (running in executor) holds resources that interact with the lock, this creates potential deadlocks.

**Specific risks:**
1. `_grid_lock` acquired in async context blocks all concurrent requests
2. `GridLadderManager.run()` runs in `run_in_executor` (thread pool) → calls `time.sleep()` (OK for thread, but `save_grid_state` opens direct SQLite connections concurrently)
3. `_grid_instances` dict accessed both from async handlers (with lock) and from executor threads (without lock in `get_status()` called during monitoring)
4. `ProcessManager._lock` (threading.Lock) also used in async endpoints — same issue

**`GridWSEngine` asyncio.Lock:**
```python
_engine_lock = asyncio.Lock()  # ← Correct for async, but...
```
This is fine for async code, but `GridLadderManager` is sync (runs in thread pool) and cannot safely interact with async queues or locks.

### SQLite Concurrent Access
- `save_grid_state()` opens new `sqlite3.connect()` each call — no connection pooling
- Multiple threads (grid managers in executor) + async handlers all hit same DB file
- SQLite default is serialized mode, but this adds contention

---

## 4. State Management Issues

### Memory vs. DB Inconsistency
| State | Storage | Problem |
|-------|---------|---------|
| `_grid_instances` | In-memory dict | Lost on restart. DB has saved state but no auto-resume |
| `_grid_tasks` | In-memory asyncio.Tasks | Lost on restart |
| `login_attempts` | In-memory dict | Lost on restart — attacker just waits for restart |
| `blocked_ips` | Memory + JSON file | Loaded at startup, but race between file writes |
| Scalper processes | `ProcessManager.processes` dict | Subprocess PIDs lost on restart — orphan processes |
| `GridWSEngine._orderbooks` | In-memory | No persistence — orderbook state lost on reconnect |
| Service singletons | Module-level via `get_*()` | Created once at `create_app` — no cleanup/refresh lifecycle |

### Lifecycle Gaps
1. **No auto-resume**: Grid ladder states saved to DB but never restored on startup
2. **Orphan processes**: If the app crashes, scalper subprocesses keep running with no way to reclaim them
3. **No graceful shutdown coordination**: `shutdown_event` calls `_grid_cleanup()` which tries `_cancel_order()` but may fail silently
4. **`@app.on_event("shutdown")` is sync** but calls `stop_all_engines()` which is async — the try/except `loop.create_task` is fragile

---

## 5. Error Handling Gaps

1. **Bare `except:` / `except Exception:`** — 12+ instances swallowing errors silently:
   - `load_blocked_ips()`: `except: pass`
   - `_get_stock_name()`: `except: return ticker`
   - `_recalc_saved_pending()`: catches everything, returns original data
   - `_grid_cleanup()`: `try: mgr._cancel_order(order) except Exception: pass`

2. **No request validation** on `sort_by` injection: `f" ORDER BY {db_col} {sort_order}"` — while `sort_map` whitelists keys, the pattern is fragile. Any future addition could introduce SQL injection.

3. **`/api/maga/latest`** — Entire endpoint wrapped in try/except returning 200 with error. No structured error response.

4. **KIS API failures in `_check_execution`** — returns `(False, 0, 0)` silently. If KIS is down, the grid manager polls forever (up to 1 hour) with no escalation.

5. **`_place_buy_order`** — returns `("", "")` on failure with no error detail propagated. Caller can't distinguish "API down" from "insufficient funds."

6. **WebSocket endpoints** — `ws_grid_orderbook` and `ws_grid_events` reference `logger` which is never imported/defined in `app.py`.

7. **`history_collector`** — referenced in `collect_sector_history` but `history_collector` is defined later in the function scope.

---

## 6. Code Duplication

1. **Grid key lookup pattern** — repeated 6 times across grid endpoints:
   ```python
   if key not in _grid_instances:
       matches = [k for k in _grid_instances if k.startswith(t + ":")]
       key = matches[0] if matches else key
   ```
   → Extract to helper function.

2. **`_init_grid_table()`** called redundantly:
   - Called in `startup_event`
   - Called again inside `save_grid_state()` every time
   - Called again inside `load_all_grid_states()`

3. **SQLite connection pattern** — `sqlite3.connect(_get_db_path())` with manual open/close repeated in 5+ places. No context manager or connection pool.

4. **sys.path manipulation** — Both `grid_ladder_manager.py` and `grid_ws_engine.py` do identical `sys.path.insert()` calls to find KIS modules. Fragile and duplicated.

5. **KIS auth calls** — `ka.auth(svr="prod")` called in `GridLadderManager.__init__`, `GridWSEngine._kis_connect`, and `_recalc_saved_pending`. No centralized auth lifecycle.

6. **Orderbook column definitions** — Duplicated between `grid_ws_engine.py` and the external `domestic_stock_functions_ws.py`.

---

## 7. Performance Bottlenecks

1. **Screener endpoint** — Executes 4 correlated subqueries (`SELECT MAX(date)`) per table per row. On a stock universe of 2000+, this is O(n×4) subqueries. Should use window functions or pre-materialized latest-date views.

2. **`/api/stocks/{ticker}`** — 5 sequential DB queries. Should be a single JOIN query.

3. **`/api/deepdive/{ticker}`** — 7 sequential queries + 2 potential on-demand HTTP fetches (Naver). No caching, no parallelism.

4. **Grid Ladder polling** — `_monitor_and_wait()` polls KIS API every 1 second per pending order. With 3 pending orders, that's 3 API calls/second for up to 1 hour. KIS rate limits are ~20 req/sec but this is wasteful. Should use WebSocket execution notices instead.

5. **WebSocket log streaming** — `/ws/logs/{ticker}` polls `manager.get_logs()` every 1 second, comparing list lengths. Should use an event-driven approach (e.g., asyncio.Event or queue).

6. **`_recalc_saved_pending()`** — Called for every saved grid instance on status check. Each call does `ka.auth(svr="prod")` + KIS API price query. With 5 saved instances, that's 5 auth + 5 price API calls per status request.

7. **`_build_saved_response(recalc=True)` default** — Always recalculates. Frontend polling `/api/grid-ladder/status` every few seconds triggers expensive KIS API calls each time.

---

## 8. Grades

| Category | Score | Notes |
|----------|-------|-------|
| **Architecture** | **5/10** | Good separation of concerns with service layer. However, mixing sync threads (GridLadder) with async (FastAPI) creates fundamental tension. No message queue, no task queue — everything in-process. SQLite as sole database limits scalability. |
| **Error Handling** | **3/10** | Pervasive silent exception swallowing. No structured error responses. No circuit breaker for KIS API. Auth middleware defined but never applied. Critical failures (order failures) handled with `pass`. |
| **Code Quality** | **4/10** | Reasonable Korean documentation. But: heavy code duplication, `sys.path` hacking, bare excepts, 700+ line god-file (app.py), global mutable state (`_grid_instances`, `blocked_ips`), no type hints on many returns, no tests evident. |

**Overall: 4.0 / 10**

---

## 9. Top 10 Engineering Fixes (Ranked by Severity)

### 🔴 P0 — Critical

**1. Authentication middleware is NEVER APPLIED**  
`verify_password` is defined but no endpoint uses `Depends(verify_password)`. The entire API is unauthenticated. The docker-compose even defaults `DASHBOARD_PASSWORD=trading123` (the honeypot password!).  
**Fix:** Add `Depends(verify_password)` to all sensitive endpoints or use a global middleware. Fix the default password.

**2. Replace `threading.Lock` with `asyncio.Lock` in async endpoints**  
Every `with _grid_lock:` in an `async def` blocks the event loop. Under load, this freezes all concurrent request handling.  
**Fix:** Convert `_grid_lock` to `asyncio.Lock`. Use `async with _grid_lock:`. For sync GridLadderManager interactions, use `run_in_executor` with a separate threading lock only inside the executor.

**3. Grid Ladder should use WebSocket execution notices instead of REST polling**  
`_monitor_and_wait()` polls `_check_execution()` via REST every 1 second. `GridWSEngine` already receives execution notices via `H0STCNI0`. These two systems are disconnected.  
**Fix:** Bridge `GridWSEngine` execution events to `GridLadderManager` via a thread-safe queue. Eliminate REST polling for execution checks.

### 🟠 P1 — High

**4. Eliminate silent exception swallowing**  
12+ bare `except: pass` blocks hide real failures. Order cancellation failures, DB save failures, and auth failures are all silently ignored.  
**Fix:** Log all exceptions at minimum. For critical paths (orders, cancellations), propagate errors to the user via the pause mechanism or status API.

**5. Fix SQLite concurrent access**  
Multiple threads open separate `sqlite3.connect()` calls to the same file with no WAL mode, no connection pool, and no retry logic.  
**Fix:** Enable WAL mode (`PRAGMA journal_mode=WAL`). Use a connection pool or single-writer pattern. Use `aiosqlite` for async handlers.

**6. Add auto-resume for Grid Ladder on startup**  
Saved grid states in DB are never restored. After a restart, all active strategies are lost.  
**Fix:** On startup, load saved states with `status='running'` and restart their tasks. Mark stopped states as `status='stopped_unclean'` for user review.

### 🟡 P2 — Medium

**7. Consolidate the 700-line `app.py` into routers**  
`app.py` contains 50+ endpoints, security logic, grid ladder management, and inline helper functions. Impossible to maintain.  
**Fix:** Split into FastAPI `APIRouter` modules: `routers/scalper.py`, `routers/grid_ladder.py`, `routers/journal.py`, `routers/admin.py`, etc.

**8. Fix `_recalc_saved_pending()` performance**  
Every status API call triggers KIS auth + price queries for all saved instances. This is O(n) KIS API calls per status poll.  
**Fix:** Cache current prices with a short TTL (5-10 seconds). Or only recalculate on explicit request (`?recalc=true`).

**9. Prevent orphan scalper processes**  
`ProcessManager` tracks PIDs in memory only. Crash = orphan processes.  
**Fix:** Write PID files to disk. On startup, check and reclaim or kill orphan processes. Use process groups for clean termination.

**10. Fix shutdown lifecycle**  
`shutdown_event` is `def` (sync) but needs to call async `stop_all_engines()`. Current try/except with `loop.create_task` is unreliable.  
**Fix:** Use `@app.on_event("shutdown") async def` and `await stop_all_engines()` directly. Ensure all grid managers are stopped and orders cancelled before process exit.

---

## Appendix: Quick-Win Checklist

- [ ] Add `Depends(verify_password)` to all `/api/*` endpoints
- [ ] Change docker-compose default password from `trading123`
- [ ] Replace `threading.Lock` → `asyncio.Lock` in async handlers
- [ ] Add `PRAGMA journal_mode=WAL` to all SQLite connections
- [ ] Extract grid key lookup into `_resolve_grid_key()` helper
- [ ] Add `logger = logging.getLogger(__name__)` to `app.py`
- [ ] Remove redundant `_init_grid_table()` calls from `save_grid_state`/`load_all_grid_states`
- [ ] Add structured `ErrorResponse` Pydantic model for all error returns
