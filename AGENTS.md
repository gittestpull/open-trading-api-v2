# TRADING APP KNOWLEDGE BASE

**Generated:** 2026-01-12T00:16:12Z
**Context**: Python Trading Platform (KIS API)

## OVERVIEW
Automated trading system for Korea Investment & Securities (KIS) Open API. Includes universal scalper bots, LLM-based sentiment analysis, and a FastAPI web dashboard.

## STRUCTURE
```
open-trading-api/
├── monitor_scalp_universal.py   # [Core] Universal Scalper Bot (RSI/BB)
├── monitor_scalp_llm.py         # [Core] LLM Sentiment Bot (GPT-5.2)
├── run_web.py                   # Web Server Entry Point (Port 8001)
├── run_scalper.py               # Bot Launcher Entry Point
├── kis_devlp.yaml               # [Secret] API Credentials (GitIgnored)
├── src/
│   ├── api/                     # KIS API Client Wrapper
│   ├── web/                     # FastAPI Application
│   │   ├── static/              # HTML/JS/CSS (Tailwind)
│   │   └── routers/             # API Endpoints
│   └── scalper/                 # Bot Logic Modules
└── logs/                        # Trade Logs
```

## CONVENTIONS

### Python & Tools
- **Manager**: `uv` (Universal Package Manager)
- **Version**: Python 3.13+
- **Formatting**: Black/Ruff compatible
- **Type Hints**: Strongly encouraged (`def foo(x: int) -> str:`)

### Architecture
- **State**: stored in `scalp_data/state_{ticker}.json`
- **Logging**: `logs/{date}/{ticker}.log`
- **Web**: FastAPI + Jinja2 (minimal) + Tailwind CSS (CDN)

### Anti-Patterns
- **No Pip**: Use `uv add` / `uv sync` instead of `pip install`.
- **No Secrets in Code**: ALWAYS read `kis_devlp.yaml`.
- **No Blocking Calls**: Use `async def` in FastAPI routers.
- **No Hardcoded Accounts**: Use `kis_auth` module to load account numbers.

## COMMANDS

```bash
# Setup
uv sync

# Run Web Dashboard
uv run python run_web.py

# Run Scalper (Manual)
uv run python monitor_scalp_universal.py --ticker 005930 --budget 1000000 --live

# Run Scalper (LLM Mode)
uv run python monitor_scalp_llm.py --ticker TSLA --budget 5000 --target 0.005
```

## KEY LOGIC

### Universal Scalper (`monitor_scalp_universal.py`)
- **Strategy**: Triple-Threat (RSI < 30 OR BB Lower OR Manual Price).
- **Safety**: 3-minute cooldown, Warming up validation.
- **Pyramiding**: 1:2:4:8 scaling on dips (-1% and RSI < 25).
- **NXT Market**: Supports Pre-market (08:00) and After-market (15:40) trading.

### Web Dashboard
- **URL**: `http://localhost:8001`
- **Features**: Real-time log streaming, bot control, balance view.
- **Auth**: Simple password protection (mock).

## NOTES
- **KIS API**: Requires specific approval keys. Token expires every 24h (auto-refreshed).
- **Market Hours**: Logic handles KRX (09:00-15:30) and US Markets automatically.
