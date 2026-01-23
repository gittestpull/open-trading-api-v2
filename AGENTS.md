# TRADING APP KNOWLEDGE BASE

**Generated:** 2026-01-23
**Context**: Python Trading Platform (KIS API)
**Stack**: Python 3.13+, uv, FastAPI, SQLite

## OVERVIEW
Automated trading system for Korea Investment & Securities (KIS) Open API. 
Includes universal scalper bots, LLM-based sentiment analysis, and a FastAPI web dashboard.

## STRUCTURE
```
open-trading-api/
├── monitor_scalp_universal.py   # [Core] Universal Scalper Bot (RSI/BB)
├── monitor_scalp_llm.py         # [Core] LLM Sentiment Bot (GPT-5.2)
├── run_web.py                   # Web Server Entry Point (Port 8001)
├── src/
│   ├── api/                     # KIS API Client Wrapper (See src/api/AGENTS.md)
│   ├── web/                     # FastAPI Application (See src/web/AGENTS.md)
│   └── scalper/                 # Bot Logic Modules
└── logs/                        # Trade Logs
```

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

## CONVENTIONS

- **Pkg Manager**: `uv` exclusively. No pip.
- **Config**: `kis_devlp.yaml` (Secrets). NEVER hardcode credentials.
- **Async**: Use `async/await` for all IO/Network calls.
- **Type Hints**: Mandatory (`def foo(x: int) -> str:`).

## KEY LOGIC

### Universal Scalper
- **Strategy**: Triple-Threat (RSI < 30 OR BB Lower OR Manual Price).
- **Safety**: 3-minute cooldown, data warming.
- **Pyramiding**: 1:2:4:8 scaling on dips.
- **Market**: KRX (09:00-15:30) + NXT (08:00-20:00).

### Web Dashboard
- **Port**: 8001
- **Stack**: FastAPI + Jinja2 + Tailwind
- **Auth**: Simple mock password.
