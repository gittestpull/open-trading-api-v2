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
    
    async def fetch_fundamental_data(self, ticker: str) -> Optional[Dict]:
        """네이버 금융에서 추정 실적(Forward EPS 등) 수집"""
        try:
            url = f"https://finance.naver.com/item/main.naver?code={ticker}"
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=self.headers, timeout=10))
            
            if response.status_code != 200:
                logger.debug(f"[Naver] Failed fetch fundamental {ticker}: {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Market Cap (시가총액)
            # 2. Forward EPS (추정EPS)
            
            fwd_eps = None
            
            # Find the main financial table usually in div.section.cop_analysis
            # But the quick summary is often in #content > div.section.trade_compare > ...
            # Actually, "추정EPS" is in the aside section "PER/EPS" table often.
            
            # Look for table with th "추정EPS" or "EPS(202X.XX)"
            # A robust way is looking for the dl.blind or specific class structures, 
            # but Naver HTML is old. Let's look for the specific table area "펀더멘털"
            
            # Search for the "펀더멘털" section which contains PER | EPS / EstPER | EstEPS
            # Use specific CSS selectors if possible, or text matching
            
            # Naver Finance Main page usually has:
            # <div id="tab_con1" class="tab_con1"> ... <table summary="동일업종 PER, 동일업종 등락률"> ... </table> ...
            # <table summary="시가총액, 시가총액순위, 상장주식수, 액면가, 매매단위, 외국인한도주식수(A), 외국인보유주식수(B), 외국인소진율(B/A), 투자의견, 목표주가, 52주최고, 52주최저, PER, EPS, 추정PER, 추정EPS, PBR, BPS, 배당수익률">
            
            # Try to find the "추정EPS" value directly by its label in the Summary Table
            # Usually in a table with class "lwidth" or similar inside div.assess_summary (Investment opinion)
            # Or in the side section .aside_invest_info
            
            # Let's target the right side table "PER/EPS"
            # It has rows: PER, EPS, 추정PER, 추정EPS
            
            rows = soup.select('div.aside_invest_info table tbody tr')
            for row in rows:
                th = row.select_one('th')
                if not th: continue
                label = th.get_text(strip=True)
                
                if '추정EPS' in label or 'Fwd.EPS' in label:
                    td = row.select_one('td')
                    if td:
                        val_text = td.get_text(strip=True).replace(',', '')
                        if val_text and val_text.isdigit():
                            fwd_eps = float(val_text)
                            break
                            
            if fwd_eps is not None:
                # Update DB directly here or return
                await self.db.execute("""
                    UPDATE stock_info
                    SET fwd_eps = ?, updated_at = ?
                    WHERE ticker = ?
                """, (fwd_eps, datetime.now().isoformat(), ticker))
                
                return {'fwd_eps': fwd_eps}
            
            return None
            
        except Exception as e:
            logger.debug(f"[Naver] Fundamental fetch error {ticker}: {e}")
            return None

    async def fetch_opentalk_info(self, ticker: str) -> Optional[Dict]:
        """네이버 모바일 토론방 페이지에서 오픈톡 참여자 수 수집"""
        try:
            url = f"https://m.stock.naver.com/domestic/stock/{ticker}/discussion"
            # 모바일 User-Agent 필수
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            }
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=mobile_headers, timeout=10))
            
            if response.status_code != 200:
                logger.debug(f"[Naver] Failed fetch opentalk {ticker}: {response.status_code}")
                return None
            
            # __NEXT_DATA__ JSON 파싱
            import json
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not next_data_script:
                logger.debug(f"[Naver] __NEXT_DATA__ not found for {ticker}")
                return None
                
            data = json.loads(next_data_script.string)
            
            # 경로: props -> pageProps -> dehydratedState -> queries -> [queryKey with /opentalk/channelInfo] -> state -> data -> result
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
            
            opentalk_users = None
            
            for query in queries:
                q_key = query.get('queryKey', [])
                # queryKey가 리스트이고 첫번째 요소가 dict인 경우 확인
                if q_key and isinstance(q_key, list) and isinstance(q_key[0], dict) and '/opentalk/channelInfo' in q_key[0].get('url', ''):
                    result_data = query.get('state', {}).get('data', {}).get('result', {})
                    if result_data:
                        # result가 두 번 중첩된 경우도 있음
                         if 'result' in result_data:
                             opentalk_users = result_data['result'].get('userCount')
                         else:
                             opentalk_users = result_data.get('userCount')
                    break
            
            if opentalk_users is not None and isinstance(opentalk_users, int):
                await self.db.execute("""
                    UPDATE stock_info
                    SET opentalk_users = ?, updated_at = ?
                    WHERE ticker = ?
                """, (opentalk_users, datetime.now().isoformat(), ticker))
                
                return {'opentalk_users': opentalk_users}
                
            return None
            
        except Exception as e:
            logger.debug(f"[Naver] Opentalk fetch error {ticker}: {e}")
            return None

    async def collect_batch(self, tickers: List[str], delay: float = 0.5) -> Dict:
        success = 0
        failed = 0
        
        for ticker in tickers:
            try:
                # Collect both discussion and fundamental
                res1 = await self.collect_for_stock(ticker)
                res2 = await self.fetch_fundamental_data(ticker)
                
                if res1 or res2:
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
