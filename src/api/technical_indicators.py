# -*- coding: utf-8 -*-
"""
Technical Indicators Calculator for AI Analysis.

Design Principle: "계산은 Python이, 해석은 AI가"
- All indicators are pre-calculated here
- AI receives structured data, not raw prices
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .database import Database, get_database

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSummary:
    """Pre-calculated technical indicators for AI consumption."""
    ticker: str
    calculated_at: str
    
    # Price info
    current_price: float
    price_change_1d: float
    price_change_5d: float
    price_change_20d: float
    
    # Moving Averages
    ma5: Optional[float]
    ma20: Optional[float]
    ma60: Optional[float]
    ma120: Optional[float]
    
    # MA Position (현재가 대비 이격도)
    disparity_5: Optional[float]   # (현재가 - MA5) / MA5 * 100
    disparity_20: Optional[float]
    disparity_60: Optional[float]
    
    # RSI
    rsi_9: Optional[float]
    rsi_14: Optional[float]
    rsi_signal: str  # "oversold", "overbought", "neutral"
    
    # MACD
    macd: Optional[float]
    macd_signal: Optional[float]
    macd_histogram: Optional[float]
    macd_trend: str  # "bullish_cross", "bearish_cross", "bullish", "bearish"
    
    # Bollinger Bands
    bb_upper: Optional[float]
    bb_middle: Optional[float]
    bb_lower: Optional[float]
    bb_position: str  # "above_upper", "near_upper", "middle", "near_lower", "below_lower"
    bb_width: Optional[float]  # (upper - lower) / middle * 100 - 변동성 지표
    
    # Support/Resistance
    support_level: Optional[float]
    resistance_level: Optional[float]
    distance_to_support: Optional[float]  # %
    distance_to_resistance: Optional[float]  # %
    
    # Volume Analysis
    volume_ratio_5d: Optional[float]  # 오늘 거래량 / 5일 평균
    volume_trend: str  # "surge", "high", "normal", "low"
    
    # Trend Summary
    short_trend: str   # "strong_up", "up", "neutral", "down", "strong_down"
    mid_trend: str
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "calculated_at": self.calculated_at,
            "price": {
                "current": self.current_price,
                "change_1d_pct": self.price_change_1d,
                "change_5d_pct": self.price_change_5d,
                "change_20d_pct": self.price_change_20d,
            },
            "moving_averages": {
                "ma5": self.ma5,
                "ma20": self.ma20,
                "ma60": self.ma60,
                "ma120": self.ma120,
                "disparity_5": self.disparity_5,
                "disparity_20": self.disparity_20,
                "disparity_60": self.disparity_60,
            },
            "rsi": {
                "rsi_9": self.rsi_9,
                "rsi_14": self.rsi_14,
                "signal": self.rsi_signal,
            },
            "macd": {
                "macd": self.macd,
                "signal": self.macd_signal,
                "histogram": self.macd_histogram,
                "trend": self.macd_trend,
            },
            "bollinger": {
                "upper": self.bb_upper,
                "middle": self.bb_middle,
                "lower": self.bb_lower,
                "position": self.bb_position,
                "width_pct": self.bb_width,
            },
            "support_resistance": {
                "support": self.support_level,
                "resistance": self.resistance_level,
                "distance_to_support_pct": self.distance_to_support,
                "distance_to_resistance_pct": self.distance_to_resistance,
            },
            "volume": {
                "ratio_vs_5d_avg": self.volume_ratio_5d,
                "trend": self.volume_trend,
            },
            "trend": {
                "short_term": self.short_trend,
                "mid_term": self.mid_trend,
            },
        }
    
    def to_prompt_text(self) -> str:
        """Generate text summary for GPT prompt injection."""
        lines = [
            f"[기술적 지표 - {self.ticker}]",
            f"현재가: {self.current_price:,.0f}원 (1일 {self.price_change_1d:+.2f}%, 5일 {self.price_change_5d:+.2f}%, 20일 {self.price_change_20d:+.2f}%)",
            "",
            "이동평균:",
        ]
        
        if self.ma5:
            lines.append(f"  MA5: {self.ma5:,.0f}원 (이격도 {self.disparity_5:+.1f}%)")
        if self.ma20:
            lines.append(f"  MA20: {self.ma20:,.0f}원 (이격도 {self.disparity_20:+.1f}%)")
        if self.ma60:
            lines.append(f"  MA60: {self.ma60:,.0f}원 (이격도 {self.disparity_60:+.1f}%)")
        if self.ma120:
            lines.append(f"  MA120: {self.ma120:,.0f}원")
        
        lines.append("")
        lines.append(f"RSI(9): {self.rsi_9:.1f} / RSI(14): {self.rsi_14:.1f} → {self.rsi_signal}")
        
        if self.macd is not None:
            lines.append(f"MACD: {self.macd:.2f}, Signal: {self.macd_signal:.2f}, Hist: {self.macd_histogram:.2f} → {self.macd_trend}")
        
        if self.bb_upper:
            lines.append(f"볼린저: 상단 {self.bb_upper:,.0f} / 중심 {self.bb_middle:,.0f} / 하단 {self.bb_lower:,.0f} → {self.bb_position}")
            lines.append(f"볼린저 밴드폭: {self.bb_width:.1f}% (변동성)")
        
        if self.support_level:
            lines.append(f"지지선: {self.support_level:,.0f}원 (현재가 대비 {self.distance_to_support:+.1f}%)")
        if self.resistance_level:
            lines.append(f"저항선: {self.resistance_level:,.0f}원 (현재가 대비 {self.distance_to_resistance:+.1f}%)")
        
        lines.append(f"거래량: 5일 평균 대비 {self.volume_ratio_5d:.1f}배 → {self.volume_trend}")
        lines.append(f"추세: 단기 {self.short_trend} / 중기 {self.mid_trend}")
        
        return "\n".join(lines)


class TechnicalIndicatorCalculator:
    """Calculate technical indicators from price data."""
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
    
    async def calculate_for_ticker(self, ticker: str, days: int = 150) -> Optional[TechnicalSummary]:
        """Calculate all technical indicators for a ticker."""
        prices = await self.db.fetch_all(
            "SELECT date, open, high, low, close, volume FROM daily_price WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker, days)
        )
        
        if not prices or len(prices) < 20:
            logger.warning(f"[TechnicalIndicator] Insufficient data for {ticker}: {len(prices) if prices else 0} days")
            return None
        
        # Convert to DataFrame (oldest first for calculations)
        df = pd.DataFrame([dict(p) for p in reversed(prices)])
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        current_price = df['close'].iloc[-1]
        
        # Price changes
        price_1d = self._calc_pct_change(df['close'], 1)
        price_5d = self._calc_pct_change(df['close'], 5)
        price_20d = self._calc_pct_change(df['close'], 20)
        
        # Moving Averages
        ma5 = self._calc_ma(df['close'], 5)
        ma20 = self._calc_ma(df['close'], 20)
        ma60 = self._calc_ma(df['close'], 60)
        ma120 = self._calc_ma(df['close'], 120)
        
        # Disparity (이격도)
        disparity_5 = self._calc_disparity(current_price, ma5)
        disparity_20 = self._calc_disparity(current_price, ma20)
        disparity_60 = self._calc_disparity(current_price, ma60)
        
        # RSI
        rsi_9 = self._calc_rsi(df['close'], 9)
        rsi_14 = self._calc_rsi(df['close'], 14)
        rsi_signal = self._interpret_rsi(rsi_14)
        
        # MACD
        macd, macd_signal_line, macd_hist = self._calc_macd(df['close'])
        macd_trend = self._interpret_macd(macd, macd_signal_line, macd_hist, df['close'])
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._calc_bollinger(df['close'])
        bb_position = self._interpret_bollinger_position(current_price, bb_upper, bb_middle, bb_lower)
        bb_width = self._calc_bollinger_width(bb_upper, bb_middle, bb_lower)
        
        # Support/Resistance
        support = self._find_support(df['low'])
        resistance = self._find_resistance(df['high'])
        dist_support = self._calc_disparity(current_price, support) if support else None
        dist_resistance = self._calc_disparity(current_price, resistance) if resistance else None
        
        # Volume Analysis
        volume_ratio = self._calc_volume_ratio(df['volume'])
        volume_trend = self._interpret_volume(volume_ratio)
        
        # Trend Analysis
        short_trend = self._analyze_trend(df['close'], ma5, ma20, rsi_14)
        mid_trend = self._analyze_mid_trend(df['close'], ma20, ma60, ma120)
        
        return TechnicalSummary(
            ticker=ticker,
            calculated_at=datetime.now().isoformat(),
            current_price=current_price,
            price_change_1d=price_1d or 0,
            price_change_5d=price_5d or 0,
            price_change_20d=price_20d or 0,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            ma120=ma120,
            disparity_5=disparity_5,
            disparity_20=disparity_20,
            disparity_60=disparity_60,
            rsi_9=rsi_9,
            rsi_14=rsi_14,
            rsi_signal=rsi_signal,
            macd=macd,
            macd_signal=macd_signal_line,
            macd_histogram=macd_hist,
            macd_trend=macd_trend,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            bb_position=bb_position,
            bb_width=bb_width,
            support_level=support,
            resistance_level=resistance,
            distance_to_support=dist_support,
            distance_to_resistance=dist_resistance,
            volume_ratio_5d=volume_ratio,
            volume_trend=volume_trend,
            short_trend=short_trend,
            mid_trend=mid_trend,
        )
    
    # ========== Calculation Methods ==========
    
    def _calc_pct_change(self, series: pd.Series, periods: int) -> Optional[float]:
        if len(series) <= periods:
            return None
        current = series.iloc[-1]
        past = series.iloc[-1 - periods]
        if past == 0:
            return None
        return round((current - past) / past * 100, 2)
    
    def _calc_ma(self, series: pd.Series, period: int) -> Optional[float]:
        if len(series) < period:
            return None
        return round(series.tail(period).mean(), 2)
    
    def _calc_disparity(self, current: float, ma: Optional[float]) -> Optional[float]:
        if ma is None or ma == 0:
            return None
        return round((current - ma) / ma * 100, 2)
    
    def _calc_rsi(self, series: pd.Series, period: int) -> Optional[float]:
        if len(series) < period + 1:
            return None
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        if loss.iloc[-1] == 0:
            return 100.0
        rs = gain.iloc[-1] / loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def _interpret_rsi(self, rsi: Optional[float]) -> str:
        if rsi is None:
            return "unknown"
        if rsi <= 30:
            return "oversold"
        elif rsi >= 70:
            return "overbought"
        elif rsi <= 40:
            return "near_oversold"
        elif rsi >= 60:
            return "near_overbought"
        return "neutral"
    
    def _calc_macd(self, series: pd.Series) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(series) < 26:
            return None, None, None
        
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return (
            round(macd_line.iloc[-1], 2),
            round(signal_line.iloc[-1], 2),
            round(histogram.iloc[-1], 2)
        )
    
    def _interpret_macd(self, macd: Optional[float], signal: Optional[float], hist: Optional[float], series: pd.Series) -> str:
        if macd is None or signal is None or hist is None:
            return "unknown"
        
        # Check for crossover (compare current and previous)
        if len(series) >= 27:
            ema12 = series.ewm(span=12, adjust=False).mean()
            ema26 = series.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]
            prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
            
            if prev_diff < 0 and curr_diff > 0:
                return "bullish_cross"
            elif prev_diff > 0 and curr_diff < 0:
                return "bearish_cross"
        
        if hist > 0:
            return "bullish"
        return "bearish"
    
    def _calc_bollinger(self, series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(series) < period:
            return None, None, None
        
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return (
            round(upper.iloc[-1], 2),
            round(sma.iloc[-1], 2),
            round(lower.iloc[-1], 2)
        )
    
    def _interpret_bollinger_position(self, price: float, upper: Optional[float], middle: Optional[float], lower: Optional[float]) -> str:
        if upper is None or middle is None or lower is None:
            return "unknown"
        
        band_width = upper - lower
        if band_width == 0:
            return "unknown"
        
        if price > upper:
            return "above_upper"
        elif price > upper - band_width * 0.1:
            return "near_upper"
        elif price < lower:
            return "below_lower"
        elif price < lower + band_width * 0.1:
            return "near_lower"
        return "middle"
    
    def _calc_bollinger_width(self, upper: Optional[float], middle: Optional[float], lower: Optional[float]) -> Optional[float]:
        if upper is None or middle is None or lower is None or middle == 0:
            return None
        return round((upper - lower) / middle * 100, 2)
    
    def _find_support(self, lows: pd.Series, window: int = 60) -> Optional[float]:
        if len(lows) < window:
            return None
        
        recent = lows.tail(window)
        sorted_lows = recent.nsmallest(10)
        
        # Find cluster of similar lows
        for i, low1 in enumerate(sorted_lows):
            for low2 in list(sorted_lows)[i+1:]:
                if abs(low1 - low2) / low1 < 0.01:  # Within 1%
                    return round((low1 + low2) / 2, 2)
        
        return round(sorted_lows.iloc[0], 2)
    
    def _find_resistance(self, highs: pd.Series, window: int = 60) -> Optional[float]:
        if len(highs) < window:
            return None
        
        recent = highs.tail(window)
        sorted_highs = recent.nlargest(10)
        
        # Find cluster of similar highs
        for i, high1 in enumerate(sorted_highs):
            for high2 in list(sorted_highs)[i+1:]:
                if abs(high1 - high2) / high1 < 0.01:  # Within 1%
                    return round((high1 + high2) / 2, 2)
        
        return round(sorted_highs.iloc[0], 2)
    
    def _calc_volume_ratio(self, volume: pd.Series) -> Optional[float]:
        if len(volume) < 6:
            return None
        
        today_vol = volume.iloc[-1]
        avg_5d = volume.iloc[-6:-1].mean()
        
        if avg_5d == 0:
            return None
        return round(today_vol / avg_5d, 2)
    
    def _interpret_volume(self, ratio: Optional[float]) -> str:
        if ratio is None:
            return "unknown"
        if ratio >= 3.0:
            return "surge"
        elif ratio >= 1.5:
            return "high"
        elif ratio >= 0.7:
            return "normal"
        return "low"
    
    def _analyze_trend(self, prices: pd.Series, ma5: Optional[float], ma20: Optional[float], rsi: Optional[float]) -> str:
        if ma5 is None or ma20 is None:
            return "unknown"
        
        current = prices.iloc[-1]
        score = 0
        
        # Price vs MAs
        if current > ma5:
            score += 1
        else:
            score -= 1
        
        if current > ma20:
            score += 1
        else:
            score -= 1
        
        # MA alignment
        if ma5 > ma20:
            score += 1
        else:
            score -= 1
        
        # RSI momentum
        if rsi is not None:
            if rsi > 60:
                score += 1
            elif rsi < 40:
                score -= 1
        
        if score >= 3:
            return "strong_up"
        elif score >= 1:
            return "up"
        elif score <= -3:
            return "strong_down"
        elif score <= -1:
            return "down"
        return "neutral"
    
    def _analyze_mid_trend(self, prices: pd.Series, ma20: Optional[float], ma60: Optional[float], ma120: Optional[float]) -> str:
        if ma20 is None or ma60 is None:
            return "unknown"
        
        current = prices.iloc[-1]
        score = 0
        
        if current > ma60:
            score += 1
        else:
            score -= 1
        
        if ma20 > ma60:
            score += 1
        else:
            score -= 1
        
        if ma120 is not None:
            if current > ma120:
                score += 1
            else:
                score -= 1
            
            if ma60 > ma120:
                score += 1
            else:
                score -= 1
        
        if score >= 3:
            return "strong_up"
        elif score >= 1:
            return "up"
        elif score <= -3:
            return "strong_down"
        elif score <= -1:
            return "down"
        return "neutral"


_calculator_instance: Optional[TechnicalIndicatorCalculator] = None

def get_technical_calculator() -> TechnicalIndicatorCalculator:
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = TechnicalIndicatorCalculator()
    return _calculator_instance
