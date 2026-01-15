# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .database import Database, get_database
from .youtube import YouTubeCollector, get_youtube_collector
from .naver import NaverCollector, get_naver_collector
from .log_buffer import get_log_buffer

logger = logging.getLogger(__name__)


class HumanIndexCalculator:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.youtube = get_youtube_collector()
        self.naver = get_naver_collector()
        self.log_buffer = get_log_buffer()
    
    async def calculate_attention_score(self, ticker: str, target_date: str = None) -> float:
        if target_date:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
        else:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
        
        score = 0.0
        
        if youtube:
            video_score = min(youtube.get('video_count', 0) / 10, 30)
            views_score = min(youtube.get('total_views', 0) / 100000, 30)
            score += video_score + views_score
        
        if naver:
            post_score = min(naver.get('post_count', 0) / 5, 20)
            views_score = min(naver.get('avg_views', 0) / 500, 20)
            score += post_score + views_score
        
        return min(score, 100)
    
    async def calculate_fomo_level(self, ticker: str, target_date: str = None) -> float:
        if target_date:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
            # Price is tricky if we don't have historical price for that specific date easily accessible 
            # in the same way, but let's try to find it or fallback
            price = await self.db.fetch_one(
                "SELECT * FROM daily_price WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1",
                (ticker, target_date)
            )
        else:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
            price = await self.db.fetch_one(
                "SELECT * FROM daily_price WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
        
        fomo = 0.0
        
        if price:
            change = price.get('change_rate', 0)
            if change > 5:
                fomo += min(change * 3, 30)
            elif change > 2:
                fomo += change * 2
        
        if youtube:
            if youtube.get('video_count', 0) > 15:
                fomo += 25
            elif youtube.get('video_count', 0) > 8:
                fomo += 15
            
            if youtube.get('sentiment_score', 0) > 0.5:
                fomo += 15
        
        if naver:
            if naver.get('like_ratio', 0.5) > 0.7:
                fomo += 15
            if naver.get('post_count', 0) > 30:
                fomo += 15
        
        return min(fomo, 100)
    
    async def calculate_crowd_sentiment(self, ticker: str, target_date: str = None) -> float:
        if target_date:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? AND date = ?",
                (ticker, target_date)
            )
        else:
            youtube = await self.db.fetch_one(
                "SELECT * FROM youtube_metrics WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
            naver = await self.db.fetch_one(
                "SELECT * FROM naver_discussion WHERE ticker = ? ORDER BY date DESC LIMIT 1",
                (ticker,)
            )
        
        sentiments = []
        weights = []
        
        if youtube and youtube.get('sentiment_score') is not None:
            sentiments.append(youtube['sentiment_score'])
            weights.append(0.4)
        
        if naver and naver.get('sentiment_score') is not None:
            sentiments.append(naver['sentiment_score'])
            weights.append(0.4)
        
        if naver and naver.get('like_ratio') is not None:
            like_sentiment = (naver['like_ratio'] - 0.5) * 2
            sentiments.append(like_sentiment)
            weights.append(0.2)
        
        if not sentiments:
            return 0.0
        
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(sentiments, weights))
        
        return round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
    
    async def calculate_human_index(self, ticker: str, target_date: str = None) -> Dict:
        attention = await self.calculate_attention_score(ticker, target_date)
        fomo = await self.calculate_fomo_level(ticker, target_date)
        sentiment = await self.calculate_crowd_sentiment(ticker, target_date)
        
        calc_date = target_date if target_date else datetime.now().strftime("%Y-%m-%d")
        
        data = {
            'ticker': ticker,
            'date': calc_date,
            'attention_score': round(attention, 2),
            'fomo_level': round(fomo, 2),
            'crowd_sentiment': sentiment
        }
        
        await self.db.execute("""
            INSERT INTO human_index (date, ticker, attention_score, fomo_level, crowd_sentiment)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                attention_score = excluded.attention_score,
                fomo_level = excluded.fomo_level,
                crowd_sentiment = excluded.crowd_sentiment
        """, (data['date'], data['ticker'], data['attention_score'], 
              data['fomo_level'], data['crowd_sentiment']))
        
        return data
    
    async def collect_all_human_data(self, ticker: str, stock_name: str, days: int = 60) -> Dict:
        results = {}
        affected_dates = set()
        
        self.log_buffer.add_sync(f"[HumanIndex] Starting collection for {stock_name} ({ticker})... Range: {days} days")
        
        try:
            self.log_buffer.add_sync(f"[HumanIndex] Collecting YouTube data for {stock_name}...")
            youtube_data = await self.youtube.collect_for_stock(ticker, stock_name, days=days)
            results['youtube'] = youtube_data
            if youtube_data and 'affected_dates' in youtube_data:
                count = len(youtube_data['affected_dates'])
                self.log_buffer.add_sync(f"[HumanIndex] YouTube: Found data for {count} days")
                affected_dates.update(youtube_data['affected_dates'])
            else:
                self.log_buffer.add_sync(f"[HumanIndex] YouTube: No data found")
        except Exception as e:
            logger.debug(f"[HumanIndex] YouTube failed for {ticker}: {e}")
            self.log_buffer.add_sync(f"[HumanIndex] YouTube failed: {e}", "ERROR")
            results['youtube'] = None
        
        try:
            self.log_buffer.add_sync(f"[HumanIndex] Collecting Naver discussion data for {ticker}...")
            naver_data = await self.naver.collect_for_stock(ticker, days=days)
            results['naver'] = naver_data
            if naver_data and 'affected_dates' in naver_data:
                count = len(naver_data['affected_dates'])
                self.log_buffer.add_sync(f"[HumanIndex] Naver: Found data for {count} days")
                affected_dates.update(naver_data['affected_dates'])
            else:
                self.log_buffer.add_sync(f"[HumanIndex] Naver: No data found")
        except Exception as e:
            logger.debug(f"[HumanIndex] Naver failed for {ticker}: {e}")
            self.log_buffer.add_sync(f"[HumanIndex] Naver failed: {e}", "ERROR")
            results['naver'] = None
            
        # Add today just in case
        affected_dates.add(datetime.now().strftime("%Y-%m-%d"))
        
        if affected_dates:
            sorted_dates = sorted(list(affected_dates))
            min_date_str = sorted_dates[0]
            max_date_str = sorted_dates[-1]
            
            try:
                min_date = datetime.strptime(min_date_str, "%Y-%m-%d")
                max_date = datetime.strptime(max_date_str, "%Y-%m-%d")
                
                curr = min_date
                while curr <= max_date:
                    ds = curr.strftime("%Y-%m-%d")
                    affected_dates.add(ds)
                    curr += timedelta(days=1)
                    
                self.log_buffer.add_sync(f"[HumanIndex] Filled sparse dates. Range: {min_date_str} ~ {max_date_str}")
            except Exception as e:
                logger.error(f"Date parsing error: {e}")
        
        # Recalculate human index for all affected dates
        calculated_indices = []
        try:
            # Sort dates to process chronologically
            sorted_dates = sorted(list(affected_dates))
            self.log_buffer.add_sync(f"[HumanIndex] Recalculating index for {len(sorted_dates)} dates: {sorted_dates[:5]}...")
            
            for d in sorted_dates:
                hi = await self.calculate_human_index(ticker, target_date=d)
                calculated_indices.append(hi)
            
            latest_hi = None
            if calculated_indices:
                calculated_indices.sort(key=lambda x: x['date'], reverse=True)
                latest_hi = calculated_indices[0]
                
            results['human_index'] = latest_hi
            results['history_updates'] = len(calculated_indices)
            results['collected'] = True # Explicit flag as requested
            
            self.log_buffer.add_sync(f"[HumanIndex] Collection complete for {stock_name}. Updated {len(calculated_indices)} days.")
            
        except Exception as e:
            logger.debug(f"[HumanIndex] Calculation failed for {ticker}: {e}")
            self.log_buffer.add_sync(f"[HumanIndex] Calculation failed: {e}", "ERROR")
            results['human_index'] = None
            results['collected'] = False
        
        return results
    
    async def get_human_index(self, ticker: str) -> Optional[Dict]:
        hi = await self.db.fetch_one(
            "SELECT * FROM human_index WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        if not hi:
            return None
            
        youtube = await self.db.fetch_one(
            "SELECT video_count, total_views, avg_likes, sentiment_score FROM youtube_metrics WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        naver = await self.db.fetch_one(
            "SELECT post_count, avg_views, like_ratio, sentiment_score FROM naver_discussion WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        result = dict(hi)
        if youtube:
            result['youtube'] = dict(youtube)
        if naver:
            result['naver'] = dict(naver)
            
        return result
    
    async def get_human_index_history(self, ticker: str, days: int = 30) -> List[Dict]:
        query = """
            SELECT date, attention_score, fomo_level, crowd_sentiment
            FROM human_index
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        rows = await self.db.fetch_all(query, (ticker, days))
        return [dict(r) for r in rows]
    
    async def get_human_index_chart_data(self, ticker: str, days: int = 30) -> Dict:
        history = await self.get_human_index_history(ticker, days)
        history.reverse()
        
        return {
            'ticker': ticker,
            'labels': [h['date'] for h in history],
            'attention': [h['attention_score'] for h in history],
            'fomo': [h['fomo_level'] for h in history],
            'sentiment': [h['crowd_sentiment'] for h in history]
        }
    
    async def get_youtube_history(self, ticker: str, days: int = 30) -> List[Dict]:
        query = """
            SELECT date, video_count, total_views, avg_likes, sentiment_score
            FROM youtube_metrics
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        rows = await self.db.fetch_all(query, (ticker, days))
        return [dict(r) for r in rows]
    
    async def get_naver_history(self, ticker: str, days: int = 30) -> List[Dict]:
        query = """
            SELECT date, post_count, avg_views, like_ratio, sentiment_score
            FROM naver_discussion
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        rows = await self.db.fetch_all(query, (ticker, days))
        return [dict(r) for r in rows]
    
    async def get_fomo_alert_stocks(self, threshold: float = 70) -> List[Dict]:
        return await self.db.fetch_all("""
            SELECT hi.*, si.name, dp.close, dp.change_rate
            FROM human_index hi
            JOIN stock_info si ON hi.ticker = si.ticker
            LEFT JOIN daily_price dp ON hi.ticker = dp.ticker 
                AND dp.date = (SELECT MAX(date) FROM daily_price WHERE ticker = hi.ticker)
            WHERE hi.fomo_level >= ?
            AND hi.date = (SELECT MAX(date) FROM human_index)
            ORDER BY hi.fomo_level DESC
            LIMIT 20
        """, (threshold,))
    
    async def get_bottom_signal_stocks(self, attention_threshold: float = 20) -> List[Dict]:
        return await self.db.fetch_all("""
            SELECT hi.*, si.name, dp.close, dp.change_rate
            FROM human_index hi
            JOIN stock_info si ON hi.ticker = si.ticker
            LEFT JOIN daily_price dp ON hi.ticker = dp.ticker 
                AND dp.date = (SELECT MAX(date) FROM daily_price WHERE ticker = hi.ticker)
            WHERE hi.attention_score <= ?
            AND hi.crowd_sentiment < 0
            AND hi.date = (SELECT MAX(date) FROM human_index)
            ORDER BY hi.attention_score ASC
            LIMIT 20
        """, (attention_threshold,))


_calculator_instance: Optional[HumanIndexCalculator] = None

def get_human_index_calculator() -> HumanIndexCalculator:
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = HumanIndexCalculator()
    return _calculator_instance
