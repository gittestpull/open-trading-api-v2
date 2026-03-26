# -*- coding: utf-8 -*-
"""
Grid Ladder Manager (동적 그리드 계단식 매수 전략)
=================================================
회장님 요청: 1천만원 시드, 50만원 단위 분할 매수.
기준가 대비 -6호가에 매수 걸고, -7/-8호가에도 매수 대기.
-6호가 체결 시 → -7/-8 취소 → 새 기준가로 재배치.

KIS Open API v2 연동 (domestic_stock_functions 활용)
"""

import sys
import os
import time
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import threading

import pytz
import pandas as pd

KST = pytz.timezone('Asia/Seoul')

# Path setup
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'src', 'core'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'src', 'utils'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'examples_user'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'examples_user', 'domestic_stock'))

import kis_auth as ka
import domestic_stock_functions as ds
import domestic_stock_functions_ws as ds_ws

logger = logging.getLogger(__name__)


# ============================================================
# 호가 단위 테이블 (KRX 가격별 호가 단위)
# ============================================================
TICK_TABLE = [
    (2_000,      1),
    (5_000,      5),
    (20_000,    10),
    (50_000,    50),
    (200_000,  100),
    (500_000,  500),
    (float('inf'), 1000),
]


def get_tick_size(price: int) -> int:
    """주어진 가격에 해당하는 호가 단위를 반환"""
    for ceiling, tick in TICK_TABLE:
        if price < ceiling:
            return tick
    return 1000


def price_n_ticks_below(base_price: int, n_ticks: int) -> int:
    """base_price에서 n틱 아래 가격을 계산"""
    price = base_price
    for _ in range(n_ticks):
        tick = get_tick_size(price)
        price -= tick
        # 호가 단위 경계 넘어가면 새 tick 적용
        if price <= 0:
            price = tick
            break
    return price


# ============================================================
# Data Classes
# ============================================================
class OrderStatus(Enum):
    PENDING = "pending"       # 미체결
    EXECUTED = "executed"     # 체결
    CANCELLED = "cancelled"   # 취소됨
    FAILED = "failed"         # 주문 실패


@dataclass
class GridOrder:
    """개별 그리드 주문 정보"""
    price: int              # 주문가
    quantity: int           # 주문수량
    tick_level: int         # 기준가 대비 몇 틱 아래 (6, 7, 8)
    order_no: str = ""      # KIS 주문번호
    org_no: str = ""        # KRX전송주문조직번호
    status: OrderStatus = OrderStatus.PENDING
    timestamp: str = ""


import sqlite3


