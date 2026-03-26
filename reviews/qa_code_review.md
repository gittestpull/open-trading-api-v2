# QA + Code Review Report
**Date:** 2026-03-26  
**Target:** open-trading-api-v2 (Grid Ladder + Platform)  
**Files Reviewed:** app.py, grid_ladder_manager.py, grid_ws_engine.py, grid_ladder.html, simulator.py, database.py

---

## Top 15 Bugs (Severity Ranked)

### 🔴 CRITICAL

**#1. Thread/Asyncio Deadlock — GridLadderManager.run() blocks event loop** `[ASK]`
- `grid_ladder_manager.py`: `run()` is a blocking method (uses `time.sleep()`, `threading.Event.wait()`)
- `app.py:start_grid_ladder` runs it via `loop.run_in_executor(None, mgr.run)` — OK for blocking, BUT `mgr._get_current_price()` calls KIS API synchronously inside the executor thread
- Meanwhile, `get_status()` is called from async endpoints while holding `_grid_lock` (threading.Lock)
- **Risk:** If the executor thread holds `_grid_lock` during a long KIS API call, async endpoints calling `grid_ladder_status` will block the entire event loop waiting for the lock
- **Fix:** Use `asyncio.Lock` for async endpoints, separate threading.Lock for the executor thread, or make status reads lock-free

**#2. Unclosed File Handles — GridWSEngine JSONL logs never closed on ticker unsubscribe** `[AUTO-FIX]`
- `grid_ws_engine.py:_write_log()` opens files into `self._log_files[ticker]` dict
- Files are only closed in `stop()`. If engine runs for days across date boundaries, old date files stay open forever
- `unsubscribe_ticker()` doesn't close the file
- **Fix:** Close file handle in `unsubscribe_ticker()` or rotate daily

**#3. Race Condition — Concurrent start of same ticker** `[AUTO-FIX]`
- `app.py:start_grid_ladder`: The check `if key in _grid_tasks and not _grid_tasks[key].done()` and the subsequent `_grid_instances[key] = mgr` are in separate `with _grid_lock` blocks
- Between the check and the assignment, another request could start the same ticker
- **Fix:** Move entire check+create+task-start into a single `with _grid_lock` block

**#4. Simulator state lost on restart — In-memory only** `[ASK]`
- `simulator.py`: `TradingSimulator` stores all state in memory (`SimulationState` dataclass)
- Server restart = all positions, trades, capital gone
- `export_state()` exists but is never called automatically
- **Risk:** User thinks they have positions, restarts server, everything vanishes

**#5. SQL Injection via sort_by in screener** `[AUTO-FIX]`
- `app.py:screener`: `sort_col_key` is validated against `sort_map` dict — ✅ Safe
- BUT `grid_ladder_manager.py:_get_stock_name()` uses parameterized query — ✅ Safe
- `app.py:update_grid_config` builds `f"UPDATE grid_ladder_instances SET {', '.join(updates)}"` — column names are hardcoded, params are parameterized — ✅ Safe
- **Actual issue:** `app.py` screener endpoint's `sort_order` could theoretically be injected but it's sanitized to "DESC"/"ASC" — Safe
- **No SQL injection found**, downgrading this

### 🟠 HIGH

**#5 (revised). Initial buy assumed executed after 2 seconds** `[ASK]`
- `grid_ladder_manager.py:run()` line: `time.sleep(2)` then checks execution
- If market is volatile or API slow, initial buy may not be filled yet
- Code falls through to "use order price as base price" — acceptable degradation
- BUT `order_no` could be empty string if `_place_buy_order_with_retry` returned `("", "")` after skip, then `_check_execution("")` is called
- **Risk:** `_check_execution("")` with empty order_no will query KIS with blank odno — undefined behavior

