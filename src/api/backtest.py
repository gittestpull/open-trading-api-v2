# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .database import Database, get_database

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Dict] = field(default_factory=list)


class BacktestEngine:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
    
    async def get_price_history(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        return await self.db.fetch_all("""
            SELECT * FROM daily_price 
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (ticker, start_date, end_date))
    
    async def run_simple_ma_strategy(self, ticker: str, start_date: str, end_date: str,
                                      short_period: int = 5, long_period: int = 20,
                                      initial_capital: float = 10000000) -> BacktestResult:
        prices = await self.get_price_history(ticker, start_date, end_date)
        
        if len(prices) < long_period:
            return BacktestResult(
                strategy_name=f"MA_{short_period}_{long_period}",
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, final_capital=initial_capital,
                total_return=0, win_rate=0, total_trades=0,
                winning_trades=0, losing_trades=0, max_drawdown=0, sharpe_ratio=0
            )
        
        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        peak_capital = capital
        max_drawdown = 0
        daily_returns = []
        
        for i in range(long_period, len(prices)):
            close_prices = [p['close'] for p in prices[i-long_period:i]]
            short_ma = sum(close_prices[-short_period:]) / short_period
            long_ma = sum(close_prices) / long_period
            current_price = prices[i]['close']
            current_date = prices[i]['date']
            
            if position == 0 and short_ma > long_ma:
                position = int(capital * 0.95 / current_price)
                if position > 0:
                    entry_price = current_price
                    capital -= position * current_price
                    trades.append({
                        'date': current_date,
                        'action': 'BUY',
                        'price': current_price,
                        'quantity': position,
                        'capital': capital
                    })
            
            elif position > 0 and short_ma < long_ma:
                sell_value = position * current_price
                pnl = (current_price - entry_price) * position
                capital += sell_value
                trades.append({
                    'date': current_date,
                    'action': 'SELL',
                    'price': current_price,
                    'quantity': position,
                    'pnl': pnl,
                    'capital': capital
                })
                position = 0
                entry_price = 0
            
            total_value = capital + (position * current_price if position > 0 else 0)
            if total_value > peak_capital:
                peak_capital = total_value
            drawdown = (peak_capital - total_value) / peak_capital * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            if i > long_period:
                prev_value = capital + (position * prices[i-1]['close'] if position > 0 else 0)
                daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0
                daily_returns.append(daily_return)
        
        if position > 0:
            final_price = prices[-1]['close']
            capital += position * final_price
        
        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        winning_trades = len([t for t in sell_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in sell_trades if t.get('pnl', 0) <= 0])
        win_rate = winning_trades / len(sell_trades) * 100 if sell_trades else 0
        
        if daily_returns:
            avg_return = sum(daily_returns) / len(daily_returns)
            std_return = (sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        return BacktestResult(
            strategy_name=f"MA_{short_period}_{long_period}",
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=round(total_return, 2),
            win_rate=round(win_rate, 2),
            total_trades=len(sell_trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            trades=trades
        )
    
    async def run_rsi_strategy(self, ticker: str, start_date: str, end_date: str,
                                period: int = 14, oversold: int = 30, overbought: int = 70,
                                initial_capital: float = 10000000) -> BacktestResult:
        prices = await self.get_price_history(ticker, start_date, end_date)
        
        if len(prices) < period + 1:
            return BacktestResult(
                strategy_name=f"RSI_{period}",
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, final_capital=initial_capital,
                total_return=0, win_rate=0, total_trades=0,
                winning_trades=0, losing_trades=0, max_drawdown=0, sharpe_ratio=0
            )
        
        def calculate_rsi(prices_list: List[float], period: int) -> float:
            if len(prices_list) < period + 1:
                return 50
            
            gains = []
            losses = []
            for i in range(1, len(prices_list)):
                change = prices_list[i] - prices_list[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                return 100
            
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        
        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        peak_capital = capital
        max_drawdown = 0
        
        for i in range(period + 1, len(prices)):
            close_prices = [p['close'] for p in prices[:i+1]]
            rsi = calculate_rsi(close_prices, period)
            current_price = prices[i]['close']
            current_date = prices[i]['date']
            
            if position == 0 and rsi < oversold:
                position = int(capital * 0.95 / current_price)
                if position > 0:
                    entry_price = current_price
                    capital -= position * current_price
                    trades.append({
                        'date': current_date, 'action': 'BUY',
                        'price': current_price, 'quantity': position,
                        'rsi': round(rsi, 1)
                    })
            
            elif position > 0 and rsi > overbought:
                pnl = (current_price - entry_price) * position
                capital += position * current_price
                trades.append({
                    'date': current_date, 'action': 'SELL',
                    'price': current_price, 'quantity': position,
                    'pnl': pnl, 'rsi': round(rsi, 1)
                })
                position = 0
                entry_price = 0
            
            total_value = capital + (position * current_price if position > 0 else 0)
            if total_value > peak_capital:
                peak_capital = total_value
            drawdown = (peak_capital - total_value) / peak_capital * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        if position > 0:
            capital += position * prices[-1]['close']
        
        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        winning_trades = len([t for t in sell_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in sell_trades if t.get('pnl', 0) <= 0])
        win_rate = winning_trades / len(sell_trades) * 100 if sell_trades else 0
        
        return BacktestResult(
            strategy_name=f"RSI_{period}",
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, final_capital=final_capital,
            total_return=round(total_return, 2),
            win_rate=round(win_rate, 2),
            total_trades=len(sell_trades),
            winning_trades=winning_trades, losing_trades=losing_trades,
            max_drawdown=round(max_drawdown, 2), sharpe_ratio=0,
            trades=trades
        )
    
    async def save_result(self, result: BacktestResult) -> int:
        import json
        
        await self.db.execute("""
            INSERT INTO backtest_results 
            (strategy_name, start_date, end_date, total_return, win_rate, max_drawdown, sharpe_ratio, params)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.strategy_name, result.start_date, result.end_date,
            result.total_return, result.win_rate, result.max_drawdown,
            result.sharpe_ratio, json.dumps({'trades': len(result.trades)})
        ))
        
        row = await self.db.fetch_one(
            "SELECT id FROM backtest_results ORDER BY id DESC LIMIT 1"
        )
        return row['id'] if row else 0
    
    async def get_results(self, limit: int = 20) -> List[Dict]:
        return await self.db.fetch_all(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )


_backtest_instance: Optional[BacktestEngine] = None

def get_backtest_engine() -> BacktestEngine:
    global _backtest_instance
    if _backtest_instance is None:
        _backtest_instance = BacktestEngine()
    return _backtest_instance
