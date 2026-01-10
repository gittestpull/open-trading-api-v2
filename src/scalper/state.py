# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional
import json
import os
import numpy as np


@dataclass
class ScalperState:
    state: str = "SEARCHING"
    avg_buy_price: float = 0.0
    total_qty: int = 0
    current_step: int = 0
    buy_history: List[Tuple[float, int]] = field(default_factory=list)
    pending_sell: Optional[dict] = None
    daily_realized_profit: float = 0.0
    
    def reset(self):
        self.state = "SEARCHING"
        self.avg_buy_price = 0.0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []
        self.pending_sell = None
        self.daily_realized_profit = 0.0


class StateManager:
    
    def __init__(self, ticker: str, state_dir: str = "scalp_data"):
        self.ticker = ticker
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, f"state_{ticker}.json")
        self._state = ScalperState()
        self._ensure_dir()
    
    def _ensure_dir(self):
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
    
    @property
    def current_state(self) -> ScalperState:
        return self._state
    
    def load(self) -> ScalperState:
        if not os.path.exists(self.state_file):
            return self._state
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._state.state = data.get("state", "SEARCHING")
                self._state.avg_buy_price = float(data.get("avg_buy_price", 0))
                self._state.total_qty = int(data.get("total_qty", 0))
                self._state.current_step = int(data.get("current_step", 0))
                self._state.buy_history = [
                    (float(p), int(q)) for p, q in data.get("buy_history", [])
                ]
                self._state.pending_sell = data.get("pending_sell")
                self._state.daily_realized_profit = float(
                    data.get("daily_realized_profit", 0)
                )
        except (json.JSONDecodeError, IOError):
            pass
        
        return self._state
    
    def save(self):
        def serialize(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        data = {
            "state": self._state.state,
            "avg_buy_price": float(self._state.avg_buy_price),
            "total_qty": int(self._state.total_qty),
            "current_step": int(self._state.current_step),
            "buy_history": [
                (float(p), int(q)) for p, q in self._state.buy_history
            ],
            "pending_sell": self._state.pending_sell,
            "daily_realized_profit": float(self._state.daily_realized_profit),
        }
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, default=serialize)
    
    def clear(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        self._state.reset()
    
    def update_position(
        self, 
        price: float, 
        qty: int, 
        is_buy: bool = True
    ):
        if is_buy:
            total_cost = (self._state.avg_buy_price * self._state.total_qty) + (price * qty)
            self._state.total_qty += qty
            if self._state.total_qty > 0:
                self._state.avg_buy_price = total_cost / self._state.total_qty
            self._state.buy_history.append((price, qty))
            self._state.current_step = len(self._state.buy_history)
            self._state.state = "HOLDING"
        else:
            sell_value = price * qty
            cost_basis = self._state.avg_buy_price * qty
            profit = sell_value - cost_basis
            self._state.daily_realized_profit += profit
            self._state.total_qty -= qty
            
            if self._state.total_qty <= 0:
                self._state.reset()
        
        self.save()