def _get_db_path():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    db_path = os.path.join(base, 'data', 'deep_dive.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


def _init_grid_table():
    """grid_ladder_instances 테이블 생성"""
    conn = sqlite3.connect(_get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grid_ladder_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            env_dv TEXT NOT NULL DEFAULT 'demo',
            total_budget INTEGER NOT NULL,
            order_amount INTEGER NOT NULL,
            entry_tick_levels TEXT NOT NULL,
            trigger_level INTEGER NOT NULL DEFAULT 6,
            poll_interval REAL NOT NULL DEFAULT 1.0,
            base_price INTEGER DEFAULT 0,
            total_invested INTEGER DEFAULT 0,
            current_round INTEGER DEFAULT 0,
            holdings TEXT DEFAULT '[]',
            trade_log TEXT DEFAULT '[]',
            last_error TEXT DEFAULT '',
            pending_order_details TEXT DEFAULT '[]',
            status TEXT DEFAULT 'stopped',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, env_dv)
        )
    """)
    # Migration: add pending_order_details column if missing
    try:
        conn.execute("ALTER TABLE grid_ladder_instances ADD COLUMN pending_order_details TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()


def save_grid_state(mgr: 'GridLadderManager'):
    """현재 상태를 DB에 저장"""
    _init_grid_table()
    conn = sqlite3.connect(_get_db_path())
    status = 'running' if not mgr._stop_requested else 'stopped'
    if mgr.paused:
        status = 'paused'
    
    # Build pending order details
    pending_details = []
    for ono, order in mgr.pending_orders.items():
        if order.status == OrderStatus.PENDING:
            pending_details.append({
                'order_no': order.order_no,
                'price': order.price,
                'quantity': order.quantity,
                'tick_level': order.tick_level,
            })
    
    conn.execute("""
        INSERT INTO grid_ladder_instances 
            (ticker, env_dv, total_budget, order_amount, entry_tick_levels, trigger_level, 
             poll_interval, base_price, total_invested, current_round, holdings, trade_log, 
             last_error, pending_order_details, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(ticker, env_dv) DO UPDATE SET
            base_price=excluded.base_price,
            total_invested=excluded.total_invested,
            current_round=excluded.current_round,
            holdings=excluded.holdings,
            trade_log=excluded.trade_log,
            last_error=excluded.last_error,
            pending_order_details=excluded.pending_order_details,
            status=excluded.status,
            updated_at=datetime('now')
    """, (
        mgr.config.stock_code,
        mgr.config.env_dv,
        mgr.config.total_budget,
        mgr.config.order_amount,
        json.dumps(mgr.config.entry_tick_levels),
        mgr.config.trigger_level,
        mgr.config.poll_interval,
        mgr.base_price,
        mgr.total_invested,
        mgr.current_round,
        json.dumps(list(mgr.all_holdings)),
        json.dumps(list(mgr.trade_log)),
        mgr.last_error,
        json.dumps(pending_details),
        status,
    ))
    # Ensure pending_order_details column exists (migration)
    try:
        conn.execute("ALTER TABLE grid_ladder_instances ADD COLUMN pending_order_details TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()


def load_all_grid_states() -> list:
    """DB에서 모든 grid ladder 상태 로드"""
    _init_grid_table()
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM grid_ladder_instances ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_grid_state(ticker: str, env_dv: str):
    """DB에서 grid ladder 상태 삭제"""
    conn = sqlite3.connect(_get_db_path())
    conn.execute("DELETE FROM grid_ladder_instances WHERE ticker=? AND env_dv=?", (ticker, env_dv))
    conn.commit()
    conn.close()


@dataclass
class GridLadderConfig:
    """전략 설정"""
    stock_code: str             # 종목코드 (6자리)
    total_budget: int           # 총 투자금 (기본 10,000,000)
    order_amount: int           # 1회 주문금액 (기본 500,000)
    entry_tick_levels: List[int] = field(default_factory=lambda: [6, 7, 8])  # 진입 호가 레벨
    trigger_level: int = 6      # 이 레벨 체결 시 나머지 취소
    env_dv: str = "real"        # real/demo
    poll_interval: float = 1.0  # 체결 확인 주기(초)
    max_rounds: int = 20        # 최대 라운드 수 (50만 × 20 = 1천만)


# ============================================================
# Main Strategy Class
# ============================================================
class GridLadderManager:
    """
    동적 그리드 계단식 매수 전략 매니저
    
    핵심 로직:
    1. 현재가 기준으로 첫 50만원 매수
    2. 체결가 기준 -6, -7, -8 호가에 50만원씩 지정가 매수 주문
    3. -6호가 체결 시 → -7, -8 즉시 취소
    4. -6호가 체결가를 새 기준가로 설정
    5. 새 기준가 기준 -6, -7, -8 호가에 재배치
    6. 총 투자금 소진될 때까지 반복
    """

    def __init__(self, config: GridLadderConfig):
        self.config = config
        self.is_demo = (config.env_dv == "demo")
        
        # KIS 인증 — 항상 실전(prod)으로 인증 (시세 조회용)
        # 모의투자도 실시간 시세는 KIS에서 가져옴
        ka.auth(svr="prod")
        self.trenv = ka.getTREnv()
        
        # 모의투자 내부 시뮬레이터
        if self.is_demo:
            self._sim_order_seq = 0
            self._sim_capital = float(config.total_budget)
            self._sim_fee_rate = 0.00015  # 수수료율
        
        # State
        self.total_invested: int = 0
        self.current_round: int = 0
        self.base_price: int = 0  # 현재 기준가
        self.executed_orders: List[GridOrder] = []  # 체결된 주문 기록
        self.pending_orders: Dict[str, GridOrder] = {}  # {주문번호: GridOrder}
        self.all_holdings: List[Tuple[int, int]] = []  # [(가격, 수량), ...]
        
        # Error / pause tracking
        self.last_error: str = ""
        self.paused: bool = False          # True = waiting for user action
        self.pause_reason: str = ""
        self._resume_event = threading.Event()
        self._skip_requested: bool = False
        self._stop_requested: bool = False
        
        # Retry config
        self.max_retries: int = 3
        self.retry_delay: float = 2.0  # seconds
        
        # Log (bounded like ProcessManager's deque)
        self.trade_log: deque = deque(maxlen=500)

    # --------------------------------------------------------
    # KIS API Wrappers
    # --------------------------------------------------------
    def _get_current_price(self) -> int:
        """현재가 조회 (FHKST01010100)"""
        df = ds.inquire_price(
            env_dv=self.config.env_dv,
            fid_cond_mrkt_div_code="J",
            fid_input_iscd=self.config.stock_code
        )
        if df.empty:
            raise RuntimeError(f"현재가 조회 실패: {self.config.stock_code}")
        
        price = int(df.iloc[0].get('stck_prpr', 0))
        logger.info(f"[현재가] {self.config.stock_code}: {price:,}원")
        return price

    def _get_orderbook(self) -> pd.DataFrame:
        """호가 조회 (FHKST01010200)"""
        df1, df2 = ds.inquire_asking_price_exp_ccn(
            env_dv=self.config.env_dv,
            fid_cond_mrkt_div_code="J",
            fid_input_iscd=self.config.stock_code
        )
        return df1

    def _place_buy_order(self, price: int, quantity: int) -> Tuple[str, str]:
        """
        지정가 매수 주문
        Demo: 내부 시뮬레이션 / Live: KIS API
        Returns: (주문번호, KRX전송주문조직번호)
        """
        if self.is_demo:
            return self._sim_place_order(price, quantity)
        
        ka.smart_sleep()
        
        df = ds.order_cash(
            env_dv="real",
            ord_dv="buy",
            cano=self.trenv.my_acct,
            acnt_prdt_cd=self.trenv.my_prod,
            pdno=self.config.stock_code,
            ord_dvsn="00",  # 00: 지정가
            ord_qty=str(quantity),
            ord_unpr=str(price),
            excg_id_dvsn_cd="KRX"
        )
        
        if df.empty:
            logger.error(f"[주문실패] {price:,}원 × {quantity}주")
            return "", ""
        
        order_no = str(df.iloc[0].get('ODNO', ''))
        org_no = str(df.iloc[0].get('KRX_FWDG_ORD_ORGNO', ''))
        
        logger.info(f"[매수주문] {price:,}원 × {quantity}주 → 주문번호: {order_no}")
        return order_no, org_no

    def _cancel_order(self, order: GridOrder) -> bool:
        """주문 취소"""
        if not order.order_no:
            return False
        
        if self.is_demo:
            return self._sim_cancel_order(order)
        
        ka.smart_sleep()
        
        df = ds.order_rvsecncl(
            env_dv="real",
            cano=self.trenv.my_acct,
            acnt_prdt_cd=self.trenv.my_prod,
            krx_fwdg_ord_orgno=order.org_no,
            orgn_odno=order.order_no,
            ord_dvsn="00",
            rvse_cncl_dvsn_cd="02",  # 02: 취소
            ord_qty=str(order.quantity),
            ord_unpr="0",
            qty_all_ord_yn="Y",  # 전량 취소
            excg_id_dvsn_cd="KRX"
        )
        
        if not df.empty:
            order.status = OrderStatus.CANCELLED
            logger.info(f"[취소완료] 주문번호 {order.order_no} ({order.price:,}원 × {order.quantity}주)")
            return True
        else:
            logger.error(f"[취소실패] 주문번호 {order.order_no}")
            return False

    def _check_execution(self, order_no: str) -> Tuple[bool, int, int]:
        """
        체결 여부 확인
        Demo: 현재가 vs 주문가 비교 / Live: KIS API
        Returns: (체결여부, 체결수량, 체결가)
        """
        if self.is_demo:
            return self._sim_check_execution(order_no)
        
        try:
            today = datetime.now(KST).strftime('%Y%m%d')
            df1, df2 = ds.inquire_daily_ccld(
                env_dv=self.config.env_dv,
                pd_dv="inner",          # 3개월 이내
                cano=self.trenv.my_acct,
                acnt_prdt_cd=self.trenv.my_prod,
                inqr_strt_dt=today,
                inqr_end_dt=today,
                sll_buy_dvsn_cd="02",   # 02: 매수
                ccld_dvsn="01",         # 01: 체결
                inqr_dvsn="00",         # 00: 역순
                inqr_dvsn_3="00",       # 00: 전체
                pdno=self.config.stock_code,
                odno=order_no,
            )
            
            if not df1.empty:
                for _, row in df1.iterrows():
                    row_odno = str(row.get('odno', '')).strip()
                    if row_odno == order_no:
                        tot_ccld_qty = int(row.get('tot_ccld_qty', 0))
                        avg_prvs = int(float(row.get('avg_prvs', 0)))
                        if tot_ccld_qty > 0:
                            return True, tot_ccld_qty, avg_prvs
            
            return False, 0, 0
            
        except Exception as e:
            logger.warning(f"체결 조회 에러: {e}")
            return False, 0, 0

    # --------------------------------------------------------
    # Core Strategy Logic
    # --------------------------------------------------------
    def _calculate_quantity(self, price: int) -> int:
        """주어진 가격에서 order_amount로 살 수 있는 수량 계산"""
        if price <= 0:
            return 0
        qty = self.config.order_amount // price
        return max(qty, 1)  # 최소 1주

    def _place_grid_orders(self) -> List[GridOrder]:
        """기준가 대비 -6, -7, -8 호가에 주문 배치"""
        orders = []
        
        for level in self.config.entry_tick_levels:
            target_price = price_n_ticks_below(self.base_price, level)
            quantity = self._calculate_quantity(target_price)
            
            # 투자금 한도 체크
            order_cost = target_price * quantity
            if self.total_invested + order_cost > self.config.total_budget:
                remaining = self.config.total_budget - self.total_invested
                quantity = remaining // target_price
                if quantity <= 0:
                    logger.info(f"[한도도달] 투자금 소진. Level {level} 주문 스킵.")
                    continue
            
            order_no, org_no = self._place_buy_order(target_price, quantity)
            
            grid_order = GridOrder(
                price=target_price,
                quantity=quantity,
                tick_level=level,
                order_no=order_no,
                org_no=org_no,
                status=OrderStatus.PENDING if order_no else OrderStatus.FAILED,
                timestamp=datetime.now(KST).strftime('%H:%M:%S')
            )
            
            if order_no:
                self.pending_orders[order_no] = grid_order
            orders.append(grid_order)
        
        return orders

    def _cancel_non_triggered_orders(self, triggered_order_no: str):
        """트리거된 주문 외 나머지 미체결 주문 모두 취소"""
        to_cancel = [
            (ono, order) for ono, order in self.pending_orders.items()
            if ono != triggered_order_no and order.status == OrderStatus.PENDING
        ]
        
        for ono, order in to_cancel:
            self._cancel_order(order)
            del self.pending_orders[ono]
        
        logger.info(f"[일괄취소] {len(to_cancel)}건 취소 완료")

    def _monitor_and_wait(self) -> Optional[GridOrder]:
        """
        미체결 주문 감시: trigger_level (6호가) 주문이 체결될 때까지 폴링
        Returns: 체결된 GridOrder 또는 None (타임아웃/에러)
        """
        trigger_orders = [
            (ono, order) for ono, order in self.pending_orders.items()
            if order.tick_level == self.config.trigger_level and order.status == OrderStatus.PENDING
        ]
        
        if not trigger_orders:
            logger.warning("[감시] 트리거 레벨 주문이 없습니다.")
            return None
        
        logger.info(f"[감시시작] {len(self.pending_orders)}건 미체결 주문 모니터링 중...")
        
        max_polls = 3600  # 최대 1시간 (1초 간격)
        
        for poll_count in range(max_polls):
            time.sleep(self.config.poll_interval)
            
            # 장 종료 체크 (15:30 이후)
            now = datetime.now(KST)
            if now.hour >= 15 and now.minute >= 30:
                logger.info("[장마감] 15:30 이후 — 감시 중단")
                return None
            
            # 모든 pending 주문의 체결 여부 확인
            for ono, order in list(self.pending_orders.items()):
                if order.status != OrderStatus.PENDING:
                    continue
                
                is_exec, exec_qty, exec_price = self._check_execution(ono)
                
                if is_exec:
                    order.status = OrderStatus.EXECUTED
                    logger.info(
                        f"[체결!] Level-{order.tick_level} | "
                        f"{exec_price:,}원 × {exec_qty}주 | "
                        f"주문번호: {ono}"
                    )
                    
                    # 체결 기록
                    self.executed_orders.append(order)
                    self.all_holdings.append((exec_price, exec_qty))
                    self.total_invested += exec_price * exec_qty
                    
                    # 로그 기록
                    self.trade_log.append({
                        'round': self.current_round,
                        'time': datetime.now(KST).strftime('%H:%M:%S'),
                        'action': 'EXECUTED',
                        'level': order.tick_level,
                        'price': exec_price,
                        'quantity': exec_qty,
                        'total_invested': self.total_invested,
                        'order_no': ono
                    })
                    
                    # trigger_level 체결이면 나머지 취소 후 리턴
                    if order.tick_level == self.config.trigger_level:
                        self._cancel_non_triggered_orders(ono)
                        del self.pending_orders[ono]
                        return order
                    
                    # 하위 레벨(7, 8) 체결이면 — 이건 급락 상황
                    # 모든 미체결 취소하고 이 가격을 새 기준가로 사용
                    if order.tick_level > self.config.trigger_level:
                        logger.warning(
                            f"[급락감지] Level-{order.tick_level} 먼저 체결! "
                            f"Panic 모드 — 전체 취소 후 재배치"
                        )
                        self._cancel_non_triggered_orders(ono)
                        del self.pending_orders[ono]
                        return order
            
            # 10분마다 상태 로그
            if poll_count > 0 and poll_count % 600 == 0:
                logger.info(f"[대기중] {poll_count}초 경과, 미체결 {len(self.pending_orders)}건")
        
        logger.warning("[타임아웃] 1시간 경과 — 감시 종료")
        return None

    # --------------------------------------------------------
    # Main Entry Point
    # --------------------------------------------------------
    def run(self):
        """전략 실행 (메인 루프)"""
        logger.info("=" * 60)
        logger.info(f"Grid Ladder Manager 시작")
        logger.info(f"  종목: {self.config.stock_code}")
        logger.info(f"  총 투자금: {self.config.total_budget:,}원")
        logger.info(f"  1회 주문: {self.config.order_amount:,}원")
        logger.info(f"  진입 레벨: {self.config.entry_tick_levels}")
        logger.info(f"  환경: {self.config.env_dv}")
        logger.info("=" * 60)
        
        # Step 1: 초기 매수 (현재가로 50만원어치)
        while not self._stop_requested:
            try:
                current_price = self._get_current_price()
                break
            except Exception as e:
                self._pause_for_user(f"현재가 조회 실패: {e}")
                if self._stop_requested:
                    return
                if self._skip_requested:
                    return
                continue  # resume → retry
        
        if self._stop_requested:
            return
        
        init_qty = self._calculate_quantity(current_price)
        logger.info(f"[초기매수] {current_price:,}원 × {init_qty}주 (약 {current_price * init_qty:,}원)")
        
        order_no, org_no = self._place_buy_order_with_retry(current_price, init_qty)
        if not order_no:
            if self._stop_requested:
                return
            # skip requested — 초기매수 없이 현재가를 기준가로 사용
            logger.info(f"[초기매수 스킵] 현재가 {current_price:,}원을 기준가로 설정")
            self.base_price = current_price
        
        # 초기 매수는 시장가에 가까우므로 곧 체결된다고 가정, 확인
        time.sleep(2)
        is_exec, exec_qty, exec_price = self._check_execution(order_no)
        
        if is_exec:
            self.base_price = exec_price
            self.total_invested += exec_price * exec_qty
            self.all_holdings.append((exec_price, exec_qty))
            logger.info(f"[초기매수 체결] {exec_price:,}원 × {exec_qty}주")
        else:
            # 아직 미체결이면 주문가를 기준가로 사용
            self.base_price = current_price
            logger.info(f"[초기매수 미체결] 주문가 {current_price:,}원을 기준가로 사용")
        
        self.current_round = 1
        
        # 초기 상태 DB 저장
        try:
            save_grid_state(self)
        except Exception as e:
            logger.warning(f"[DB 저장 실패] {e}")
        
        self.trade_log.append({
            'round': 0,
            'time': datetime.now(KST).strftime('%H:%M:%S'),
            'action': 'INITIAL_BUY',
            'level': 0,
            'price': self.base_price,
            'quantity': init_qty,
            'total_invested': self.total_invested,
            'order_no': order_no
        })
        
        # Step 2: 반복 루프
        while (self.total_invested < self.config.total_budget 
               and self.current_round <= self.config.max_rounds):
            
            logger.info(f"\n{'─' * 40}")
            logger.info(f"[Round {self.current_round}] 기준가: {self.base_price:,}원 | 투자금: {self.total_invested:,}/{self.config.total_budget:,}원")
            logger.info(f"{'─' * 40}")
            
            if self._stop_requested:
                break
            
            # 2a. 그리드 주문 배치 (-6, -7, -8 호가)
            grid_orders = self._place_grid_orders()
            if not grid_orders or all(o.status == OrderStatus.FAILED for o in grid_orders):
                self._pause_for_user("그리드 주문 배치 실패 — 주문가능금액/계좌 확인 후 [Retry] 또는 [Stop]")
                if self._stop_requested:
                    break
                if self._skip_requested:
                    self.current_round += 1
                    continue
                # resume → retry this round
                continue
            
            for o in grid_orders:
                logger.info(
                    f"  Level-{o.tick_level}: {o.price:,}원 × {o.quantity}주 "
                    f"({o.status.value}) [#{o.order_no}]"
                )
            
            # 주문 배치 후 DB 저장 (pending 포함)
            try:
                save_grid_state(self)
            except Exception as e:
                logger.warning(f"[DB 저장 실패] {e}")
            
            # 2b. 체결 대기
            executed = self._monitor_and_wait()
            
            if executed is None:
                logger.info("[대기종료] 체결 없음 — 전략 종료")
                # 남은 미체결 주문 전부 취소
                for ono, order in list(self.pending_orders.items()):
                    self._cancel_order(order)
                self.pending_orders.clear()
                break
            
            # 2c. 새 기준가 설정
            self.base_price = executed.price
            self.current_round += 1
            
            logger.info(f"[기준가 갱신] {self.base_price:,}원 → 다음 라운드")
            
            # Save state to DB after each round
            try:
                save_grid_state(self)
            except Exception as e:
                logger.warning(f"[DB 저장 실패] {e}")
        
        # Save final state
        try:
            save_grid_state(self)
        except Exception as e:
            logger.warning(f"[DB 저장 실패] {e}")
        
        # Step 3: 결과 요약
        self._print_summary()

    def _print_summary(self):
        """전략 실행 결과 요약"""
        logger.info("\n" + "=" * 60)
        logger.info("Grid Ladder Manager 실행 결과")
        logger.info("=" * 60)
        logger.info(f"  총 라운드: {self.current_round}")
        logger.info(f"  총 투자금: {self.total_invested:,}원")
        logger.info(f"  총 체결 건수: {len(self.executed_orders)}건")
        
        if self.all_holdings:
            total_qty = sum(q for _, q in self.all_holdings)
            total_cost = sum(p * q for p, q in self.all_holdings)
            avg_price = total_cost / total_qty if total_qty > 0 else 0
            
            logger.info(f"  총 보유수량: {total_qty}주")
            logger.info(f"  평균단가: {avg_price:,.0f}원")
            
            logger.info("\n  [체결 내역]")
            for i, (p, q) in enumerate(self.all_holdings, 1):
                logger.info(f"    {i}. {p:,}원 × {q}주 = {p * q:,}원")
        
        logger.info("=" * 60)
        
        # JSON 로그 저장
        log_dir = os.path.join(ROOT_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, 
            f"grid_ladder_{self.config.stock_code}_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'config': {
                    'stock_code': self.config.stock_code,
                    'total_budget': self.config.total_budget,
                    'order_amount': self.config.order_amount,
                    'entry_tick_levels': self.config.entry_tick_levels,
                    'env_dv': self.config.env_dv,
                },
                'summary': {
                    'total_rounds': self.current_round,
                    'total_invested': self.total_invested,
                    'total_executions': len(self.executed_orders),
                    'holdings': self.all_holdings,
                    'avg_price': sum(p * q for p, q in self.all_holdings) / sum(q for _, q in self.all_holdings) if self.all_holdings else 0,
                },
                'trade_log': list(self.trade_log),
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  로그 저장: {log_file}")
    
    # ────────────────────────────────────────────
    # Demo Simulation Methods (내부 DB 시뮬레이션)
    # ────────────────────────────────────────────
    def _sim_place_order(self, price: int, quantity: int) -> Tuple[str, str]:
        """모의: 주문 즉시 접수, 잔고 체크"""
        cost = price * quantity
        fee = int(cost * self._sim_fee_rate)
        required = cost + fee
        
        if required > self._sim_capital:
            # 자금 부족 시 수량 조정
            max_qty = int((self._sim_capital * 0.99) / (price * (1 + self._sim_fee_rate)))
            if max_qty <= 0:
                logger.error(f"[SIM 주문실패] 잔고 부족 (필요: {required:,}, 보유: {self._sim_capital:,.0f})")
                return "", ""
            quantity = max_qty
        
        self._sim_order_seq += 1
        order_no = f"SIM{self._sim_order_seq:06d}"
        
        # 모의 주문은 접수만, 체결은 _sim_check_execution에서 처리
        logger.info(f"[SIM 매수주문] {price:,}원 × {quantity}주 → {order_no}")
        return order_no, f"SIM_ORG_{self._sim_order_seq}"

    def _sim_cancel_order(self, order: GridOrder) -> bool:
        """모의: 즉시 취소"""
        order.status = OrderStatus.CANCELLED
        logger.info(f"[SIM 취소] {order.order_no} ({order.price:,}원 × {order.quantity}주)")
        return True

    def _sim_check_execution(self, order_no: str) -> Tuple[bool, int, int]:
        """
        모의: KIS 실시간 시세로 체결 판정
        현재가가 주문가 이하이면 체결 처리
        """
        # pending_orders에서 해당 주문 찾기
        order = self.pending_orders.get(order_no)
        if not order:
            return False, 0, 0
        
        try:
            current_price = self._get_current_price()
        except Exception:
            return False, 0, 0
        
        # 매수 지정가: 현재가가 주문가 이하이면 체결
        if current_price <= order.price:
            # 체결 처리: 자본금 차감
            cost = order.price * order.quantity
            fee = int(cost * self._sim_fee_rate)
            self._sim_capital -= (cost + fee)
            
            logger.info(
                f"[SIM 체결] {order.order_no} | {order.price:,}원 × {order.quantity}주 "
                f"(수수료: {fee:,}원, 잔여자금: {self._sim_capital:,.0f}원)"
            )
            return True, order.quantity, order.price
        
        return False, 0, 0

    def _pause_for_user(self, reason: str):
        """에러 시 멈추고 사용자 액션 대기"""
        self.paused = True
        self.pause_reason = reason
        self.last_error = reason
        logger.warning(f"[PAUSED] {reason} — 사용자 액션 대기 (retry/skip/stop)")
        self._resume_event.clear()
        self._resume_event.wait()  # blocks until resume/skip/stop
        self.paused = False
        self.pause_reason = ""

    def resume(self):
        """재시도 — 현재 단계를 다시 실행"""
        self._skip_requested = False
        self.last_error = ""
        self._resume_event.set()
        logger.info("[RESUMED] 재시도")

    def skip(self):
        """건너뛰기 — 현재 단계를 스킵하고 다음으로"""
        self._skip_requested = True
        self.last_error = ""
        self._resume_event.set()
        logger.info("[SKIP] 현재 단계 건너뛰기")

    def request_stop(self):
        """사용자 정지 요청"""
        self._stop_requested = True
        self._resume_event.set()  # pause 풀기
        logger.info("[STOP REQUESTED]")

    def _place_buy_order_with_retry(self, price: int, quantity: int) -> Tuple[str, str]:
        """재시도 로직 포함 매수 주문"""
        for attempt in range(self.max_retries):
            if self._stop_requested:
                return "", ""
            
            order_no, org_no = self._place_buy_order(price, quantity)
            if order_no:
                return order_no, org_no
            
            if attempt < self.max_retries - 1:
                logger.warning(f"[주문재시도] {attempt + 1}/{self.max_retries} 실패, {self.retry_delay}초 후 재시도")
                time.sleep(self.retry_delay)
        
        # 모든 재시도 실패 → pause
        self._pause_for_user(
            f"주문 실패 ({price:,}원 × {quantity}주) — "
            f"주문가능금액/계좌 확인 후 [Retry] 또는 [Skip]"
        )
        
        if self._stop_requested:
            return "", ""
        if self._skip_requested:
            return "", ""  # skip this order
        
        # resume = retry one more time
        return self._place_buy_order(price, quantity)

    def get_status(self) -> dict:
        """현재 상태 조회 (외부에서 호출용)"""
        pending_details = []
        for ono, order in self.pending_orders.items():
            if order.status == OrderStatus.PENDING:
                pending_details.append({
                    'order_no': order.order_no,
                    'price': order.price,
                    'quantity': order.quantity,
                    'tick_level': order.tick_level,
                })
        
        return {
            'round': self.current_round,
            'base_price': self.base_price,
            'total_invested': self.total_invested,
            'budget_remaining': self.config.total_budget - self.total_invested,
            'pending_orders': len(self.pending_orders),
            'executed_orders': len(self.executed_orders),
            'holdings': list(self.all_holdings),
            'last_error': self.last_error,
            'paused': self.paused,
            'pause_reason': self.pause_reason,
            'env_dv': self.config.env_dv,
            'pending_order_details': pending_details,
        }


# ============================================================
# CLI Entry Point
# ============================================================
def main():
    """커맨드라인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Grid Ladder Manager - 동적 그리드 계단식 매수')
    parser.add_argument('--stock', '-s', required=True, help='종목코드 (예: 014940)')
    parser.add_argument('--budget', '-b', type=int, default=10_000_000, help='총 투자금 (기본: 10,000,000)')
    parser.add_argument('--amount', '-a', type=int, default=500_000, help='1회 주문금액 (기본: 500,000)')
    parser.add_argument('--levels', '-l', nargs='+', type=int, default=[6, 7, 8], help='진입 호가 레벨 (기본: 6 7 8)')
    parser.add_argument('--trigger', '-t', type=int, default=6, help='트리거 레벨 (기본: 6)')
    parser.add_argument('--env', '-e', choices=['real', 'demo'], default='real', help='실전/모의 (기본: real)')
    parser.add_argument('--poll', '-p', type=float, default=1.0, help='폴링 주기(초) (기본: 1.0)')
    
    args = parser.parse_args()
    
    # KIS 인증
    svr = "prod" if args.env == "real" else "vps"
    ka.auth(svr=svr)
    
    config = GridLadderConfig(
        stock_code=args.stock,
        total_budget=args.budget,
        order_amount=args.amount,
        entry_tick_levels=args.levels,
        trigger_level=args.trigger,
        env_dv=args.env,
        poll_interval=args.poll,
    )
    
    manager = GridLadderManager(config)
    manager.run()


if __name__ == '__main__':
    main()
