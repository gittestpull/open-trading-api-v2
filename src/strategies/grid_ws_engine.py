# -*- coding: utf-8 -*-
"""
Grid WebSocket Engine — KIS 실시간 호가 + 체결통보 → Frontend 브로드캐스트
"""

import sys
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

import websockets
import pandas as pd
from io import StringIO

import pytz

KST = pytz.timezone("Asia/Seoul")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src", "core"))
sys.path.insert(0, os.path.join(ROOT_DIR, "examples_user", "domestic_stock"))

import kis_auth as ka

logger = logging.getLogger(__name__)

# Column definitions (from domestic_stock_functions_ws.py)
ORDERBOOK_COLUMNS = [
    "MKSC_SHRN_ISCD", "BSOP_HOUR", "HOUR_CLS_CODE",
    "ASKP1", "ASKP2", "ASKP3", "ASKP4", "ASKP5",
    "ASKP6", "ASKP7", "ASKP8", "ASKP9", "ASKP10",
    "BIDP1", "BIDP2", "BIDP3", "BIDP4", "BIDP5",
    "BIDP6", "BIDP7", "BIDP8", "BIDP9", "BIDP10",
    "ASKP_RSQN1", "ASKP_RSQN2", "ASKP_RSQN3", "ASKP_RSQN4", "ASKP_RSQN5",
    "ASKP_RSQN6", "ASKP_RSQN7", "ASKP_RSQN8", "ASKP_RSQN9", "ASKP_RSQN10",
    "BIDP_RSQN1", "BIDP_RSQN2", "BIDP_RSQN3", "BIDP_RSQN4", "BIDP_RSQN5",
    "BIDP_RSQN6", "BIDP_RSQN7", "BIDP_RSQN8", "BIDP_RSQN9", "BIDP_RSQN10",
    "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "OVTM_TOTAL_ASKP_RSQN", "OVTM_TOTAL_BIDP_RSQN",
    "ANTC_CNPR", "ANTC_CNQN", "ANTC_VOL", "ANTC_CNTG_VRSS", "ANTC_CNTG_VRSS_SIGN",
    "ANTC_CNTG_PRDY_CTRT", "ACML_VOL", "TOTAL_ASKP_RSQN_ICDC", "TOTAL_BIDP_RSQN_ICDC",
    "OVTM_TOTAL_ASKP_ICDC", "OVTM_TOTAL_BIDP_ICDC", "STCK_DEAL_CLS_CODE",
]

CCNL_NOTICE_COLUMNS = [
    "CUST_ID", "ACNT_NO", "ODER_NO", "ODER_QTY", "SELN_BYOV_CLS", "RCTF_CLS",
    "ODER_KIND", "ODER_COND", "STCK_SHRN_ISCD", "CNTG_QTY", "CNTG_UNPR",
    "STCK_CNTG_HOUR", "RFUS_YN", "CNTG_YN", "ACPT_YN", "BRNC_NO", "ACNT_NO2",
    "ACNT_NAME", "ORD_COND_PRC", "ORD_EXG_GB", "POPUP_YN", "FILLER", "CRDT_CLS",
    "CRDT_LOAN_DATE", "CNTG_ISNM40", "ODER_PRC",
]


@dataclass
class OrderbookLevel:
    price: int
    qty: int


@dataclass
class OrderbookState:
    ticker: str = ""
    asks: List[OrderbookLevel] = field(default_factory=list)  # 매도 (낮은가→높은가, idx0=최우선)
    bids: List[OrderbookLevel] = field(default_factory=list)  # 매수 (높은가→낮은가, idx0=최우선)
    total_ask_qty: int = 0
    total_bid_qty: int = 0
    current_price: int = 0     # 현재가(최근 체결가)
    price_change: int = 0      # 전일 대비
    acml_vol: int = 0          # 누적 거래량
    time: str = ""

    def to_dict(self) -> dict:
        return {
            "type": "orderbook",
            "ticker": self.ticker,
            "asks": [{"price": a.price, "qty": a.qty} for a in self.asks],
            "bids": [{"price": b.price, "qty": b.qty} for b in self.bids],
            "total_ask_qty": self.total_ask_qty,
            "total_bid_qty": self.total_bid_qty,
            "current_price": self.current_price,
            "price_change": self.price_change,
            "acml_vol": self.acml_vol,
            "time": self.time,
        }


