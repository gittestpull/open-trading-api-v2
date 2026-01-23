# WEB DASHBOARD KNOWLEDGE BASE

**Context**: Python, FastAPI, Web Dashboard
**Role**: Real-time monitoring, bot control, websocket streaming
**Stack**: FastAPI, Pydantic v2, Jinja2, Tailwind, Websockets

## STRUCTURE
- `app.py`: FastAPI entry via `create_app()`. Monolithic router for scalper, stocks, AI, and admin APIs.
- `app_patch.py`: Extension module for history collection endpoints.
- `process_manager.py`: Bot lifecycle controller (subprocess). Manages `ScalperProcess` and stdout log buffers.
- `static/`: Frontend dashboard assets (Vanilla JS/HTML/CSS). `index.html` is the primary SPA.

## CORE CAPABILITIES
- **Bot Control**: Start/stop scalper bots with specific budget/strategy via `ProcessManager`.
- **Real-time Logs**: Streaming bot output via Websockets (`/ws/logs/{ticker}`).
- **Data APIs**: Access to stock info, daily stats, investor trends, and news from SQLite.
- **AI Analysis**: LLM-driven deep-dive reports and sector leader analysis.
- **Backtesting**: RSI/MA strategy testing with performance reporting.
- **Simulator**: Trade logging and paper trading portfolio management.

## CONVENTIONS
- **FastAPI Routers**: (Requested) Use `APIRouter` to modularize `app.py`.
- **Jinja2 Templates**: (Requested) Use for dynamic page rendering instead of static `FileResponse`.
- **Async/Await**: Non-blocking IO for DB, external API calls, and Websocket handlers.
- **BackgroundTasks**: Delegate long-running data collection/backtests to background workers.
- **Pydantic**: Use strict Pydantic models for all request/response schemas.

## COMMANDS
```bash
# Start Web Server (Port 8001)
uv run python run_web.py

# Typecheck
uv run python -m mypy open-trading-api/src/web/
```

## AGENT INSTRUCTIONS
- Ensure bot control via `ProcessManager` is thread-safe using `manager._lock`.
- Maintain log buffer size (default 500) to balance visibility and memory usage.
- Serve dynamic content via Jinja2 where possible to reduce JS-side rendering complexity.
