# -*- coding: utf-8 -*-
import asyncio
import logging
import re
from datetime import datetime, timedelta
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
    
    def get_discussion_posts(self, ticker: str, max_pages: int = 100, days_back: int = 30) -> List[Dict]:
        try:
            posts = []
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            for page in range(1, max_pages + 1):
                url = f"https://finance.naver.com/item/board.naver?code={ticker}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                rows = soup.select('table.type2 tbody tr')
                page_posts = []
                stop_collection = False
                
                for row in rows:
                    if not row.select_one('td.title'):
                        continue
                        
                    try:
                        title_elem = row.select_one('td.title a')
                        if not title_elem: continue
                        title = title_elem.get_text(strip=True)
                        
                        # Get all td elements in this row
                        tds = row.find_all('td')
                        date_str = ""
                        if len(tds) >= 1:
                            # First td contains date (e.g., "2026.01.13 14:53")
                            date_raw = tds[0].get_text(strip=True)
                            if len(date_raw) >= 10:
                                date_str = date_raw[:10].replace('.', '-')
                            else:
                                date_str = datetime.now().strftime("%Y-%m-%d")
                        
                        if not date_str:
                             date_str = datetime.now().strftime("%Y-%m-%d")

                        # Stop if we went back far enough
                        if date_str < cutoff_date:
                            stop_collection = True
                            # Don't break here immediately if we want to finish the page, 
                            # but usually we can stop. Let's just ignore this post and continue checking
                            # incase order is slightly off (unlikely for board).
                            # Actually, Naver board is strict reverse chrono.
                            break
    
                        # tds[3]=views, tds[4]=likes, tds[5]=dislikes (no class)
                        views = 0
                        likes = 0
                        dislikes = 0
                        
                        if len(tds) >= 6:
                             v_text = tds[3].get_text(strip=True).replace(',', '')
                             l_text = tds[4].get_text(strip=True).replace(',', '')
                             d_text = tds[5].get_text(strip=True).replace(',', '')
                             
                             if v_text.isdigit(): views = int(v_text)
                             if l_text.isdigit(): likes = int(l_text)
                             if d_text.isdigit(): dislikes = int(d_text)
                        
                        page_posts.append({
                            'title': title,
                            'date': date_str,
                            'views': views,
                            'likes': likes,
                            'dislikes': dislikes
                        })
                    except Exception:
                        continue
                
                if not page_posts:
                    break
                    
                posts.extend(page_posts)
                
                if stop_collection:
                    break
                
                # Small delay to be polite
                if page % 10 == 0:
                    asyncio.sleep(0.5) 
                    # Note: we are in a sync function here called by async. 
                    # requests is sync. time.sleep is better but blocks loop.
                    # Since this is running in threadpool usually (FastAPI), time.sleep is ok?
                    # But here we are just calling it directly.
                    # Let's use no sleep for now as requests takes time.
                
            return posts
        except Exception as e:
            logger.debug(f"[Naver] Failed to fetch posts for {ticker}: {e}")
            return []

    def analyze_sentiment(self, titles: List[str]) -> float:
        if not titles:
            return 0.0
            
        positive_keywords = ['상승', '급등', '호재', '매수', '기대', '좋', '강세', '돌파', '신고가', '목표가', '상향']
        negative_keywords = ['하락', '급락', '악재', '매도', '우려', '나쁨', '약세', '폭락', '손절', '하향', '위험']
        
        pos_count = 0
        neg_count = 0
        
        for title in titles:
            t_lower = title.lower()
            pos_count += sum(1 for kw in positive_keywords if kw in t_lower)
            neg_count += sum(1 for kw in negative_keywords if kw in t_lower)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return round((pos_count - neg_count) / (pos_count + neg_count), 3)
    
    async def collect_for_stock(self, ticker: str, days: int = 30) -> Dict:
        # Increase max_pages to ensure we cover enough history even for active stocks
        # 500 pages * 20 posts = 10,000 posts. Should cover 30 days even for active stocks.
        loop = asyncio.get_running_loop()
        posts = await loop.run_in_executor(None, self.get_discussion_posts, ticker, 300, days)
        if not posts:
            return {}
        
        daily_stats = {}
        affected_dates = set()
        
        for post in posts:
            d = post['date']
            if d not in daily_stats:
                daily_stats[d] = {
                    'posts': [],
                    'views': 0,
                    'likes': 0,
                    'dislikes': 0
                }
            daily_stats[d]['posts'].append(post)
            daily_stats[d]['views'] += post['views']
            daily_stats[d]['likes'] += post['likes']
            daily_stats[d]['dislikes'] += post['dislikes']
            
        results = {}
        
        for date_str, stats in daily_stats.items():
            post_list = stats['posts']
            count = len(post_list)
            if count == 0: continue
            
            avg_views = stats['views'] // count
            total_likes = stats['likes']
            total_dislikes = stats['dislikes']
            
            like_ratio = 0.5
            if (total_likes + total_dislikes) > 0:
                like_ratio = total_likes / (total_likes + total_dislikes)
            
            titles = [p['title'] for p in post_list]
            sentiment = self.analyze_sentiment(titles)
            
            data = {
                'ticker': ticker,
                'date': date_str,
                'post_count': count,
                'avg_views': avg_views,
                'like_ratio': round(like_ratio, 3),
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
            
            results[date_str] = data
            affected_dates.add(date_str)
            
        return {'affected_dates': list(affected_dates), 'details': results}
    
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