**#6. WebSocket zombie connections — No heartbeat timeout on server side** `[AUTO-FIX]`
- `app.py:ws_grid_orderbook` sends keepalive pings every 30s timeout, but never checks if client is alive
- If client disconnects ungracefully (network drop), the server loop continues forever consuming memory via the queue
- `grid_ws_engine.py:_broadcast_orderbook` has dead client cleanup for QueueFull but not for disconnected clients
- **Fix:** Add periodic ping/pong check or catch `ConnectionClosed` in send

**#7. `_grid_cleanup` calls blocking `_cancel_order` in shutdown** `[AUTO-FIX]`
- `app.py:shutdown_event` is sync, calls `_grid_cleanup()` which iterates and calls `mgr._cancel_order(order)` — this calls KIS API synchronously
- If there are many pending orders across many tickers, shutdown hangs
- **Fix:** Add timeout or fire-and-forget

**#8. Unbounded `self.state.trades` list in simulator** `[AUTO-FIX]`
- `simulator.py`: Every buy/sell appends to `self.state.trades` — unbounded list
- Long-running server with active trading = memory leak
- **Fix:** Use `deque(maxlen=10000)` or periodically flush to DB

**#9. `login_attempts` dict never cleaned up for successful IPs** `[AUTO-FIX]`
- `app.py`: `login_attempts` grows for every unique IP that ever fails. Only deleted on success.
- Bot scanners hitting the server = unbounded dict growth
- **Fix:** Add TTL-based cleanup or use `collections.OrderedDict` with max size

### 🟡 MEDIUM

**#10. XSS in grid_ladder.html — Stock name reflected unsanitized** `[AUTO-FIX]`
- `grid_ladder.html:renderInstanceCard()`: `${s.name || ''}` is injected directly into innerHTML
- If a stock name contains `<script>` or event handlers, it executes
- Stock names come from DB (originally from KIS API) — low risk but still a vulnerability
- Same issue in `searchStocks()`: `${s.name}` in innerHTML
- **Fix:** Use `textContent` or escape HTML entities

**#11. Error swallowing — bare except in multiple places** `[AUTO-FIX]`
- `grid_ws_engine.py:_broadcast_orderbook`: `except: pass` on queue operations
- `app.py:load_blocked_ips`: `except: pass`
- `app.py:shutdown_event`: `except Exception: pass` around event loop cleanup
- `grid_ladder_manager.py:_get_stock_name`: `except: return ticker`
- **Risk:** Silent failures mask real bugs in production

**#12. GridWSEngine reconnect loop references undefined `self.ticker`** `[AUTO-FIX]`
- `grid_ws_engine.py:_kis_connect()` line ~255: `f"[GridWSEngine] KIS WS loop ended for {self.ticker}"`
- `self.ticker` doesn't exist — `GridWSEngine` is multi-ticker, uses `self._subscribed_tickers`
- **Crash:** `AttributeError` when reconnect loop exhausts retries
- **Fix:** Remove `self.ticker` reference

**#13. Demo simulation checks execution by polling current price** `[ASK]`
- `grid_ladder_manager.py:_sim_check_execution` calls `_get_current_price()` on every poll
- With 1-second polling and 3 pending orders, that's 3 KIS API calls/second in demo mode
- KIS rate limit is ~20 calls/second — borderline with multiple tickers
- **Risk:** Rate limit exceeded → all API calls fail

**#14. `_recalc_saved_pending` does `sys.path.insert` and `ka.auth()` on every call** `[AUTO-FIX]`
- `app.py:_recalc_saved_pending` is called for every saved instance in `grid_ladder_status`
- Each call does `ka.auth(svr="prod")` — potentially re-authenticating with KIS on every status poll
- 5-second auto-refresh × N saved instances = excessive auth calls
- **Fix:** Cache auth or skip recalc on frequent polls

