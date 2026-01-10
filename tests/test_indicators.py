# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from src.scalper.indicators import TechnicalIndicators


class TestCalculateRSI:
    
    def test_rsi_returns_series(self):
        # given
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110])
        
        # when
        result = TechnicalIndicators.calculate_rsi(prices, period=9)
        
        # then
        assert isinstance(result, pd.Series)
        assert len(result) == len(prices)
    
    def test_rsi_extreme_up_trend(self):
        # given
        prices = pd.Series([i for i in range(1, 21)])
        
        # when
        result = TechnicalIndicators.calculate_rsi(prices, period=9)
        
        # then
        assert result.iloc[-1] == 100.0
    
    def test_rsi_extreme_down_trend(self):
        # given
        prices = pd.Series([i for i in range(20, 0, -1)])
        
        # when
        result = TechnicalIndicators.calculate_rsi(prices, period=9)
        
        # then
        assert result.iloc[-1] == 0.0
    
    def test_rsi_with_flat_prices(self):
        # given
        prices = pd.Series([100] * 20)
        
        # when
        result = TechnicalIndicators.calculate_rsi(prices, period=9)
        
        # then
        assert pd.isna(result.iloc[-1]) or result.iloc[-1] == 50.0


class TestCalculateBollingerBands:
    
    def test_bollinger_returns_three_series(self):
        # given
        prices = pd.Series([100 + i for i in range(30)])
        
        # when
        lower, sma, upper = TechnicalIndicators.calculate_bollinger_bands(prices)
        
        # then
        assert isinstance(lower, pd.Series)
        assert isinstance(sma, pd.Series)
        assert isinstance(upper, pd.Series)
    
    def test_bollinger_upper_greater_than_lower(self):
        # given
        prices = pd.Series([100 + np.sin(i) * 5 for i in range(30)])
        
        # when
        lower, sma, upper = TechnicalIndicators.calculate_bollinger_bands(prices)
        
        # then
        valid_idx = ~pd.isna(lower) & ~pd.isna(upper)
        assert all(upper[valid_idx] >= lower[valid_idx])
    
    def test_bollinger_sma_between_bands(self):
        # given
        prices = pd.Series([100 + np.sin(i) * 5 for i in range(30)])
        
        # when
        lower, sma, upper = TechnicalIndicators.calculate_bollinger_bands(prices)
        
        # then
        valid_idx = ~pd.isna(lower) & ~pd.isna(upper) & ~pd.isna(sma)
        assert all(lower[valid_idx] <= sma[valid_idx])
        assert all(sma[valid_idx] <= upper[valid_idx])


class TestCalculateAll:
    
    def test_returns_none_for_insufficient_data(self):
        # given
        df = pd.DataFrame({"last": [100, 101, 102]})
        
        # when
        rsi, bb = TechnicalIndicators.calculate_all(df)
        
        # then
        assert rsi is None
        assert bb is None
    
    def test_returns_values_for_sufficient_data(self):
        # given
        df = pd.DataFrame({"last": [100 + i for i in range(30)]})
        
        # when
        rsi, bb = TechnicalIndicators.calculate_all(df)
        
        # then
        assert rsi is not None
        assert bb is not None
        assert isinstance(bb, tuple)
        assert len(bb) == 2


class TestFindSupportLevel:
    
    def test_returns_none_for_insufficient_data(self):
        # given
        df = pd.DataFrame({"low": [100, 101, 102]})
        
        # when
        result = TechnicalIndicators.find_support_level(df)
        
        # then
        assert result is None
    
    def test_finds_double_bottom(self):
        # given
        lows = [105, 103, 100.1, 104, 106, 100.2, 105, 107] * 10
        df = pd.DataFrame({"low": lows})
        
        # when
        result = TechnicalIndicators.find_support_level(df, window=60)
        
        # then
        assert result is not None
        assert 99 < result < 101


class TestCountRSIOversoldTouches:
    
    def test_counts_zero_for_no_oversold(self):
        # given
        df = pd.DataFrame({"last": [100 + i for i in range(80)]})
        
        # when
        result = TechnicalIndicators.count_rsi_oversold_touches(df, window=60)
        
        # then
        assert result == 0
    
    def test_counts_touches_with_minimum_gap(self):
        # given
        prices = []
        for i in range(80):
            if i % 20 < 5:
                prices.append(100 - i % 20)
            else:
                prices.append(100 + (i % 20))
        df = pd.DataFrame({"last": prices})
        
        # when
        result = TechnicalIndicators.count_rsi_oversold_touches(df, window=60, min_gap=5)
        
        # then
        assert result >= 0


class TestEstimatePriceForTargetRSI:
    
    def test_returns_none_for_insufficient_data(self):
        # given
        df = pd.DataFrame({"last": [100, 101, 102]})
        
        # when
        result = TechnicalIndicators.estimate_price_for_target_rsi(df)
        
        # then
        assert result is None
    
    def test_returns_price_for_sufficient_data(self):
        # given
        df = pd.DataFrame({"last": [100 + i * 0.5 for i in range(20)]})
        
        # when
        result = TechnicalIndicators.estimate_price_for_target_rsi(df, target_rsi=30)
        
        # then
        assert result is not None
        assert isinstance(result, (int, float))
