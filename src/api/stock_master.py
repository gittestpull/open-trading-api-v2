# -*- coding: utf-8 -*-
import os
import sys
import time
import urllib.request
import ssl
import zipfile
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .database import Database, get_database


class StockMasterService:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(base_dir, "stock_info")
        os.makedirs(self.data_dir, exist_ok=True)
        ssl._create_default_https_context = ssl._create_unverified_context
    
    def _download_master(self, market: str) -> bool:
        url = f"https://new.real.download.dws.co.kr/common/master/{market}_code.mst.zip"
        zip_file = os.path.join(self.data_dir, f"{market}_code.zip")
        mst_file = os.path.join(self.data_dir, f"{market}_code.mst")
        
        if os.path.exists(mst_file):
            file_age_hours = (time.time() - os.path.getmtime(mst_file)) / 3600
            if file_age_hours < 24:
                return True
        
        try:
            print(f"[StockMaster] Downloading {market} master...")
            urllib.request.urlretrieve(url, zip_file)
            with zipfile.ZipFile(zip_file) as z:
                z.extractall(self.data_dir)
            if os.path.exists(zip_file):
                os.remove(zip_file)
            print(f"[StockMaster] {market} download complete")
            return True
        except Exception as e:
            print(f"[StockMaster] {market} download failed: {e}")
            return False
    
    def _parse_master(self, market: str) -> List[Dict]:
        mst_file = os.path.join(self.data_dir, f"{market}_code.mst")
        if not os.path.exists(mst_file):
            return []
        
        stocks = []
        cutoff = 228 if market == 'kospi' else 222
        
        try:
            with open(mst_file, mode="r", encoding="cp949") as f:
                for row in f:
                    part1 = row[0:len(row) - cutoff]
                    if len(part1) > 21:
                        ticker = part1[0:9].rstrip()
                        name = part1[21:].strip()
                        if ticker and name and ticker.isdigit():
                            stocks.append({
                                'ticker': ticker,
                                'name': name,
                                'market': market.upper()
                            })
        except Exception as e:
            print(f"[StockMaster] {market} parse error: {e}")
        
        return stocks
    
    async def load_all_stocks(self) -> int:
        all_stocks = []
        
        for market in ['kospi', 'kosdaq']:
            if self._download_master(market):
                stocks = self._parse_master(market)
                all_stocks.extend(stocks)
                print(f"[StockMaster] {market.upper()}: {len(stocks)} stocks loaded")
        
        if all_stocks:
            count = await self.db.upsert_stock_info(all_stocks)
            print(f"[StockMaster] Total {count} stocks saved to database")
            return count
        return 0
    
    async def get_all_tickers(self) -> List[str]:
        rows = await self.db.fetch_all("SELECT ticker FROM stock_info ORDER BY market, ticker")
        return [row['ticker'] for row in rows]
    
    async def get_stock_count(self) -> Dict[str, int]:
        total = await self.db.fetch_one("SELECT COUNT(*) as cnt FROM stock_info")
        kospi = await self.db.fetch_one("SELECT COUNT(*) as cnt FROM stock_info WHERE market = 'KOSPI'")
        kosdaq = await self.db.fetch_one("SELECT COUNT(*) as cnt FROM stock_info WHERE market = 'KOSDAQ'")
        return {
            'total': total['cnt'] if total else 0,
            'kospi': kospi['cnt'] if kospi else 0,
            'kosdaq': kosdaq['cnt'] if kosdaq else 0
        }
    
    async def search_stocks(self, keyword: str, limit: int = 20) -> List[Dict]:
        query = """
            SELECT ticker, name, market, sector, market_cap
            FROM stock_info
            WHERE name LIKE ? OR ticker LIKE ?
            ORDER BY market_cap DESC NULLS LAST
            LIMIT ?
        """
        pattern = f"%{keyword}%"
        return await self.db.fetch_all(query, (pattern, pattern, limit))
    
    async def get_stock_info(self, ticker: str) -> Optional[Dict]:
        query = "SELECT * FROM stock_info WHERE ticker = ?"
        return await self.db.fetch_one(query, (ticker,))
    
    async def get_top_stocks_by_market_cap(self, limit: int = 100) -> List[Dict]:
        query = """
            SELECT si.ticker, si.name, si.market, dp.market_cap
            FROM stock_info si
            LEFT JOIN daily_price dp ON si.ticker = dp.ticker 
                AND dp.date = (SELECT MAX(date) FROM daily_price WHERE ticker = si.ticker)
            WHERE dp.market_cap IS NOT NULL AND dp.market_cap > 0
            ORDER BY dp.market_cap DESC
            LIMIT ?
        """
        return await self.db.fetch_all(query, (limit,))
    
    def get_code_by_name(self, name: str) -> Optional[str]:
        for market in ['kospi', 'kosdaq']:
            mst_file = os.path.join(self.data_dir, f"{market}_code.mst")
            if not os.path.exists(mst_file):
                self._download_master(market)
            
            if os.path.exists(mst_file):
                cutoff = 228 if market == 'kospi' else 222
                try:
                    with open(mst_file, mode="r", encoding="cp949") as f:
                        for row in f:
                            part1 = row[0:len(row) - cutoff]
                            if len(part1) > 21:
                                stock_name = part1[21:].strip()
                                if stock_name == name:
                                    return part1[0:9].rstrip()
                except Exception:
                    pass
        return None


_service_instance: Optional[StockMasterService] = None

def get_stock_master_service() -> StockMasterService:
    global _service_instance
    if _service_instance is None:
        _service_instance = StockMasterService()
    return _service_instance
