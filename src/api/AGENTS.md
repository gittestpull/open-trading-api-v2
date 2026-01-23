# API MODULE KNOWLEDGE BASE (open-trading-api/src/api)

**Context**: Python 3.13+, KIS (Korea Investment & Securities) API Client
**Role**: Market Data Collection (KRX/Crypto), Order Execution, KIS Authentication

## CORE MODULES
- `collector.py`: Multi-threaded/Async price & market data collection
- `stock_master.py`: KIS MST file downloader/parser (CP949 encoding)
- `database.py`: Async SQLite (aiosqlite) for trade/market storage
- `kis_auth.py`: Token management & environment (Prod/Mock) switching
- `ai_analyst.py`: LLM-based sentiment & market analysis integration

## CONVENTIONS
- **Async**: `asyncio` + `aiosqlite`. Avoid blocking I/O
- **Models**: `Pydantic` for request/response schemas
- **Auth**: Always use `kis_auth.py` wrapper. No raw key handling
- **Error**: Try/Except with `logging` + `log_buffer` for trade tracking
- **KIS MST**: Handle `CP949` encoding for domestic stock master files

## DATA FLOW
1. `kis_auth` gets access token (Prod/Demo)
2. `stock_master` refreshes symbol list via MST download
3. `collector` fetches real-time/daily data to `database`
4. `journal` records execution details for performance analysis
