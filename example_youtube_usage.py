"""
YouTube News Collector 사용 예제
"""

from youtube_news_collector import YouTubeNewsCollector
import pandas as pd

def collect_multiple_stocks():
    """여러 종목의 뉴스를 한 번에 수집"""
    collector = YouTubeNewsCollector()
    
    stocks = ["삼성전자", "SK하이닉스", "NAVER", "카카오"]
    
    for stock in stocks:
        print(f"\n{'='*60}")
        print(f"📌 수집 중: {stock}")
        print('='*60)
        
        videos = collector.search_stock_news(
            ticker_name=stock,
            max_results=30,
            days_back=7,
            order="relevance"
        )
        
        if videos:
            print(f"✅ {stock}: {len(videos)}개 영상 수집 완료")
    
    collector.save_to_json("multi_stock_news.json")
    collector.save_to_csv("multi_stock_news.csv")
    
    print(f"\n\n{'='*60}")
    print("📊 전체 수집 통계")
    print('='*60)
    
    df = pd.DataFrame(collector.results)
    print(f"\n총 수집 영상: {len(df)}개")
    print(f"\n종목별 수집 현황:")
    print(df.groupby('ticker_name').size())
    
    print(f"\n\n조회수 Top 5:")
    top5 = df.nlargest(5, 'view_count')[['ticker_name', 'title', 'channel_title', 'view_count']]
    for idx, row in top5.iterrows():
        print(f"\n{row['ticker_name']} - {row['view_count']:,}회")
        print(f"  {row['title'][:60]}...")
        print(f"  채널: {row['channel_title']}")

def analyze_single_stock():
    """단일 종목 심층 분석"""
    collector = YouTubeNewsCollector()
    
    ticker = "테슬라"
    videos = collector.search_stock_news(
        ticker_name=ticker,
        max_results=50,
        days_back=14,
        order="viewCount",
        include_keywords=["전망", "분석", "실적"]
    )
    
    if not videos:
        print("수집된 영상이 없습니다.")
        return
    
    df = pd.DataFrame(videos)
    
    print(f"\n{'='*60}")
    print(f"📊 {ticker} 분석 리포트")
    print('='*60)
    
    print(f"\n총 영상 수: {len(df)}개")
    print(f"평균 조회수: {df['view_count'].mean():,.0f}회")
    print(f"평균 좋아요: {df['like_count'].mean():,.0f}개")
    print(f"총 조회수: {df['view_count'].sum():,.0f}회")
    
    print(f"\n\n상위 채널 (영상 수 기준):")
    top_channels = df['channel_title'].value_counts().head(5)
    for channel, count in top_channels.items():
        print(f"  {channel}: {count}개")
    
    collector.save_to_json(f"{ticker}_analysis.json")
    collector.save_to_csv(f"{ticker}_analysis.csv")

if __name__ == "__main__":
    print("=" * 60)
    print("YouTube 뉴스 수집기 - 사용 예제")
    print("=" * 60)
    
    print("\n[1] 여러 종목 수집 예제")
    collect_multiple_stocks()
    
    print("\n\n" + "=" * 60)
    print("[2] 단일 종목 심층 분석 예제")
    print("=" * 60)
    analyze_single_stock()
    
    print("\n\n✅ 모든 예제 실행 완료!")
