# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .database import Database, get_database

logger = logging.getLogger(__name__)


@dataclass
class SimulationState:
    initial_capital: float
    current_capital: float
    positions: Dict[str, Dict] = field(default_factory=dict)
    trades: List[Dict] = field(default_factory=list)
    daily_values: List[Dict] = field(default_factory=list)


class TradingSimulator:
    
    def __init__(self, db: Database = None, initial_capital: float = 10000000):
        self.db = db or get_database()
        self.state = SimulationState(
            initial_capital=initial_capital,
            current_capital=initial_capital
        )
        self.fee_rate = 0.00015
        self.tax_rate = 0.0021
    
    def reset(self, initial_capital: float = None):
        capital = initial_capital or self.state.initial_capital
        self.state = SimulationState(
            initial_capital=capital,
            current_capital=capital
        )
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        result = await self.db.fetch_one("""
            SELECT close FROM daily_price 
            WHERE ticker = ? 
            ORDER BY date DESC LIMIT 1
        """, (ticker,))
        return result['close'] if result else None
    
    def buy(self, ticker: str, price: float, quantity: int = None, 
            amount: float = None) -> Dict:
        if quantity is None and amount is None:
            return {"error": "quantity or amount required"}
        
        if quantity is None:
            quantity = int(amount / price)
        
        total_cost = price * quantity
        fee = total_cost * self.fee_rate
        required = total_cost + fee
        
        if required > self.state.current_capital:
            max_qty = int((self.state.current_capital * 0.99) / (price * (1 + self.fee_rate)))
            if max_qty <= 0:
                return {"error": "Insufficient capital"}
            quantity = max_qty
            total_cost = price * quantity
            fee = total_cost * self.fee_rate
            required = total_cost + fee
        
        self.state.current_capital -= required
        
        if ticker in self.state.positions:
            pos = self.state.positions[ticker]
            new_qty = pos['quantity'] + quantity
            new_avg = (pos['avg_price'] * pos['quantity'] + price * quantity) / new_qty
            pos['quantity'] = new_qty
            pos['avg_price'] = new_avg
        else:
            self.state.positions[ticker] = {
                'quantity': quantity,
                'avg_price': price,
                'entry_date': datetime.now().isoformat()
            }
        
        trade = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'side': 'BUY',
            'price': price,
            'quantity': quantity,
            'amount': total_cost,
            'fee': round(fee, 0),
            'capital_after': self.state.current_capital
        }
        self.state.trades.append(trade)
        
        return trade
    
    def sell(self, ticker: str, price: float, quantity: int = None) -> Dict:
        if ticker not in self.state.positions:
            return {"error": f"No position in {ticker}"}
        
        pos = self.state.positions[ticker]
        
        if quantity is None or quantity >= pos['quantity']:
            quantity = pos['quantity']
            is_full_close = True
        else:
            is_full_close = False
        
        total_proceeds = price * quantity
        fee = total_proceeds * self.fee_rate
        tax = total_proceeds * self.tax_rate
        net_proceeds = total_proceeds - fee - tax
        
        pnl = (price - pos['avg_price']) * quantity - fee - tax
        
        self.state.current_capital += net_proceeds
        
        if is_full_close:
            del self.state.positions[ticker]
        else:
            pos['quantity'] -= quantity
        
        trade = {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'side': 'SELL',
            'price': price,
            'quantity': quantity,
            'amount': total_proceeds,
            'fee': round(fee, 0),
            'tax': round(tax, 0),
            'pnl': round(pnl, 0),
            'capital_after': self.state.current_capital
        }
        self.state.trades.append(trade)
        
        return trade
    
    async def get_portfolio_value(self) -> float:
        total = self.state.current_capital
        
        for ticker, pos in self.state.positions.items():
            current_price = await self.get_current_price(ticker)
            if current_price:
                total += current_price * pos['quantity']
            else:
                total += pos['avg_price'] * pos['quantity']
        
        return total
    
    async def get_portfolio_summary(self) -> Dict:
        total_value = await self.get_portfolio_value()
        
        positions_detail = []
        for ticker, pos in self.state.positions.items():
            current_price = await self.get_current_price(ticker)
            if current_price:
                market_value = current_price * pos['quantity']
                unrealized_pnl = (current_price - pos['avg_price']) * pos['quantity']
                unrealized_pnl_pct = (current_price / pos['avg_price'] - 1) * 100
            else:
                market_value = pos['avg_price'] * pos['quantity']
                unrealized_pnl = 0
                unrealized_pnl_pct = 0
            
            stock = await self.db.fetch_one(
                "SELECT name FROM stock_info WHERE ticker = ?", (ticker,)
            )
            
            positions_detail.append({
                'ticker': ticker,
                'name': stock['name'] if stock else ticker,
                'quantity': pos['quantity'],
                'avg_price': pos['avg_price'],
                'current_price': current_price or pos['avg_price'],
                'market_value': market_value,
                'unrealized_pnl': round(unrealized_pnl, 0),
                'unrealized_pnl_pct': round(unrealized_pnl_pct, 2)
            })
        
        total_pnl = total_value - self.state.initial_capital
        total_return = (total_value / self.state.initial_capital - 1) * 100
        
        sell_trades = [t for t in self.state.trades if t['side'] == 'SELL']
        realized_pnl = sum(t.get('pnl', 0) for t in sell_trades)
        winning_trades = len([t for t in sell_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in sell_trades if t.get('pnl', 0) <= 0])
        win_rate = winning_trades / len(sell_trades) * 100 if sell_trades else 0
        
        return {
            'initial_capital': self.state.initial_capital,
            'current_capital': round(self.state.current_capital, 0),
            'total_value': round(total_value, 0),
            'total_pnl': round(total_pnl, 0),
            'total_return_pct': round(total_return, 2),
            'realized_pnl': round(realized_pnl, 0),
            'positions': positions_detail,
            'position_count': len(positions_detail),
            'total_trades': len(self.state.trades),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2)
        }
    
    def get_trades(self, limit: int = 50) -> List[Dict]:
        return self.state.trades[-limit:][::-1]
    
    def export_state(self) -> Dict:
        return {
            'initial_capital': self.state.initial_capital,
            'current_capital': self.state.current_capital,
            'positions': self.state.positions,
            'trades': self.state.trades,
            'exported_at': datetime.now().isoformat()
        }
    
    def import_state(self, data: Dict):
        self.state = SimulationState(
            initial_capital=data.get('initial_capital', 10000000),
            current_capital=data.get('current_capital', 10000000),
            positions=data.get('positions', {}),
            trades=data.get('trades', [])
        )


_simulator_instance: Optional[TradingSimulator] = None

def get_trading_simulator(initial_capital: float = 10000000) -> TradingSimulator:
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = TradingSimulator(initial_capital=initial_capital)
    return _simulator_instance
