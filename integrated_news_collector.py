"""
Integrated News Collector
YouTube + KIS API 통합 뉴스 수집기
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth as ka

from youtube_news_collector import YouTubeNewsCollector
from stock_code_lookup import get_stock_code

class IntegratedNewsCollector:
    """YouTube와 KIS API 뉴스를 통합 수집하는 클래스"""
    
    def __init__(self):
        self.youtube_collector = YouTubeNewsCollector()
        self.kis_authenticated = False
        self.all_news = []
    
    def authenticate_kis(self):
        """KIS API 인증"""
        if not self.kis_authenticated:
            ka.auth()
            self.kis_authenticated = True
    
    def collect_kis_news(
        self,
        stock_code: str,
        days_back: int = 7,
        max_results: int = 100
    ) -> List[Dict]:
        """
        KIS API로 국내 주식 뉴스 수집
        
        Args:
            stock_code: 종목코드 (예: "005930")
            days_back: 검색 기간 (기본 7일)
            max_results: 최대 결과 수
        
        Returns:
            뉴스 리스트
        """
        self.authenticate_kis()
        
        api_url = "/uapi/domestic-stock/v1/quotations/news-title"
        tr_id = "FHKST01011800"
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        all_news = []
        current_date = end_date
        
        while current_date >= start_date and len(all_news) < max_results:
            params = {
                "FID_NEWS_OFER_ENTP_CODE": "0",
                "FID_COND_MRKT_CLS_CODE": "00",
                "FID_INPUT_ISCD": stock_code,
                "FID_TITL_CNTT": "",
                "FID_INPUT_DATE_1": current_date.strftime("%Y%m%d"),
                "FID_INPUT_HOUR_1": "235959",
                "FID_RANK_SORT_CLS_CODE": "0",
                "FID_INPUT_SRNO": ""
            }
            
            res = ka._url_fetch(api_url, tr_id, "", params)
            
            if res.isOK():
                output = res.getBody().output
                if isinstance(output, dict):
                    output = [output]
                
                if not output or len(output) == 0:
                    break
                
                df = pd.DataFrame(output)
                
                for _, row in df.iterrows():
                    news_item = {
                        'source': 'KIS',
                        'ticker_code': stock_code,
                        'ticker_name': row.get('kor_isnm1', ''),
                        'title': row['hts_pbnt_titl_cntt'],
                        'provider': row.get('dorg', ''),
                        'date': row['data_dt'],
                        'time': row['data_tm'],
                        'datetime': f"{row['data_dt']} {row['data_tm']}",
                        'news_id': row.get('cntt_usiq_srno', ''),
                        'collected_at': datetime.now().isoformat()
                    }
                    all_news.append(news_item)
                
                if 'data_dt' in df.columns and 'data_tm' in df.columns:
                    min_dt = df['data_dt'].min()
                    min_tm = df.loc[df['data_dt'] == min_dt, 'data_tm'].min()
                    min_datetime_str = f"{min_dt}{min_tm}"
                    dt_obj = datetime.strptime(min_datetime_str, "%Y%m%d%H%M%S")
                    current_date = dt_obj - timedelta(seconds=1)
                else:
                    break
            else:
                print(f"KIS API 오류: {res.getErrorMessage()}")
                break
        
        print(f"✅ KIS API: {len(all_news)}개 뉴스 수집")
        return all_news[:max_results]
    
    def collect_all_news(
        self,
        ticker: str,
        days_back: int = 7,
        max_youtube: int = 50,
        max_kis: int = 100,
        youtube_keywords: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        """
        YouTube + KIS API 통합 뉴스 수집
        
        Args:
            ticker: 종목명 또는 종목코드
            days_back: 검색 기간 (기본 7일)
            max_youtube: YouTube 최대 결과 수
            max_kis: KIS API 최대 결과 수
            youtube_keywords: YouTube 추가 키워드
        
        Returns:
            {'youtube': [...], 'kis': [...], 'all': [...]}
        """
        print(f"\n{'='*60}")
        print(f"📰 통합 뉴스 수집: {ticker}")
        print('='*60)
        
        stock_code = get_stock_code(ticker) if not ticker.isdigit() else ticker
        ticker_name = ticker if not ticker.isdigit() else None
        
        youtube_news = []
        if ticker_name:
            print(f"\n🔍 YouTube 검색 중...")
            youtube_news = self.youtube_collector.search_stock_news(
                ticker_name=ticker_name,
                max_results=max_youtube,
                days_back=days_back,
                include_keywords=youtube_keywords
            )
        
        kis_news = []
        if stock_code and stock_code != "NOT_FOUND":
            print(f"\n🔍 KIS API 검색 중 (종목코드: {stock_code})...")
            kis_news = self.collect_kis_news(
                stock_code=stock_code,
                days_back=days_back,
                max_results=max_kis
            )
        
        all_news = youtube_news + kis_news
        self.all_news.extend(all_news)
        
        print(f"\n📊 수집 완료:")
        print(f"  - YouTube: {len(youtube_news)}개")
        print(f"  - KIS API: {len(kis_news)}개")
        print(f"  - 총합: {len(all_news)}개")
        
        return {
            'youtube': youtube_news,
            'kis': kis_news,
            'all': all_news
        }
    
    def save_results(self, filename: Optional[str] = None):
        """통합 결과 저장"""
        if not self.all_news:
            print("⚠️  저장할 뉴스가 없습니다.")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integrated_news_{timestamp}"
        
        os.makedirs("data", exist_ok=True)
        
        json_file = f"data/{filename}.json"
        csv_file = f"data/{filename}.csv"
        
        import json
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.all_news, f, ensure_ascii=False, indent=2)
        
        df = pd.DataFrame(self.all_news)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        print(f"\n💾 저장 완료:")
        print(f"  - {json_file}")
        print(f"  - {csv_file}")
        
        return {'json': json_file, 'csv': csv_file}
    
    def get_summary(self) -> pd.DataFrame:
        """수집 결과 요약"""
        if not self.all_news:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.all_news)
        
        summary = {
            '총 뉴스 수': len(df),
            'YouTube 뉴스': len(df[df['source'] == 'YouTube']) if 'source' in df.columns else 0,
            'KIS 뉴스': len(df[df['source'] == 'KIS']) if 'source' in df.columns else 0
        }
        
        return pd.Series(summary)


def main():
    """CLI 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description="통합 뉴스 수집기 (YouTube + KIS)")
    parser.add_argument("ticker", help="종목명 또는 종목코드")
    parser.add_argument("--days", type=int, default=7, help="검색 기간 (기본 7일)")
    parser.add_argument("--max-youtube", type=int, default=50, help="YouTube 최대 개수")
    parser.add_argument("--max-kis", type=int, default=100, help="KIS 최대 개수")
    parser.add_argument("--keywords", nargs="+", help="YouTube 추가 키워드")
    parser.add_argument("--no-save", action="store_true", help="파일 저장 안함")
    
    args = parser.parse_args()
    
    collector = IntegratedNewsCollector()
    
    results = collector.collect_all_news(
        ticker=args.ticker,
        days_back=args.days,
        max_youtube=args.max_youtube,
        max_kis=args.max_kis,
        youtube_keywords=args.keywords
    )
    
    if results['all']:
        print(f"\n{'='*60}")
        print("📊 통합 뉴스 요약")
        print('='*60)
        
        print(f"\n{collector.get_summary()}")
        
        if results['youtube']:
            df_yt = pd.DataFrame(results['youtube'])
            print(f"\n🎬 YouTube Top 5 (조회수):")
            top5_yt = df_yt.nlargest(5, 'view_count')[['title', 'channel_title', 'view_count']]
            for idx, row in top5_yt.iterrows():
                print(f"\n  {row['view_count']:,}회 | {row['channel_title']}")
                print(f"  {row['title'][:60]}...")
        
        if results['kis']:
            df_kis = pd.DataFrame(results['kis'])
            print(f"\n📰 KIS 최신 뉴스 5개:")
            for idx, row in df_kis.head(5).iterrows():
                print(f"\n  {row['datetime']} | {row['provider']}")
                print(f"  {row['title']}")
    
    if not args.no_save and results['all']:
        collector.save_results()
    
    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
