"""
YouTube News Collector for Stock Tickers
한국 주식 종목 관련 YouTube 뉴스/분석 영상 수집기
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

load_dotenv()

class YouTubeNewsCollector:
    """YouTube API를 활용한 종목 뉴스 수집기"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: YouTube Data API v3 키 (기본값: 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API key not found. Set YOUTUBE_API_KEY in .env file")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.results = []
    
    def search_stock_news(
        self,
        ticker_name: str,
        max_results: int = 50,
        days_back: int = 7,
        order: str = "relevance",
        include_keywords: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        종목 관련 YouTube 영상 검색
        
        Args:
            ticker_name: 종목명 (예: "삼성전자", "테슬라")
            max_results: 최대 결과 수 (기본 50개, 최대 50개)
            days_back: 검색 기간 (기본 7일)
            order: 정렬 기준 (relevance/date/viewCount/rating)
            include_keywords: 추가 검색 키워드 (예: ["전망", "분석"])
        
        Returns:
            검색된 영상 정보 리스트
        """
        query = ticker_name
        if include_keywords:
            query += " " + " ".join(include_keywords)
        
        published_after = (datetime.now() - timedelta(days=days_back)).isoformat() + "Z"
        
        try:
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                type='video',
                maxResults=min(max_results, 50),
                order=order,
                publishedAfter=published_after,
                regionCode='KR',
                relevanceLanguage='ko'
            ).execute()
            
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
            if not video_ids:
                print(f"No videos found for '{ticker_name}'")
                return []
            
            videos_response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            collected_videos = []
            for video in videos_response.get('items', []):
                video_data = self._parse_video_data(video, ticker_name)
                collected_videos.append(video_data)
                self.results.append(video_data)
            
            print(f"✅ Collected {len(collected_videos)} videos for '{ticker_name}'")
            return collected_videos
            
        except HttpError as e:
            print(f"❌ YouTube API Error: {e}")
            return []
    
    def _parse_video_data(self, video: Dict, ticker_name: str) -> Dict:
        """비디오 데이터 파싱"""
        snippet = video['snippet']
        statistics = video.get('statistics', {})
        
        return {
            'ticker_name': ticker_name,
            'video_id': video['id'],
            'title': snippet['title'],
            'description': snippet['description'][:500],
            'channel_title': snippet['channelTitle'],
            'published_at': snippet['publishedAt'],
            'view_count': int(statistics.get('viewCount', 0)),
            'like_count': int(statistics.get('likeCount', 0)),
            'comment_count': int(statistics.get('commentCount', 0)),
            'url': f"https://www.youtube.com/watch?v={video['id']}",
            'thumbnail': snippet['thumbnails']['high']['url'],
            'collected_at': datetime.now().isoformat()
        }
    
    def save_to_json(self, filename: Optional[str] = None) -> str:
        """JSON 파일로 저장"""
        if not self.results:
            print("⚠️  No data to save")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_news_{timestamp}.json"
        
        filepath = os.path.join("data", filename)
        os.makedirs("data", exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Saved {len(self.results)} videos to {filepath}")
        return filepath
    
    def save_to_csv(self, filename: Optional[str] = None) -> str:
        """CSV 파일로 저장"""
        if not self.results:
            print("⚠️  No data to save")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_news_{timestamp}.csv"
        
        filepath = os.path.join("data", filename)
        os.makedirs("data", exist_ok=True)
        
        df = pd.DataFrame(self.results)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"💾 Saved {len(self.results)} videos to {filepath}")
        return filepath
    
    def get_top_videos(self, top_n: int = 10, sort_by: str = "view_count") -> pd.DataFrame:
        """상위 N개 영상 조회"""
        if not self.results:
            print("⚠️  No data collected yet")
            return pd.DataFrame()
        
        df = pd.DataFrame(self.results)
        return df.sort_values(by=sort_by, ascending=False).head(top_n)
    
    def clear_results(self):
        """수집 결과 초기화"""
        self.results = []


def main():
    """CLI 실행 예제"""
    import argparse
    
    parser = argparse.ArgumentParser(description="YouTube Stock News Collector")
    parser.add_argument("ticker", help="종목명 (예: 삼성전자, 테슬라)")
    parser.add_argument("--max-results", type=int, default=50, help="최대 수집 개수 (기본 50)")
    parser.add_argument("--days", type=int, default=7, help="검색 기간 (기본 7일)")
    parser.add_argument("--keywords", nargs="+", help="추가 검색 키워드 (예: 전망 분석)")
    parser.add_argument("--order", default="relevance", choices=["relevance", "date", "viewCount", "rating"])
    parser.add_argument("--top", type=int, default=10, help="상위 N개 출력 (기본 10)")
    parser.add_argument("--no-save", action="store_true", help="파일 저장 안함")
    
    args = parser.parse_args()
    
    collector = YouTubeNewsCollector()
    
    print(f"\n🔍 Searching YouTube for '{args.ticker}'...")
    videos = collector.search_stock_news(
        ticker_name=args.ticker,
        max_results=args.max_results,
        days_back=args.days,
        order=args.order,
        include_keywords=args.keywords
    )
    
    if not videos:
        print("No results found.")
        return
    
    print(f"\n📊 Top {args.top} Videos by View Count:")
    top_videos = collector.get_top_videos(top_n=args.top, sort_by="view_count")
    
    for idx, row in top_videos.iterrows():
        print(f"\n[{idx+1}] {row['title']}")
        print(f"    채널: {row['channel_title']}")
        print(f"    조회수: {row['view_count']:,} | 좋아요: {row['like_count']:,}")
        print(f"    URL: {row['url']}")
    
    if not args.no_save:
        print("\n💾 Saving results...")
        collector.save_to_json()
        collector.save_to_csv()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
