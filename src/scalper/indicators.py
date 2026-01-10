# -*- coding: utf-8 -*-
from typing import Tuple, Optional
import pandas as pd
import numpy as np


class TechnicalIndicators:
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 9) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return lower, sma, upper
    
    @staticmethod
    def calculate_all(
        df: pd.DataFrame,
        price_col: str = "last",
        rsi_period: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0
    ) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
        if df is None or len(df) < bb_period:
            return None, None
        
        prices = df[price_col]
        rsi = TechnicalIndicators.calculate_rsi(prices, rsi_period)
        lower, _, upper = TechnicalIndicators.calculate_bollinger_bands(
            prices, bb_period, bb_std
        )
        
        return rsi.iloc[-1], (lower.iloc[-1], upper.iloc[-1])
    
    @staticmethod
    def find_support_level(df: pd.DataFrame, price_col: str = "low", window: int = 60) -> Optional[float]:
        if df is None or len(df) < window:
            return None
        
        recent = df[price_col].tail(window)
        sorted_lows = recent.nsmallest(10)
        
        if len(sorted_lows) < 2:
            return None
        
        for i, low1 in enumerate(sorted_lows):
            for low2 in sorted_lows[i+1:]:
                if abs(low1 - low2) / low1 < 0.005:
                    return (low1 + low2) / 2
        
        return None
    
    @staticmethod
    def count_rsi_oversold_touches(
        df: pd.DataFrame,
        price_col: str = "last",
        rsi_period: int = 9,
        oversold_level: int = 30,
        window: int = 60,
        min_gap: int = 5
    ) -> int:
        if df is None or len(df) < window:
            return 0
        
        prices = df[price_col].tail(window)
        rsi = TechnicalIndicators.calculate_rsi(prices, rsi_period)
        
        touches = 0
        last_touch_idx = -min_gap
        
        for i, val in enumerate(rsi):
            if val <= oversold_level and (i - last_touch_idx) >= min_gap:
                touches += 1
                last_touch_idx = i
        
        return touches
    
    @staticmethod
    def estimate_price_for_target_rsi(
        df: pd.DataFrame,
        price_col: str = "last",
        rsi_period: int = 9,
        target_rsi: int = 30
    ) -> Optional[float]:
        if df is None or len(df) < rsi_period + 1:
            return None
        
        prices = df[price_col]
        delta = prices.diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        drop_idx = len(df) - rsi_period
        gain_old = gains.iloc[drop_idx]
        loss_old = losses.iloc[drop_idx]
        
        sum_gain = gains.tail(rsi_period).sum()
        sum_loss = losses.tail(rsi_period).sum()
        
        try:
            target_rs = target_rsi / (100 - target_rsi)
            curr_price = prices.iloc[-1]
            target_price = curr_price + (sum_loss - loss_old) - (sum_gain - gain_old) / target_rs
            return target_price
        except ZeroDivisionError:
            return None
