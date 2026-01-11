# -*- coding: utf-8 -*-
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .database import Database, get_database

logger = logging.getLogger(__name__)


class NaverCollector:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def get_discussion_stats(self, ticker: str) -> Optional[Dict]:
        try:
            url = f"https://finance.naver.com/item/board.naver?code={ticker}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            posts = soup.select('table.type2 tbody tr')
            valid_posts = [p for p in posts if p.select_one('td.title')]
            
            post_count = len(valid_posts)
            total_views = 0
            total_likes = 0
            total_dislikes = 0
            
            for post in valid_posts[:20]:
                try:
                    views_td = post.select('td.num')
                    if len(views_td) >= 3:
                        views_text = views_td[0].get_text(strip=True).replace(',', '')
                        total_views += int(views_text) if views_text.isdigit() else 0
                        
                        likes_text = views_td[1].get_text(strip=True).replace(',', '')
                        total_likes += int(likes_text) if likes_text.isdigit() else 0
                        
                        dislikes_text = views_td[2].get_text(strip=True).replace(',', '')
                        total_dislikes += int(dislikes_text) if dislikes_text.isdigit() else 0
                except (ValueError, IndexError):
                    continue
            
            avg_views = total_views // post_count if post_count > 0 else 0
            like_ratio = total_likes / (total_likes + total_dislikes) if (total_likes + total_dislikes) > 0 else 0.5
            
            return {
                'ticker': ticker,
                'post_count': post_count,
                'avg_views': avg_views,
                'like_ratio': round(like_ratio, 3),
                'total_likes': total_likes,
                'total_dislikes': total_dislikes
            }
        except Exception as e:
            logger.debug(f"[Naver] Discussion fetch failed for {ticker}: {e}")
            return None
    
    def analyze_sentiment(self, ticker: str) -> float:
        try:
            url = f"https://finance.naver.com/item/board.naver?code={ticker}"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            titles = soup.select('td.title a')
            
            positive_keywords = ['상승', '급등', '호재', '매수', '기대', '좋', '강세', '돌파', '신고가', '목표가', '상향']
            negative_keywords = ['하락', '급락', '악재', '매도', '우려', '나쁨', '약세', '폭락', '손절', '하향', '위험']
            
            pos_count = 0
            neg_count = 0
            
            for title_elem in titles[:30]:
                title = title_elem.get_text(strip=True).lower()
                pos_count += sum(1 for kw in positive_keywords if kw in title)
                neg_count += sum(1 for kw in negative_keywords if kw in title)
            
            if pos_count + neg_count == 0:
                return 0.0
            
            return round((pos_count - neg_count) / (pos_count + neg_count), 3)
        except Exception as e:
            logger.debug(f"[Naver] Sentiment analysis failed for {ticker}: {e}")
            return 0.0
    
    async def collect_for_stock(self, ticker: str) -> Optional[Dict]:
        stats = self.get_discussion_stats(ticker)
        if not stats:
            return None
        
        sentiment = self.analyze_sentiment(ticker)
        
        data = {
            'ticker': ticker,
            'date': datetime.now().strftime("%Y-%m-%d"),
            'post_count': stats['post_count'],
            'avg_views': stats['avg_views'],
            'like_ratio': stats['like_ratio'],
            'sentiment_score': sentiment
        }
        
        await self.db.execute("""
            INSERT INTO naver_discussion (date, ticker, post_count, avg_views, like_ratio, sentiment_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                post_count = excluded.post_count,
                avg_views = excluded.avg_views,
                like_ratio = excluded.like_ratio,
                sentiment_score = excluded.sentiment_score
        """, (data['date'], data['ticker'], data['post_count'], data['avg_views'],
              data['like_ratio'], data['sentiment_score']))
        
        return data
    
    async def collect_batch(self, tickers: List[str], delay: float = 0.5) -> Dict:
        success = 0
        failed = 0
        
        for ticker in tickers:
            try:
                result = await self.collect_for_stock(ticker)
                if result:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.debug(f"[Naver] {ticker} failed: {e}")
                failed += 1
            
            await asyncio.sleep(delay)
        
        return {'success': success, 'failed': failed}


_naver_instance: Optional[NaverCollector] = None

def get_naver_collector() -> NaverCollector:
    global _naver_instance
    if _naver_instance is None:
        _naver_instance = NaverCollector()
    return _naver_instance
