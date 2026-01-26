import asyncio
import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .database import Database, get_database

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.collectors.integrated_news import IntegratedNewsCollector

logger = logging.getLogger(__name__)


class NewsCollector:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.integrated_collector = IntegratedNewsCollector()
    
    def get_news(self, ticker: str, max_pages: int = 10, days_back: int = 30) -> List[Dict]:
        try:
            news_list = []
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            for page in range(1, max_pages + 1):
                url = f"https://finance.naver.com/item/news_news.naver?code={ticker}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                rows = soup.select('table.type5 tbody tr')
                
                if not rows:
                    break
                    
                page_news = []
                stop_collection = False
                
                for row in rows:
                    title_elem = row.select_one('td.title a')
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    link = "https://finance.naver.com" + title_elem['href']
                    
                    date_elem = row.select_one('td.date')
                    if date_elem:
                        date_raw = date_elem.get_text(strip=True)
                        if len(date_raw) >= 10:
                            date_str = date_raw[:10].replace('.', '-')
                            datetime_str = date_raw.replace('.', '-')
                        else:
                            date_str = datetime.now().strftime("%Y-%m-%d")
                            datetime_str = date_str + " 00:00"
                    else:
                        date_str = datetime.now().strftime("%Y-%m-%d")
                        datetime_str = date_str + " 00:00"
                        
                    provider_elem = row.select_one('td.info')
                    provider = provider_elem.get_text(strip=True) if provider_elem else "Naver"

                    if date_str < cutoff_date:
                        stop_collection = True
                        break

                    page_news.append({
                        'title': title,
                        'link': link,
                        'date': date_str,
                        'datetime': datetime_str,
                        'provider': provider
                    })
                
                if not page_news:
                    break
                    
                news_list.extend(page_news)
                
                if stop_collection:
                    break
                
                if page % 5 == 0:
                     asyncio.sleep(0.2)
            
            return news_list
            
        except Exception as e:
            logger.debug(f"[News] Failed to fetch news for {ticker}: {e}")
            return []

    def analyze_sentiment(self, titles: List[str]) -> float:
        if not titles:
            return 0.0
            
        positive_keywords = ['상승', '급등', '호재', '매수', '기대', '좋', '강세', '돌파', '신고가', '목표가', '상향', '흑자', '성장', '최대']
        negative_keywords = ['하락', '급락', '악재', '매도', '우려', '나쁨', '약세', '폭락', '손절', '하향', '위험', '적자', '감소', '최저']
        
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
        loop = asyncio.get_running_loop()
        news_items = await loop.run_in_executor(None, self.get_news, ticker, 20, days)
        
        if not news_items:
            return {}
        
        daily_stats = {}
        affected_dates = set()
        
        for item in news_items:
            d = item['date']
            if d not in daily_stats:
                daily_stats[d] = {
                    'news': [],
                    'count': 0
                }
            daily_stats[d]['news'].append(item)
            daily_stats[d]['count'] += 1
            
            await self.db.execute("""
                INSERT INTO stock_news (ticker, date, datetime, title, link, provider)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, link) DO NOTHING
            """, (ticker, d, item['datetime'], item['title'], item['link'], item['provider']))
            
        results = {}
        
        for date_str, stats in daily_stats.items():
            news_list = stats['news']
            count = stats['count']
            
            titles = [n['title'] for n in news_list]
            sentiment = self.analyze_sentiment(titles)
            
            data = {
                'ticker': ticker,
                'date': date_str,
                'news_count': count,
                'sentiment_score': sentiment
            }
            
            await self.db.execute("""
                INSERT INTO news_metrics (date, ticker, news_count, sentiment_score)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    news_count = excluded.news_count,
                    sentiment_score = excluded.sentiment_score
            """, (data['date'], data['ticker'], data['news_count'], data['sentiment_score']))
            
            results[date_str] = data
            affected_dates.add(date_str)
            
        return {'affected_dates': list(affected_dates), 'details': results}


    async def collect_integrated_news(self, ticker: str, stock_name: str, days: int = 7, max_youtube: int = 50, max_kis: int = 200) -> Dict:
        """
        KIS API + YouTube 통합 뉴스 수집 및 DB 저장
        
        Args:
            ticker: 종목코드
            stock_name: 종목명
            days: 수집 기간 (기본 7일)
            max_youtube: YouTube 최대 수집 개수 (기본 50개)
            max_kis: KIS API 최대 수집 개수 (기본 200개, 60일 기준)
        """
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self.integrated_collector.collect_all_news,
                stock_name if stock_name else ticker,
                days,
                max_youtube,
                max_kis,
                ["전망", "분석"]
            )
            
            kis_news = result.get('kis', [])
            youtube_news = result.get('youtube', [])
            
            saved_count = 0
            
            for item in kis_news:
                await self.db.execute("""
                    INSERT INTO stock_news (ticker, date, datetime, title, source, provider)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, link) DO NOTHING
                """, (
                    ticker,
                    item.get('date', ''),
                    item.get('datetime', ''),
                    item.get('title', ''),
                    'KIS',
                    item.get('provider', 'KIS')
                ))
                saved_count += 1
            
            for item in youtube_news:
                youtube_date = item.get('published_at', '')[:10] if item.get('published_at') else ''
                await self.db.execute("""
                    INSERT INTO stock_news (ticker, date, datetime, title, url, link, source, provider, content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, link) DO UPDATE SET
                        datetime = excluded.datetime,
                        content = excluded.content
                """, (
                    ticker,
                    youtube_date,
                    item.get('published_at', ''),
                    item.get('title', ''),
                    item.get('url', ''),
                    item.get('url', ''),
                    'YouTube',
                    item.get('channel_title', ''),
                    item.get('description', '')[:500]
                ))
                saved_count += 1
            
            logger.info(f"[IntegratedNews] {ticker}: KIS={len(kis_news)}, YouTube={len(youtube_news)}, Saved={saved_count}")
            
            return {
                'ticker': ticker,
                'kis_count': len(kis_news),
                'youtube_count': len(youtube_news),
                'total_saved': saved_count
            }
            
        except Exception as e:
            logger.error(f"[IntegratedNews] Failed for {ticker}: {e}")
            return {}


_news_instance: Optional[NewsCollector] = None

def get_news_collector() -> NewsCollector:
    global _news_instance
    if _news_instance is None:
        _news_instance = NewsCollector()
    return _news_instance
