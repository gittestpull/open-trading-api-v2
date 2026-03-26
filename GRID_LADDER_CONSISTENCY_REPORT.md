# Grid Ladder Consistency Report

## 1. Stock Code Input Pattern

### Main App (index.html)
- **Modal-based search**: Opens `modal-stock-search` with `stockSearchInput` text field
- **API**: `GET /api/stocks/search?q={query}&limit=20` — returns `{stocks: [...]}`
- **Debounce**: 300ms `setTimeout` before calling `searchStocks()`
- **Enter key**: Selects first result
- **Autocomplete**: Displays clickable results in `stockSearchResults` container

### Grid Ladder (grid_ladder.html)
- **Plain text input**: `<input type="text" id="stockCode" placeholder="예: 014940" maxlength="6">`
- **No search/autocomplete**: User must manually type the 6-digit stock code
- **No name resolution**: No stock name display after entering code

### ❌ Inconsistency
Grid Ladder lacks the stock search modal that the main app uses. Users must memorize or look up stock codes separately.

---

## 2. API Pattern

### Endpoint URL Structure
| Pattern | Scalper | Grid Ladder |
|---------|---------|-------------|
| Start | `POST /api/scalper/start` (body) | `POST /api/grid-ladder/start` (body) ✅ |
| Stop | `POST /api/scalper/stop/{ticker}` (path param) | `POST /api/grid-ladder/stop` (body: `{stock_code}`) ❌ |
| Status | `GET /api/scalper/status?ticker=X` (query param) | `GET /api/grid-ladder/status?stock_code=X` (query param) ✅ |
| Logs | `GET /api/scalper/logs/{ticker}` (path param) | `GET /api/grid-ladder/logs/{stock_code}` (path param) ✅ |

### Request Model Naming
| Scalper | Grid Ladder |
|---------|-------------|
| `StartScalperRequest.ticker` | `GridLadderStartRequest.stock_code` ❌ |
| `stop_scalper(ticker: str)` path param | `GridLadderStopRequest.stock_code` body ❌ |

### Error Handling Pattern
- **Scalper**: Returns `{"error": "..."}` from ProcessManager, app raises `HTTPException(400)`
- **Grid Ladder**: Raises `HTTPException(400/404)` directly with Korean `detail` messages ✅ (acceptable)

### Background Task Pattern
- **Scalper**: `ProcessManager` spawns `subprocess.Popen`, manages lifecycle with threading, `deque` log buffer
- **Grid Ladder**: Uses `asyncio.create_task()` + `loop.run_in_executor()` for blocking `mgr.run()`. Stores in module-level dicts `_grid_instances` / `_grid_tasks`

### ❌ Inconsistencies
1. **Field naming**: `ticker` (scalper) vs `stock_code` (grid ladder)
2. **Stop endpoint**: Scalper uses path param `/stop/{ticker}`, Grid Ladder uses request body
3. **Process management**: Scalper uses dedicated `ProcessManager` class with proper locking, log buffering, cleanup. Grid Ladder uses bare module-level dicts with no thread safety or cleanup on shutdown.

---

## 3. UI Pattern

### Main App (index.html)
- **CSS Framework**: Tailwind CSS via CDN (`cdn.tailwindcss.com`)
- **Custom colors**: Extended Tailwind config with `dark-900/800/700/600` and `accent-blue/green/red/yellow/purple`
- **Font**: Not explicitly set (Tailwind default sans-serif)
- **External CSS**: `/static/css/styles.css` (131 lines, mostly animations)
- **External JS**: `/static/js/app.js` (2799 lines), `/static/js/report.js`
- **Cards**: `class="glass"` (custom), `bg-dark-800`, `border border-dark-600`, `rounded-xl`
- **Tabs**: `showTab('name')`, `tab-active` class, `border-b border-dark-600`
- **Buttons**: Tailwind utility classes (`bg-accent-blue hover:bg-blue-600 rounded-md`)
- **Real-time**: WebSocket for scalper logs (`/ws/logs/{ticker}`), WebSocket for MAGA, polling for some features
- **API calls**: `fetch()` in app.js, no auth headers in JS (HTTP Basic handled by browser)
- **i18n**: `data-i18n` attributes with `toggleLanguage()` support

### Grid Ladder (grid_ladder.html)
- **CSS Framework**: **None** — all custom CSS with CSS variables in `<style>` block
- **Custom colors**: CSS variables `--bg-primary: #0d1117`, etc. (same hex values as Tailwind config)
- **Font**: `'Paperlogy'` Google Font (explicitly loaded)
- **External CSS/JS**: None — fully self-contained single HTML file
- **Cards**: `.card` class with custom CSS
- **Buttons**: `.btn`, `.btn-start`, `.btn-stop` custom classes
- **Real-time**: `setInterval` polling every 5 seconds (no WebSocket)
- **API calls**: Inline `apiCall()` helper with `alert()` for errors

