# -*- coding: utf-8 -*-
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests

from .database import Database, get_database

logger = logging.getLogger(__name__)

YAHOO_FINANCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


class GlobalMarketCollector:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.symbols = {
            'SPY': 'S&P 500 ETF',
            'QQQ': 'Nasdaq 100 ETF',
            'DIA': 'Dow Jones ETF',
            'VIX': 'Volatility Index',
            'DXY': 'US Dollar Index',
            'GLD': 'Gold ETF',
            'TLT': '20+ Year Treasury',
            'USO': 'Oil ETF',
        }
        # Mapping for Yahoo Finance specific symbols
        self.yahoo_symbols = {
            'VIX': '^VIX',
            'DXY': 'DX-Y.NYB'
        }
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        try:
            response = requests.get(
                f"{YAHOO_FINANCE_URL}/{symbol}",
                params={'interval': '1d', 'range': '5d'},
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            result = data.get('chart', {}).get('result', [])
            if not result:
                return None
            
            meta = result[0].get('meta', {})
            quote = result[0].get('indicators', {}).get('quote', [{}])[0]
            
            closes = quote.get('close', [])
            # Filter out None values which can happen with Yahoo data
            valid_closes = [c for c in closes if c is not None]
            
            if not valid_closes or len(valid_closes) < 2:
                # Retry logic or check if we have at least one current price
                if valid_closes:
                    current_price = valid_closes[-1]
                    return {
                        'symbol': symbol,
                        'name': self.symbols.get(symbol, symbol),
                        'close_price': round(current_price, 2),
                        'change_rate': 0.0,
                        'currency': meta.get('currency', 'USD')
                    }
                return None
            
            current_price = valid_closes[-1]
            prev_price = valid_closes[-2]
            change_rate = ((current_price - prev_price) / prev_price * 100) if prev_price else 0
            
            return {
                'symbol': symbol,
                'name': self.symbols.get(symbol, symbol),
                'close_price': round(current_price, 2),
                'change_rate': round(change_rate, 2),
                'currency': meta.get('currency', 'USD')
            }
        except Exception as e:
            logger.debug(f"[GlobalMarket] {symbol} fetch failed: {e}")
            return None
    
    async def collect_all(self) -> Dict:
        results = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        for internal_symbol, name in self.symbols.items():
            # Use mapped symbol if available, otherwise use internal symbol
            query_symbol = self.yahoo_symbols.get(internal_symbol, internal_symbol)
            
            data = self.fetch_quote(query_symbol)
            if data:
                # Restore internal symbol for database consistency
                data['symbol'] = internal_symbol
                data['name'] = name
                results.append(data)
                
                await self.db.execute("""
                    INSERT INTO global_market (date, symbol, close_price, change_rate)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date, symbol) DO UPDATE SET
                        close_price = excluded.close_price,
                        change_rate = excluded.change_rate
                """, (today, internal_symbol, data['close_price'], data['change_rate']))
            
            await asyncio.sleep(0.3)
        
        return {
            'date': today,
            'markets': results,
            'count': len(results)
        }
    
    async def get_latest(self) -> List[Dict]:
        return await self.db.fetch_all("""
            SELECT gm.*, 
                   (SELECT close_price FROM global_market gm2 
                    WHERE gm2.symbol = gm.symbol AND gm2.date < gm.date 
                    ORDER BY date DESC LIMIT 1) as prev_close
            FROM global_market gm
            WHERE gm.date = (SELECT MAX(date) FROM global_market)
            ORDER BY gm.symbol
        """)
    
    async def get_history(self, symbol: str, days: int = 30) -> List[Dict]:
        return await self.db.fetch_all("""
            SELECT * FROM global_market 
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
        """, (symbol, days))
    
    async def get_market_summary(self) -> Dict:
        latest = await self.get_latest()
        
        summary = {
            'us_stocks': {},
            'volatility': {},
            'commodities': {},
            'bonds': {},
            'currency': {}
        }
        
        category_map = {
            'SPY': 'us_stocks', 'QQQ': 'us_stocks', 'DIA': 'us_stocks',
            'VIX': 'volatility',
            'GLD': 'commodities', 'USO': 'commodities',
            'TLT': 'bonds',
            'DXY': 'currency'
        }
        
        for item in latest:
            symbol = item['symbol']
            category = category_map.get(symbol, 'other')
            summary[category][symbol] = {
                'price': item['close_price'],
                'change': item['change_rate']
            }
        
        spy_data = summary['us_stocks'].get('SPY', {})
        vix_data = summary['volatility'].get('VIX', {})
        
        market_sentiment = 'neutral'
        if spy_data.get('change', 0) > 1 and vix_data.get('change', 0) < 0:
            market_sentiment = 'bullish'
        elif spy_data.get('change', 0) < -1 and vix_data.get('change', 0) > 0:
            market_sentiment = 'bearish'
        
        summary['sentiment'] = market_sentiment
        summary['updated_at'] = datetime.now().isoformat()
        
        return summary


_global_market_instance: Optional[GlobalMarketCollector] = None

def get_global_market_collector() -> GlobalMarketCollector:
    global _global_market_instance
    if _global_market_instance is None:
        _global_market_instance = GlobalMarketCollector()
    return _global_market_instance
