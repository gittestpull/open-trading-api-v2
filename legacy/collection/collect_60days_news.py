#!/usr/bin/env python3
"""
60일치 뉴스 수집 스크립트
KIS API + YouTube 통합 뉴스를 60일 기간으로 수집합니다.
"""

import asyncio
import sys
from src.api.news import NewsCollector
from src.api.database import get_database

async def main():
    if len(sys.argv) < 2:
        print("Usage: python collect_60days_news.py <ticker> [stock_name]")
        print("Example: python collect_60days_news.py 005930 삼성전자")
        sys.exit(1)
    
    ticker = sys.argv[1]
    stock_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    COLLECTION_DAYS = 60
    MAX_KIS_NEWS = 300
    MAX_YOUTUBE_VIDEOS = 100
    
    print(f"\n{'='*60}")
    print(f"📰 {COLLECTION_DAYS}일 뉴스 수집 시작")
    print(f"종목코드: {ticker}")
    print(f"종목명: {stock_name or '(자동 검색)'}")
    print('='*60)
    
    db = get_database()
    collector = NewsCollector(db)
    
    result = await collector.collect_integrated_news(
        ticker=ticker,
        stock_name=stock_name,
        days=COLLECTION_DAYS,
        max_youtube=MAX_YOUTUBE_VIDEOS,
        max_kis=MAX_KIS_NEWS
    )
    
    print(f"\n{'='*60}")
    print(f"📊 수집 결과")
    print('='*60)
    print(f"  - KIS 뉴스: {result.get('kis_count', 0)}개")
    print(f"  - YouTube: {result.get('youtube_count', 0)}개")
    print(f"  - DB 저장: {result.get('total_saved', 0)}개")
    print(f"\n✅ 완료!")

if __name__ == "__main__":
    asyncio.run(main())