### ❌ Inconsistencies
1. **No Tailwind CSS** — Grid Ladder uses hand-written CSS instead of the project's Tailwind setup
2. **Different font** — `Paperlogy` vs Tailwind default (main app)
3. **No shared CSS/JS** — Does not load `/static/css/styles.css` or `/static/js/app.js`
4. **No i18n support** — Korean-only, no `data-i18n` attributes
5. **No auth integration** — No login modal, no HTTP Basic awareness
6. **Error display** — Uses `alert()` instead of toast/notification pattern
7. **Self-contained HTML** — 400+ lines of inline CSS/JS vs main app's external files

---

## 4. Process Management Pattern

### Scalper (ProcessManager)
- Dedicated class in `process_manager.py`
- `threading.Lock` for concurrent access
- `subprocess.Popen` for child processes
- `deque(maxlen=500)` log buffer with reader thread
- Proper cleanup: `terminate()` → `wait(timeout=5)` → `kill()`
- State files in `scalp_data/` directory
- Registered in `shutdown_event`: `manager.cleanup()`

### Grid Ladder
- Module-level dicts: `_grid_instances`, `_grid_tasks`
- No locking (asyncio single-thread, but `run_in_executor` uses thread pool)
- `asyncio.Task` wrapping `run_in_executor(None, mgr.run)` — blocking call in thread pool
- Logs stored in `GridLadderManager.trade_log` (list, no max size)
- Stop: `task.cancel()` + manual order cancellation
- **No shutdown cleanup** — `shutdown_event` does not cancel grid tasks or clean up instances
- **No crash recovery** — If server restarts, running grids are lost silently

---

## 5. Complete Inconsistencies Summary

| # | Category | Issue | Severity |
|---|----------|-------|----------|
| 1 | Field Naming | `stock_code` vs `ticker` | 🟡 Medium |
| 2 | Stop Endpoint | Body param vs path param | 🟡 Medium |
| 3 | CSS Framework | Custom CSS vs Tailwind | 🔴 High |
| 4 | Font Family | Paperlogy vs system default | 🟡 Medium |
| 5 | Stock Input | Plain text vs search modal | 🔴 High |
| 6 | Shared Assets | No CSS/JS imports | 🔴 High |
| 7 | i18n | No bilingual support | 🟡 Medium |
| 8 | Auth | No login integration | 🟡 Medium |
| 9 | Process Mgmt | No ProcessManager, no cleanup | 🔴 High |
| 10 | Real-time | Polling vs WebSocket | 🟡 Medium |
| 11 | Error UX | alert() vs toast | 🟢 Low |
| 12 | Log Buffer | Unbounded list vs deque(500) | 🟡 Medium |
| 13 | Shutdown | Not registered in shutdown_event | 🔴 High |

---

## 6. Recommended Fixes

### 6.1 Rename `stock_code` → `ticker` (API consistency)

```python
# app.py
class GridLadderStartRequest(BaseModel):
    ticker: str  # was stock_code
    ...

class GridLadderStopRequest(BaseModel):
    ticker: str  # was stock_code

# Change stop endpoint to path param:
@app.post("/api/grid-ladder/stop/{ticker}")
async def stop_grid_ladder(ticker: str):
    ...
```

Also rename in `GridLadderConfig`, `GridLadderManager`, and `grid_ladder.html`.

### 6.2 Add Grid Ladder to ProcessManager or create GridProcessManager

Either extend `ProcessManager` or create a parallel `GridLadderProcessManager` with:
- Thread lock for `_grid_instances`
- `deque(maxlen=500)` for log buffer
- Cleanup method
- Register in `shutdown_event`

### 6.3 Convert grid_ladder.html to use Tailwind + shared assets

```html
<!-- Replace custom CSS with Tailwind -->
<script src="https://cdn.tailwindcss.com"></script>
<script> /* same tailwind.config as index.html */ </script>
<link rel="stylesheet" href="/static/css/styles.css">

<!-- Remove Paperlogy font, use system default like main app -->
<!-- Add data-i18n attributes for bilingual support -->
```

### 6.4 Add stock search to grid_ladder.html

Either:
- Import the search modal from a shared JS module (extract from app.js)
- Or add a minimal search input that calls `/api/stocks/search?q=...` with debounce

### 6.5 Register shutdown cleanup

```python
@app.on_event("shutdown")
def shutdown_event():
    manager.cleanup()
    scheduler.stop()
    get_maga_engine().stop()
    # ADD: Grid Ladder cleanup
    for code, task in _grid_tasks.items():
        if not task.done():
            task.cancel()
    for code, mgr in _grid_instances.items():
        for ono, order in list(mgr.pending_orders.items()):
            mgr._cancel_order(order)
    _grid_tasks.clear()
    _grid_instances.clear()
```

### 6.6 Add WebSocket for grid ladder logs (optional but consistent)

```python
@app.websocket("/ws/grid-ladder/{ticker}")
async def websocket_grid_ladder(websocket: WebSocket, ticker: str):
    # Stream trade_log updates similar to /ws/logs/{ticker}
```

### 6.7 Cap trade_log size

```python
from collections import deque
self.trade_log: deque = deque(maxlen=500)  # was unbounded list
```