class GridWSEngine:
    """
    KIS WebSocket → 실시간 호가/체결통보 수신 → Frontend WS 브로드캐스트 + JSONL 로깅
    
    싱글톤: 1개의 KIS WS 연결로 다수 종목 구독 (KIS 제한: appkey당 1 연결)
    """

    def __init__(self, env_dv: str = "real"):
        self.env_dv = env_dv
        
        # Multi-ticker orderbook state
        self._orderbooks: Dict[str, OrderbookState] = {}
        self._subscribed_tickers: Set[str] = set()

        # Frontend WebSocket clients per ticker
        self._orderbook_clients: Dict[str, Set[asyncio.Queue]] = {}  # {ticker: set(queues)}
        self._event_clients: Dict[str, Set[asyncio.Queue]] = {}     # {ticker: set(queues)}

        # KIS WS state
        self._kis_ws = None
        self._kis_task: Optional[asyncio.Task] = None
        self._running = False
        self._data_map: Dict[str, dict] = {}
        self._approval_key: str = ""

        # JSONL log
        self._log_dir = os.path.join(ROOT_DIR, "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_files: Dict[str, any] = {}  # {ticker: file}

    # ── Logging ──────────────────────────────────────────────

    def _write_log(self, ticker: str, event_type: str, data: dict):
        if ticker not in self._log_files:
            today = datetime.now(KST).strftime("%Y%m%d")
            path = os.path.join(self._log_dir, f"grid_ladder_{ticker}_{today}.jsonl")
            self._log_files[ticker] = open(path, "a", encoding="utf-8")
        entry = {"ts": datetime.now(KST).isoformat(), "event": event_type, "data": data}
        self._log_files[ticker].write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._log_files[ticker].flush()

    # ── Frontend client management ───────────────────────────

    def subscribe_orderbook(self, ticker: str) -> asyncio.Queue:
        t = ticker.upper()
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        if t not in self._orderbook_clients:
            self._orderbook_clients[t] = set()
        self._orderbook_clients[t].add(q)
        return q

    def unsubscribe_orderbook(self, ticker: str, q: asyncio.Queue):
        t = ticker.upper()
        if t in self._orderbook_clients:
            self._orderbook_clients[t].discard(q)

    def subscribe_events(self, ticker: str) -> asyncio.Queue:
        t = ticker.upper()
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        if t not in self._event_clients:
            self._event_clients[t] = set()
        self._event_clients[t].add(q)
        return q

    def unsubscribe_events(self, ticker: str, q: asyncio.Queue):
        t = ticker.upper()
        if t in self._event_clients:
            self._event_clients[t].discard(q)

    async def _broadcast_orderbook(self, ticker: str, data: dict):
        clients = self._orderbook_clients.get(ticker, set())
        dead = []
        for q in clients:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                try: q.get_nowait()
                except: pass
                try: q.put_nowait(data)
                except: dead.append(q)
        for q in dead:
            clients.discard(q)

    async def broadcast_event(self, ticker: str, event: dict):
        clients = self._event_clients.get(ticker, set())
        dead = []
        for q in clients:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try: q.get_nowait()
                except: pass
                try: q.put_nowait(event)
                except: dead.append(q)
        for q in dead:
            clients.discard(q)
        self._write_log(ticker, event.get("type", "event"), event)

    # ── Parse KIS WS messages ────────────────────────────────

    def _parse_orderbook_raw(self, fields: list) -> Optional[str]:
        """
        Parse H0STASP0 raw fields. Returns ticker.
        """
        if len(fields) < 45:
            return None
        
        ticker = fields[0].strip() if fields[0] else ""

        asks = []
        bids = []
        for i in range(10):
            ap = int(fields[3 + i] or 0)
            aq = int(fields[23 + i] or 0)
            bp = int(fields[13 + i] or 0)
            bq = int(fields[33 + i] or 0)
            if ap > 0:
                asks.append(OrderbookLevel(price=ap, qty=aq))
            if bp > 0:
                bids.append(OrderbookLevel(price=bp, qty=bq))

        # asks: ascending (KIS already sends them ascending)
        asks.sort(key=lambda x: x.price)
        # bids: descending (KIS sends them descending)
        bids.sort(key=lambda x: x.price, reverse=True)

        raw_time = fields[1] if len(fields) > 1 else ""
        formatted_time = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}" if len(raw_time) >= 6 else raw_time

        # Get or create orderbook for this ticker
        if ticker not in self._orderbooks:
            self._orderbooks[ticker] = OrderbookState(ticker=ticker)
        ob = self._orderbooks[ticker]
        
        ob.asks = asks
        ob.bids = bids
        ob.total_ask_qty = int(fields[43] or 0) if len(fields) > 43 else 0
        ob.total_bid_qty = int(fields[44] or 0) if len(fields) > 44 else 0
        ob.acml_vol = int(fields[53] or 0) if len(fields) > 53 else 0
        ob.time = formatted_time
        
        if len(fields) > 59 and fields[59]:
            try: ob.current_price = int(fields[59])
            except: pass
        
        if len(fields) > 50 and fields[50]:
            try:
                raw_val = int(fields[50])
                if abs(raw_val) > 1000 and ob.current_price > 0:
                    ob.price_change = ob.current_price - abs(raw_val)
                else:
                    ob.price_change = raw_val
            except: pass
        
        return ticker

    def _parse_orderbook(self, row: pd.Series):
        """Fallback: parse from DataFrame row (unused if raw parsing works)"""
        pass  # Now using _parse_orderbook_raw instead

    def _parse_ccnl_notice(self, row: pd.Series) -> Optional[dict]:
        """Parse H0STCNI0/H0STCNI9 row into event dict"""
        cntg_yn = str(row.get("CNTG_YN", "")).strip()
        ticker = str(row.get("STCK_SHRN_ISCD", "")).strip()
        order_no = str(row.get("ODER_NO", "")).strip()
        cntg_qty = int(row.get("CNTG_QTY", 0) or 0)
        cntg_price = int(row.get("CNTG_UNPR", 0) or 0)
        order_qty = int(row.get("ODER_QTY", 0) or 0)
        order_price = int(row.get("ODER_PRC", 0) or 0)
        raw_time = str(row.get("STCK_CNTG_HOUR", ""))
        formatted = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}" if len(raw_time) >= 6 else raw_time

        if cntg_yn == "2":
            return {
                "type": "fill",
                "ticker": ticker,
                "order_no": order_no,
                "price": cntg_price,
                "qty": cntg_qty,
                "time": formatted,
            }
        elif cntg_yn == "1":
            acpt_yn = str(row.get("ACPT_YN", "")).strip()
            rfus_yn = str(row.get("RFUS_YN", "")).strip()
            rctf_cls = str(row.get("RCTF_CLS", "")).strip()

            if rfus_yn == "Y":
                return {"type": "error", "ticker": ticker, "order_no": order_no, "reason": "order_rejected", "time": formatted}
            if rctf_cls == "2":
                return {"type": "cancel", "ticker": ticker, "order_no": order_no, "qty": order_qty, "price": order_price, "time": formatted}
            return {"type": "order", "ticker": ticker, "order_no": order_no, "qty": order_qty, "price": order_price, "time": formatted}
        return None

    # ── KIS WebSocket connection ─────────────────────────────

    def _build_sub_msg(self, tr_id: str, tr_key: str, tr_type: str = "1") -> dict:
        """Build KIS WS subscription message"""
        return {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
        }

    async def subscribe_ticker(self, ticker: str):
        """Subscribe to orderbook for a new ticker on existing WS"""
        t = ticker.upper()
        if t in self._subscribed_tickers:
            return
        self._subscribed_tickers.add(t)
        if self._kis_ws:
            msg = self._build_sub_msg("H0STASP0", t)
            await self._kis_ws.send(json.dumps(msg))
            logger.info(f"[GridWSEngine] Subscribed H0STASP0 for {t}")

    async def unsubscribe_ticker(self, ticker: str):
        """Unsubscribe from orderbook for a ticker"""
        t = ticker.upper()
        if t not in self._subscribed_tickers:
            return
        self._subscribed_tickers.discard(t)
        if self._kis_ws:
            msg = self._build_sub_msg("H0STASP0", t, tr_type="2")
            await self._kis_ws.send(json.dumps(msg))
            logger.info(f"[GridWSEngine] Unsubscribed H0STASP0 for {t}")

    async def _kis_connect(self):
        """Connect to KIS WebSocket"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: ka.auth(svr="prod"))
        await loop.run_in_executor(None, lambda: ka.auth_ws(svr="prod"))
        
        env = ka.getTREnv()
        self._approval_key = ka._base_headers_ws.get("approval_key", "")
        if not self._approval_key:
            logger.error("[GridWSEngine] Failed to get WS approval_key")
            return

        cn_tr_id = "H0STCNI0" if self.env_dv == "real" else "H0STCNI9"
        hts_id = env.my_htsid

        ws_url = env.my_url_ws.rstrip("/") + "/"
        logger.info(f"[GridWSEngine] Connecting to {ws_url}")

        max_retries = 10
        retry = 0

        while self._running and retry < max_retries:
            try:
                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    self._kis_ws = ws
                    logger.info(f"[GridWSEngine] KIS WS connected")

                    # Subscribe execution notice
                    cn_msg = self._build_sub_msg(cn_tr_id, hts_id)
                    await ws.send(json.dumps(cn_msg))
                    logger.info(f"[GridWSEngine] Subscribed {cn_tr_id} for {hts_id}")
                    await asyncio.sleep(0.3)

                    # Subscribe all pending tickers
                    for t in list(self._subscribed_tickers):
                        msg = self._build_sub_msg("H0STASP0", t)
                        await ws.send(json.dumps(msg))
                        logger.info(f"[GridWSEngine] Subscribed H0STASP0 for {t}")
                        await asyncio.sleep(0.2)

                    retry = 0  # Reset on successful connect

                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_kis_message(raw)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[GridWSEngine] KIS WS closed: {e}")
            except Exception as e:
                logger.error(f"[GridWSEngine] KIS WS error: {e}")

            if self._running:
                retry += 1
                wait = min(retry * 2, 30)
                logger.info(f"[GridWSEngine] Reconnecting in {wait}s (attempt {retry}/{max_retries})")
                await asyncio.sleep(wait)

        logger.info(f"[GridWSEngine] KIS WS loop ended for {self.ticker}")

    async def _handle_kis_message(self, raw: str):
        """Process a raw KIS WebSocket message"""
        if not raw:
            return

        # Data messages start with 0 or 1
        if raw[0] in ("0", "1"):
            parts = raw.split("|")
            if len(parts) < 4:
                return

            encrypted = parts[0]
            tr_id = parts[1]
            count = parts[2]
            data_str = parts[3]

            # Decrypt if needed
            if encrypted == "1" and tr_id in self._data_map:
                dm = self._data_map[tr_id]
                if dm.get("key") and dm.get("iv"):
                    data_str = ka.aes_cbc_base64_dec(dm["key"], dm["iv"], data_str)

            # Determine columns
            if tr_id == "H0STASP0":
                columns = ORDERBOOK_COLUMNS
            elif tr_id in ("H0STCNI0", "H0STCNI9"):
                columns = CCNL_NOTICE_COLUMNS
            else:
                return

            try:
                fields = data_str.split("^")
                logger.debug(f"[GridWSEngine] {tr_id} raw fields count={len(fields)}")
                if tr_id == "H0STASP0" and len(fields) != len(columns):
                    logger.warning(f"[GridWSEngine] Column mismatch: got {len(fields)} fields, expected {len(columns)}")
                
                df = pd.read_csv(
                    StringIO(data_str), header=None, sep="^", names=columns[:len(fields)] if len(fields) < len(columns) else columns, dtype=object
                )
            except Exception as e:
                logger.warning(f"[GridWSEngine] Parse error for {tr_id}: {e}")
                return

            for _, row in df.iterrows():
                if tr_id == "H0STASP0":
                    raw_fields = data_str.split("^")
                    parsed_ticker = self._parse_orderbook_raw(raw_fields)
                    if parsed_ticker and parsed_ticker in self._orderbooks:
                        ob_data = self._orderbooks[parsed_ticker].to_dict()
                        await self._broadcast_orderbook(parsed_ticker, ob_data)
                        self._write_log(parsed_ticker, "orderbook", ob_data)
                elif tr_id in ("H0STCNI0", "H0STCNI9"):
                    event = self._parse_ccnl_notice(row)
                    if event:
                        evt_ticker = event.get("ticker", "")
                        await self.broadcast_event(evt_ticker, event)

        else:
            # System response (subscription confirmation, ping/pong)
            try:
                rsp = json.loads(raw)
            except json.JSONDecodeError:
                return

            header = rsp.get("header", {})
            tr_id = header.get("tr_id", "")
            encrypt = header.get("encrypt", "N")

            body = rsp.get("body", {})
            output = body.get("output", {})

            if encrypt == "Y":
                self._data_map[tr_id] = {
                    "key": output.get("key", ""),
                    "iv": output.get("iv", ""),
                }

            # Ping/pong — KIS sends PINGPONG, echo back same message
            if tr_id == "PINGPONG":
                if self._kis_ws:
                    await self._kis_ws.send(raw)
                    logger.debug("[GridWSEngine] PINGPONG replied")

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self):
        """Start KIS WS connection in background"""
        if self._running:
            return
        self._running = True
        self._kis_task = asyncio.create_task(self._kis_connect())
        logger.info(f"[GridWSEngine] Started")

    async def stop(self):
        """Stop KIS WS connection"""
        self._running = False
        if self._kis_ws:
            try: await self._kis_ws.close()
            except: pass
        if self._kis_task and not self._kis_task.done():
            self._kis_task.cancel()
            try: await self._kis_task
            except: pass
        for f in self._log_files.values():
            try: f.close()
            except: pass
        self._log_files.clear()
        logger.info(f"[GridWSEngine] Stopped")

    def get_current_orderbook(self, ticker: str) -> dict:
        """Return current orderbook snapshot for ticker"""
        t = ticker.upper()
        if t in self._orderbooks:
            return self._orderbooks[t].to_dict()
        return OrderbookState(ticker=t).to_dict()

    @property
    def is_running(self) -> bool:
        return self._running


# ── Global singleton engine ──────────────────────────────────

_engine: Optional[GridWSEngine] = None
_engine_lock = asyncio.Lock()


async def get_or_create_engine(ticker: str, env_dv: str = "real") -> GridWSEngine:
    """Get singleton engine, subscribe ticker if needed"""
    global _engine
    async with _engine_lock:
        if _engine is None or not _engine.is_running:
            _engine = GridWSEngine(env_dv)
            await _engine.start()
        # Subscribe this ticker
        await _engine.subscribe_ticker(ticker.upper())
    return _engine


async def stop_engine(ticker: str, env_dv: str = "real"):
    """Unsubscribe a ticker (don't stop the whole engine)"""
    global _engine
    if _engine and _engine.is_running:
        await _engine.unsubscribe_ticker(ticker.upper())


async def stop_all_engines():
    global _engine
    async with _engine_lock:
        if _engine:
            await _engine.stop()
            _engine = None
