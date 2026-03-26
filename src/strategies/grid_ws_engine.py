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
    """

    def __init__(self, ticker: str, env_dv: str = "real"):
        self.ticker = ticker.upper()
        self.env_dv = env_dv
        self.orderbook = OrderbookState(ticker=self.ticker)

        # Frontend WebSocket clients
        self._orderbook_clients: Set[asyncio.Queue] = set()
        self._event_clients: Set[asyncio.Queue] = set()

        # KIS WS state
        self._kis_ws = None
        self._kis_task: Optional[asyncio.Task] = None
        self._running = False
        self._data_map: Dict[str, dict] = {}

        # JSONL log
        self._log_dir = os.path.join(ROOT_DIR, "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        today = datetime.now(KST).strftime("%Y%m%d")
        self._log_path = os.path.join(self._log_dir, f"grid_ladder_{self.ticker}_{today}.jsonl")
        self._log_file = None

    # ── Logging ──────────────────────────────────────────────

    def _open_log(self):
        if self._log_file is None:
            self._log_file = open(self._log_path, "a", encoding="utf-8")

    def _write_log(self, event_type: str, data: dict):
        self._open_log()
        entry = {
            "ts": datetime.now(KST).isoformat(),
            "event": event_type,
            "data": data,
        }
        self._log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._log_file.flush()

    # ── Frontend client management ───────────────────────────

    def subscribe_orderbook(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._orderbook_clients.add(q)
        return q

    def unsubscribe_orderbook(self, q: asyncio.Queue):
        self._orderbook_clients.discard(q)

    def subscribe_events(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._event_clients.add(q)
        return q

    def unsubscribe_events(self, q: asyncio.Queue):
        self._event_clients.discard(q)

    async def _broadcast_orderbook(self, data: dict):
        dead = []
        for q in self._orderbook_clients:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                # Drop oldest, push new
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(data)
                except Exception:
                    dead.append(q)
        for q in dead:
            self._orderbook_clients.discard(q)

    async def broadcast_event(self, event: dict):
        """Public: grid ladder manager can push events (fill, order, cancel, error)"""
        dead = []
        for q in self._event_clients:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(event)
                except Exception:
                    dead.append(q)
        for q in dead:
            self._event_clients.discard(q)
        # Also log
        self._write_log(event.get("type", "event"), event)

    # ── Parse KIS WS messages ────────────────────────────────

    def _parse_orderbook_raw(self, fields: list):
        """
        Parse H0STASP0 raw fields directly (bypass pd column mapping).
        KIS real data has 62 fields:
          [0]=ticker, [1]=time, [2]=hour_cls
          [3..12] = ASKP1~10 (매도호가, 오름차순)
          [13..22] = BIDP1~10 (매수호가, 내림차순)
          [23..32] = ASKP_RSQN1~10 (매도잔량)
          [33..42] = BIDP_RSQN1~10 (매수잔량)
          [43] = TOTAL_ASKP_RSQN
          [44] = TOTAL_BIDP_RSQN
          ... (나머지 예상체결 등)
        """
        if len(fields) < 45:
            return

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

        self.orderbook.asks = asks
        self.orderbook.bids = bids
        self.orderbook.total_ask_qty = int(fields[43] or 0) if len(fields) > 43 else 0
        self.orderbook.total_bid_qty = int(fields[44] or 0) if len(fields) > 44 else 0
        self.orderbook.acml_vol = int(fields[53] or 0) if len(fields) > 53 else 0
        self.orderbook.time = formatted_time
        
        # 현재가: field[59] (마지막 체결가) or 매수1/매도1 중간값
        if len(fields) > 59 and fields[59]:
            try:
                self.orderbook.current_price = int(fields[59])
            except (ValueError, TypeError):
                pass
        
        # 전일대비: field[50]의 절대값이 현재가보다 크면 전일종가임
        # 실제 전일대비 = 현재가 - |field[50]|
        if len(fields) > 50 and fields[50]:
            try:
                raw_val = int(fields[50])
                if abs(raw_val) > 1000 and self.orderbook.current_price > 0:
                    # field[50]은 전일종가(음수 부호 포함)
                    prev_close = abs(raw_val)
                    self.orderbook.price_change = self.orderbook.current_price - prev_close
                else:
                    self.orderbook.price_change = raw_val
            except (ValueError, TypeError):
                pass

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

    async def _kis_connect(self):
        """Connect to KIS WebSocket, subscribe to orderbook + execution notices"""
        # Auth (sync calls — run in executor)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: ka.auth(svr="prod"))
        await loop.run_in_executor(None, lambda: ka.auth_ws(svr="prod"))
        
        env = ka.getTREnv()
        # approval_key is stored in ka._base_headers_ws
        approval_key = ka._base_headers_ws.get("approval_key", "")
        if not approval_key:
            logger.error("[GridWSEngine] Failed to get WS approval_key")
            return

        # Build subscription messages
        ob_tr_id = "H0STASP0"
        cn_tr_id = "H0STCNI0" if self.env_dv == "real" else "H0STCNI9"
        hts_id = env.my_htsid  # HTS ID for execution notice

        ob_msg = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": ob_tr_id,
                    "tr_key": self.ticker,
                }
            },
        }

        cn_msg = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": cn_tr_id,
                    "tr_key": hts_id,
                }
            },
        }

        # WS URL: ws://ops.koreainvestment.com:21000/ (path=/)
        ws_url = env.my_url_ws.rstrip("/") + "/"
        logger.info(f"[GridWSEngine] Connecting to {ws_url}")

        max_retries = 10
        retry = 0

        while self._running and retry < max_retries:
            try:
                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    self._kis_ws = ws
                    logger.info(f"[GridWSEngine] KIS WS connected for {self.ticker}")

                    # Subscribe orderbook
                    await ws.send(json.dumps(ob_msg))
                    logger.info(f"[GridWSEngine] Subscribed H0STASP0 for {self.ticker}")
                    await asyncio.sleep(0.5)

                    # Subscribe execution notice
                    await ws.send(json.dumps(cn_msg))
                    logger.info(f"[GridWSEngine] Subscribed {cn_tr_id} for {hts_id}")

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
                    # Use raw field parsing (bypass column mismatch)
                    raw_fields = data_str.split("^")
                    self._parse_orderbook_raw(raw_fields)
                    ob_data = self.orderbook.to_dict()
                    await self._broadcast_orderbook(ob_data)
                    self._write_log("orderbook", ob_data)
                elif tr_id in ("H0STCNI0", "H0STCNI9"):
                    event = self._parse_ccnl_notice(row)
                    if event:
                        await self.broadcast_event(event)

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
        logger.info(f"[GridWSEngine] Started for {self.ticker}")

    async def stop(self):
        """Stop KIS WS connection"""
        self._running = False
        if self._kis_ws:
            try:
                await self._kis_ws.close()
            except Exception:
                pass
        if self._kis_task and not self._kis_task.done():
            self._kis_task.cancel()
            try:
                await self._kis_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._log_file:
            self._log_file.close()
            self._log_file = None
        logger.info(f"[GridWSEngine] Stopped for {self.ticker}")

    def get_current_orderbook(self) -> dict:
        """Return current orderbook snapshot"""
        return self.orderbook.to_dict()

    @property
    def is_running(self) -> bool:
        return self._running


# ── Global engine registry ───────────────────────────────────

_engines: Dict[str, GridWSEngine] = {}
_engines_lock = asyncio.Lock()


async def get_or_create_engine(ticker: str, env_dv: str = "real") -> GridWSEngine:
    """Get existing engine or create a new one for the ticker"""
    key = f"{ticker.upper()}:{env_dv}"
    async with _engines_lock:
        if key not in _engines or not _engines[key].is_running:
            engine = GridWSEngine(ticker.upper(), env_dv)
            await engine.start()
            _engines[key] = engine
        return _engines[key]


async def stop_engine(ticker: str, env_dv: str = "real"):
    key = f"{ticker.upper()}:{env_dv}"
    async with _engines_lock:
        if key in _engines:
            await _engines[key].stop()
            del _engines[key]


async def stop_all_engines():
    async with _engines_lock:
        for engine in _engines.values():
            await engine.stop()
        _engines.clear()
