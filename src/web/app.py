# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from .process_manager import ProcessManager


class StartScalperRequest(BaseModel):
    ticker: str
    budget: float = 1000000
    target: float = 0.005
    live_mode: bool = False
    llm_mode: bool = False
    orderbook: bool = False
    momentum: bool = False
    buy_price: float = 0


def create_app(base_dir: str) -> FastAPI:
    app = FastAPI(title="Scalper Dashboard", version="1.0.0")
    manager = ProcessManager(base_dir)
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = os.path.join(static_dir, "index.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return HTMLResponse("<h1>Scalper Dashboard</h1><p>Static files not found</p>")
    
    @app.post("/api/scalper/start")
    async def start_scalper(req: StartScalperRequest):
        result = manager.start_scalper(
            ticker=req.ticker,
            budget=req.budget,
            target=req.target,
            live_mode=req.live_mode,
            llm_mode=req.llm_mode,
            orderbook=req.orderbook,
            momentum=req.momentum,
            buy_price=req.buy_price,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.post("/api/scalper/stop/{ticker}")
    async def stop_scalper(ticker: str):
        result = manager.stop_scalper(ticker)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.get("/api/scalper/status")
    async def get_status(ticker: Optional[str] = None):
        return {"processes": manager.get_status(ticker)}
    
    @app.get("/api/scalper/logs/{ticker}")
    async def get_logs(ticker: str, lines: int = 100):
        logs = manager.get_logs(ticker, lines)
        return {"ticker": ticker, "logs": logs}
    
    @app.get("/api/scalper/states")
    async def get_states():
        return {"states": manager.get_state_files()}
    
    @app.websocket("/ws/logs/{ticker}")
    async def websocket_logs(websocket: WebSocket, ticker: str):
        await websocket.accept()
        ticker_key = ticker.upper()
        last_count = 0
        
        try:
            while True:
                logs = manager.get_logs(ticker_key, 500)
                current_count = len(logs)
                
                if current_count > last_count:
                    new_logs = logs[last_count:]
                    for log in new_logs:
                        await websocket.send_text(log)
                    last_count = current_count
                
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            pass
    
    @app.on_event("shutdown")
    def shutdown_event():
        manager.cleanup()
    
    return app