**#15. Market close check has logic bug** `[AUTO-FIX]`
- `grid_ladder_manager.py:_monitor_and_wait`: `if now.hour >= 15 and now.minute >= 30`
- This means at 16:00 (hour=16, minute=0), `minute >= 30` is False → monitoring continues after close!
- Should be: `if now.hour > 15 or (now.hour == 15 and now.minute >= 30)`

---

## Code Review Details

### 1. Memory Leaks

| Location | Issue | Category |
|----------|-------|----------|
| `simulator.py:state.trades` | Unbounded list, grows forever | [AUTO-FIX] |
| `grid_ws_engine.py:_log_files` | File handles never closed on date rollover | [AUTO-FIX] |
| `app.py:login_attempts` | Never cleaned for failed-only IPs | [AUTO-FIX] |
| `grid_ws_engine.py:_orderbooks` | Dict grows as tickers are subscribed, never pruned | [AUTO-FIX] |
| `app.py:_grid_instances` | Cleaned on stop, OK ✅ | — |

### 2. Thread Safety

| Location | Issue | Category |
|----------|-------|----------|
| `app.py:_grid_lock` | threading.Lock used across async + sync — can block event loop | [ASK] |
| `grid_ladder_manager.py:pending_orders` | Accessed from executor thread (run) AND async endpoints (get_status) without lock | [ASK] |
| `grid_ws_engine.py:_engine_lock` | asyncio.Lock — correct for async ✅ | — |

### 3. SQL Injection
**No SQL injection found.** All queries use parameterized `?` placeholders. The screener's `ORDER BY` uses a whitelist map. Grid ladder DB operations use parameterized queries.

### 4. XSS
- `grid_ladder.html`: Stock names and error messages injected via `innerHTML` without escaping — **XSS possible** if malicious data enters DB
- Trade log events (`appendTradeLog`) inject `event.reason` directly — XSS via crafted WebSocket event

### 5. WebSocket Lifecycle

| Issue | Detail |
|-------|--------|
| No server-side heartbeat timeout | Client disconnect without close frame → zombie loop |
| Reconnect uses cleared timer but not debounced | Rapid open/close could stack reconnect timers |
| `_kis_connect` infinite reconnect | max_retries=10 then stops — leaves subscribed clients with dead connection |
| Frontend reconnect on `onclose` | 5-second timer, no backoff — rapid reconnect storm possible |

### 6. Error Swallowing

| Location | Pattern | Risk |
|----------|---------|------|
| `grid_ws_engine.py:_broadcast_orderbook` | `except: pass` | Lost orderbook updates |
| `app.py:load_blocked_ips` | `except: pass` | Security feature silently broken |
| `app.py:shutdown_event` | `except Exception: pass` | Shutdown errors hidden |
| `grid_ladder_manager.py:_get_stock_name` | `except: return ticker` | DB errors hidden |
| `grid_ladder_manager.py:save_grid_state` (callers) | `except Exception as e: logger.warning(...)` | State loss on DB error |

---

## QA Report — User Flow Analysis

### Flow 1: Start grid ladder (live) → KIS key expired mid-run
- **Result:** `_get_current_price()` raises `RuntimeError` → caught by `_pause_for_user()`
- **Issue:** `_place_buy_order()` returns `("", "")` on failure but doesn't distinguish auth error from order error
- KIS token refresh via `ka.auth()` is only called once at `__init__` — **no auto-refresh**
- **Verdict:** ⚠️ Strategy pauses but user has no way to refresh auth without restart

