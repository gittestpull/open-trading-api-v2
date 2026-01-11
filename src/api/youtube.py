# -*- coding: utf-8 -*-
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re

try:
    from googleapiclient.discovery import build
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

from .database import Database, get_database

logger = logging.getLogger(__name__)


class YouTubeCollector:
    
    def __init__(self, api_key: str = None, db: Database = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.db = db or get_database()
        self._youtube = None
    
    def _get_client(self):
        if not YOUTUBE_AVAILABLE:
            logger.warning("[YouTube] googleapiclient not installed")
            return None
        if not self.api_key:
            logger.warning("[YouTube] API key not set")
            return None
        if self._youtube is None:
            self._youtube = build('youtube', 'v3', developerKey=self.api_key)
        return self._youtube
    
    def search_videos(self, query: str, max_results: int = 10, days_back: int = 7) -> List[Dict]:
        youtube = self._get_client()
        if not youtube:
            return []
        
        try:
            published_after = (datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'
            
            request = youtube.search().list(
                part='snippet',
                q=f'{query} 주식',
                type='video',
                order='viewCount',
                publishedAfter=published_after,
                maxResults=max_results,
                regionCode='KR',
                relevanceLanguage='ko'
            )
            response = request.execute()
            
            videos = []
            video_ids = [item['id']['videoId'] for item in response.get('items', [])]
            
            if video_ids:
                stats_request = youtube.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)
                )
                stats_response = stats_request.execute()
                
                for item in stats_response.get('items', []):
                    stats = item.get('statistics', {})
                    snippet = item.get('snippet', {})
                    videos.append({
                        'video_id': item['id'],
                        'title': snippet.get('title', ''),
                        'channel': snippet.get('channelTitle', ''),
                        'published_at': snippet.get('publishedAt', ''),
                        'view_count': int(stats.get('viewCount', 0)),
                        'like_count': int(stats.get('likeCount', 0)),
                        'comment_count': int(stats.get('commentCount', 0)),
                    })
            
            return videos
        except Exception as e:
            logger.error(f"[YouTube] Search failed: {e}")
            return []
    
    def analyze_sentiment(self, videos: List[Dict]) -> float:
        if not videos:
            return 0.0
        
        positive_keywords = ['상승', '급등', '호재', '매수', '기대', '좋은', '강세', '돌파', '신고가']
        negative_keywords = ['하락', '급락', '악재', '매도', '우려', '나쁜', '약세', '폭락', '손절']
        
        total_score = 0
        total_weight = 0
        
        for video in videos:
            title = video.get('title', '').lower()
            view_count = video.get('view_count', 1)
            weight = min(view_count / 10000, 10)
            
            pos_count = sum(1 for kw in positive_keywords if kw in title)
            neg_count = sum(1 for kw in negative_keywords if kw in title)
            
            if pos_count + neg_count > 0:
                score = (pos_count - neg_count) / (pos_count + neg_count)
                total_score += score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    async def collect_for_stock(self, ticker: str, stock_name: str) -> Optional[Dict]:
        videos = self.search_videos(stock_name, max_results=20, days_back=7)
        
        if not videos:
            return None
        
        sentiment = self.analyze_sentiment(videos)
        total_views = sum(v.get('view_count', 0) for v in videos)
        avg_likes = sum(v.get('like_count', 0) for v in videos) // len(videos) if videos else 0
        
        data = {
            'ticker': ticker,
            'date': datetime.now().strftime("%Y-%m-%d"),
            'video_count': len(videos),
            'total_views': total_views,
            'avg_likes': avg_likes,
            'sentiment_score': round(sentiment, 3)
        }
        
        await self.db.execute("""
            INSERT INTO youtube_metrics (date, ticker, video_count, total_views, avg_likes, sentiment_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                video_count = excluded.video_count,
                total_views = excluded.total_views,
                avg_likes = excluded.avg_likes,
                sentiment_score = excluded.sentiment_score
        """, (data['date'], data['ticker'], data['video_count'], data['total_views'], 
              data['avg_likes'], data['sentiment_score']))
        
        return data
    
    async def collect_batch(self, stocks: List[Dict], delay: float = 1.0) -> Dict:
        success = 0
        failed = 0
        
        for stock in stocks:
            try:
                result = await self.collect_for_stock(stock['ticker'], stock['name'])
                if result:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.debug(f"[YouTube] {stock['ticker']} failed: {e}")
                failed += 1
            
            await asyncio.sleep(delay)
        
        return {'success': success, 'failed': failed}


_youtube_instance: Optional[YouTubeCollector] = None

def get_youtube_collector() -> YouTubeCollector:
    global _youtube_instance
    if _youtube_instance is None:
        _youtube_instance = YouTubeCollector()
    return _youtube_instance
