# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List


@dataclass
class StrategyConfig:
    rsi_period: int = 9
    rsi_buy_level: int = 30
    rsi_sell_level: int = 70
    bb_period: int = 20
    bb_std: float = 2.0
    target_profit: float = 0.005
    pyramiding_threshold: float = 0.01
    max_steps: int = 4
    weights: List[int] = field(default_factory=lambda: [1, 2, 4, 8])
    
    @property
    def sum_weights(self) -> int:
        return sum(self.weights)


@dataclass
class FeeConfig:
    domestic_buy_fee: float = 0.00015
    domestic_sell_fee: float = 0.00015
    domestic_sell_tax: float = 0.0017
    overseas_buy_fee: float = 0.0004
    overseas_sell_fee: float = 0.0004
    overseas_sell_tax: float = 0.0
    
    def get_domestic_friction(self) -> float:
        return self.domestic_buy_fee + self.domestic_sell_fee + self.domestic_sell_tax
    
    def get_overseas_friction(self) -> float:
        return self.overseas_buy_fee + self.overseas_sell_fee + self.overseas_sell_tax


@dataclass
class ScalperConfig:
    ticker: str
    budget: float
    live_mode: bool = False
    manual_buy_price: float = 0.0
    use_orderbook: bool = False
    use_momentum: bool = False
    
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    fees: FeeConfig = field(default_factory=FeeConfig)
    
    poll_interval: int = 30
    supply_check_interval: int = 600
    market_data_interval: int = 600
    unfilled_check_interval: int = 30
    price_info_interval: int = 300
    buy_cooldown_seconds: int = 180


NXT_PRE_START = "08:00"
NXT_PRE_END = "08:50"
NXT_POST_START = "15:40"
NXT_POST_END = "20:00"
KRX_START = "09:00"
KRX_END = "15:30"