### Flow 2: Start grid ladder (demo) → market closed
- **Result:** `_get_current_price()` returns last close price (KIS returns it even after hours)
- Demo simulation then places orders that will never fill (current price won't change)
- `_monitor_and_wait` polls for 1 hour then gives up
- **Verdict:** ⚠️ Wastes 1 hour polling. Should check market hours before starting.

### Flow 3: Multiple tickers → switch orderbook → switch back
- **Result:** `switchTicker()` closes old WS, opens new one. Old ticker's data stops.
- Returning to old ticker reconnects WS — gets fresh orderbook within seconds
- **Issue:** Grid order markers (`gridOrderMap`) are rebuilt from `allInstances` — correct
- **Verdict:** ✅ Works, minor flicker during reconnect

### Flow 4: Server restart → reload saved state → resume
- **Result:** Saved states load from DB via `load_all_grid_states()` — shown as "💾 Saved"
- **Issue:** No auto-resume mechanism. User must manually click Start again.
- Pending KIS orders from before restart are **orphaned** — still live on KIS but not tracked
- **Verdict:** 🔴 CRITICAL — Orphaned live orders on KIS after restart

### Flow 5: Edit config while running
- **Result:** `update_grid_config` modifies `mgr.config` directly and saves to DB
- The running `run()` loop reads `self.config.entry_tick_levels` on next round
- **Issue:** No synchronization — config change mid-round could cause inconsistent state
- Level change while monitoring: old levels' orders stay pending, new levels not placed until next round
- **Verdict:** ⚠️ Works but confusing behavior

### Flow 6: Stop while paused → stop while monitoring
- **Stop while paused:** `request_stop()` sets `_stop_requested=True` and unblocks `_resume_event` → exits cleanly ✅
- **Stop while monitoring:** `_stop_requested` not checked inside `_monitor_and_wait` polling loop! Waits up to 1 hour.
- **Verdict:** 🔴 Stop command ignored during monitoring — user stuck waiting

### Flow 7: 0 budget, 0 amount, negative values
- **0 budget:** `_calculate_quantity(0) → division by zero` if price is 0 (unlikely)
- Budget 0 → `total_invested(0) < total_budget(0)` is False → skips main loop → prints empty summary
- **0 amount:** `order_amount=0` → `_calculate_quantity: 0 // price = 0` → `max(0, 1) = 1` → orders 1 share at any price
- **Negative values:** No validation — negative budget wraps around comparison logic
- **Verdict:** ⚠️ Missing input validation on API endpoint

### Flow 8: Very high price stock vs very low
- **Samsung 70,000:** `order_amount=500,000 / 70,000 = 7주` → tick_size=100 → -6 ticks = 69,400 ✅
- **Penny stock 100:** `tick_size=1` → -6 ticks = 94원 → `500,000 / 94 = 5,319주` → huge order quantity
- **Issue:** No max quantity check. 5,319 shares of a penny stock might exceed KIS single-order limit.
- **Verdict:** ⚠️ Edge case — needs quantity cap

### Flow 9: Network disconnect mid-operation
- **Grid Manager:** KIS API call hangs → `_pause_for_user()` after retry exhaustion ✅
- **WS Engine:** `websockets.ConnectionClosed` caught → reconnects with backoff ✅
- **Frontend:** Auto-reconnect every 5 seconds — no exponential backoff ⚠️
- **Verdict:** Mostly handled, frontend reconnect could be improved

### Flow 10: Concurrent API calls (start same ticker twice)
- **Race condition exists** (Bug #3 above)
- Second request may overwrite first instance in `_grid_instances`
- First task continues running with no reference — zombie task
- **Verdict:** 🔴 Zombie task + orphaned KIS orders

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 4 (event loop blocking, orphaned orders on restart, stop ignored during monitor, race condition) |
| 🟠 High | 5 (unclosed files, empty order_no, zombies, simulator memory, cleanup hangs) |
| 🟡 Medium | 6 (XSS, error swallowing, undefined self.ticker, auth spam, market close bug, input validation) |

**Recommended Priority:**
1. Fix market close logic bug (#15) — one-liner, high impact
2. Fix `self.ticker` AttributeError (#12) — crashes reconnect
3. Add `_stop_requested` check in `_monitor_and_wait` polling loop (#6 QA)
4. Move start_grid_ladder check+create into single lock block (#3)
5. Add input validation for budget/amount (non-negative, reasonable ranges)
