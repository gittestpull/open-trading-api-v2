# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from datetime import datetime
import time
import logging
import pandas as pd

from .config import ScalperConfig
from .indicators import TechnicalIndicators
from .state import StateManager


logger = logging.getLogger(__name__)


class BaseScalper(ABC):
    
    def __init__(self, config: ScalperConfig):
        self.config = config
        self.ticker = config.ticker.upper()
        self.state_manager = StateManager(self.ticker)
        self.state_manager.load()
        
        self.cached_balance: Tuple[float, float, float, float] = (0, 0, 0, 0)
        self.last_buy_time: float = 0
        self.consecutive_errors: int = 0
        self.max_allowed_errors: int = 3
        
        self._initialize_api()
    
    @abstractmethod
    def _initialize_api(self):
        pass
    
    @abstractmethod
    def get_minute_chart(self) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_current_price(self) -> float:
        pass
    
    @abstractmethod
    def get_balance(self) -> Tuple[float, float, float, float]:
        pass
    
    @abstractmethod
    def place_order(self, side: str, qty: int, price: float) -> bool:
        pass
    
    @abstractmethod
    def get_orderbook(self) -> Tuple[int, int, str]:
        pass
    
    @abstractmethod
    def check_market_hours(self) -> bool:
        pass
    
    @property
    def state(self) -> str:
        return self.state_manager.current_state.state
    
    @state.setter
    def state(self, value: str):
        self.state_manager.current_state.state = value
    
    @property
    def avg_buy_price(self) -> float:
        return self.state_manager.current_state.avg_buy_price
    
    @property
    def total_qty(self) -> int:
        return self.state_manager.current_state.total_qty
    
    @property
    def current_step(self) -> int:
        return self.state_manager.current_state.current_step
    
    @property
    def buy_history(self):
        return self.state_manager.current_state.buy_history
    
    def calculate_indicators(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
        return TechnicalIndicators.calculate_all(
            df,
            price_col="last",
            rsi_period=self.config.strategy.rsi_period,
            bb_period=self.config.strategy.bb_period,
            bb_std=self.config.strategy.bb_std
        )
    
    def calculate_step_budget(self, step: int) -> float:
        if step >= len(self.config.strategy.weights):
            return 0
        weight = self.config.strategy.weights[step]
        return self.config.budget * (weight / self.config.strategy.sum_weights)
    
    def should_buy(
        self,
        current_price: float,
        rsi: float,
        bb_lower: float,
        candle_low: float
    ) -> Tuple[bool, str]:
        reasons = []
        
        rsi_hit = rsi <= self.config.strategy.rsi_buy_level
        if rsi_hit:
            reasons.append(f"RSI({rsi:.1f})")
        
        bb_hit = current_price <= bb_lower or candle_low <= bb_lower
        if bb_hit:
            reasons.append(f"BB({bb_lower:.2f})")
        
        manual_price = self.config.manual_buy_price
        price_hit = manual_price > 0 and (current_price <= manual_price or candle_low <= manual_price)
        if price_hit:
            reasons.append(f"Price({manual_price:,.0f})")
        
        should = rsi_hit or bb_hit or price_hit
        return should, " | ".join(reasons)
    
    def should_pyramid(self, current_price: float, rsi: float) -> bool:
        if self.current_step >= self.config.strategy.max_steps:
            return False
        
        now = time.time()
        if now - self.last_buy_time < self.config.buy_cooldown_seconds:
            return False
        
        threshold = self.avg_buy_price * (1 - self.config.strategy.pyramiding_threshold)
        price_drop = current_price <= threshold
        
        if self.current_step < 2:
            rsi_low = rsi <= 25
            return price_drop or rsi_low
        else:
            rsi_low = rsi <= 25
            return price_drop and rsi_low
    
    def should_sell(
        self,
        current_price: float,
        rsi: float,
        bb_upper: float
    ) -> Tuple[bool, str]:
        profit_rate = (current_price - self.avg_buy_price) / self.avg_buy_price
        net_profit = profit_rate - self._get_friction()
        
        if net_profit >= self.config.strategy.target_profit:
            return True, f"TARGET({net_profit:.2%})"
        
        bb_hit = current_price >= bb_upper
        min_profit_for_bb = self.config.strategy.target_profit
        if bb_hit and net_profit >= min_profit_for_bb:
            return True, f"BB_UPPER({net_profit:.2%})"
        
        return False, ""
    
    @abstractmethod
    def _get_friction(self) -> float:
        pass
    
    def execute_buy(self, price: float, step: int) -> bool:
        budget = self.calculate_step_budget(step)
        qty = int(budget / price)
        
        if qty <= 0 and self.config.budget >= price:
            qty = 1
        
        if qty <= 0:
            return False
        
        if self.place_order("buy", qty, price):
            self.state_manager.update_position(price, qty, is_buy=True)
            self.last_buy_time = time.time()
            self.consecutive_errors = 0
            return True
        
        self.consecutive_errors += 1
        return False
    
    def execute_sell(self, price: float) -> bool:
        qty = self.total_qty
        if qty <= 0:
            return False
        
        if self.place_order("sell", qty, price):
            self.state_manager.update_position(price, qty, is_buy=False)
            self.consecutive_errors = 0
            return True
        
        self.consecutive_errors += 1
        return False
    
    def format_status_log(
        self,
        current_price: float,
        rsi: float,
        bb: Tuple[float, float],
        cash: float,
        asset: float
    ) -> str:
        lower_bb, upper_bb = bb
        
        parts = [
            f"Price: {current_price:.2f}",
            f"RSI: {rsi:.1f}",
            f"BB: [{lower_bb:.2f}, {upper_bb:.2f}]",
        ]
        
        if self.state == "HOLDING":
            profit_rate = (current_price - self.avg_buy_price) / self.avg_buy_price
            net_profit = profit_rate - self._get_friction()
            pnl = (current_price - self.avg_buy_price) * self.total_qty
            parts.append(f"Profit: {profit_rate:.2%} (Net: {net_profit:.2%})")
            parts.append(f"PNL: {pnl:,.0f}")
        
        parts.append(f"Cash: {cash:,.0f}")
        parts.append(f"Asset: {asset:,.0f}")
        
        if self.buy_history:
            history_str = ", ".join([
                f"B{i+1}:{p:.0f}({q})" 
                for i, (p, q) in enumerate(self.buy_history)
            ])
            parts.append(history_str)
        
        parts.append(f"State: {self.state}")
        
        return " | ".join(parts)
    
    def run(self):
        logger.info(
            f"Starting Scalper | Ticker: {self.ticker} | "
            f"Budget: {self.config.budget:,.0f} | "
            f"Target: {self.config.strategy.target_profit:.2%}"
        )
        
        while True:
            try:
                if not self.check_market_hours():
                    logger.info("Market closed. Stopping...")
                    break
                
                if self.consecutive_errors >= self.max_allowed_errors:
                    logger.error("Too many consecutive errors. Stopping...")
                    break
                
                df = self.get_minute_chart()
                if df is None or df.empty:
                    time.sleep(10)
                    continue
                
                rsi, bb = self.calculate_indicators(df)
                if rsi is None or bb is None:
                    time.sleep(10)
                    continue
                
                current_price = df["last"].iloc[-1]
                candle_low = df["low"].iloc[-1] if "low" in df.columns else current_price
                lower_bb, upper_bb = bb
                
                cash, asset, _, _ = self.get_balance()
                
                logger.info(self.format_status_log(current_price, rsi, bb, cash, asset))
                
                if self.state == "SEARCHING":
                    should, reason = self.should_buy(current_price, rsi, lower_bb, candle_low)
                    if should:
                        logger.info(f"BUY SIGNAL: {reason}")
                        self.execute_buy(current_price, step=0)
                
                elif self.state == "HOLDING":
                    should, reason = self.should_sell(current_price, rsi, upper_bb)
                    if should:
                        logger.info(f"SELL SIGNAL: {reason}")
                        self.execute_sell(current_price)
                    elif self.should_pyramid(current_price, rsi):
                        logger.info(f"PYRAMID SIGNAL: Step {self.current_step + 1}")
                        self.execute_buy(current_price, step=self.current_step)
                
                time.sleep(self.config.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user. Saving state...")
                self.state_manager.save()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.consecutive_errors += 1
                time.sleep(10)
