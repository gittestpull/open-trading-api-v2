# -*- coding: utf-8 -*-
"""
인간지표 3개월치 데이터 수집 스크립트
- 주요 종목들에 대해 Naver 토론방 데이터 수집 (90일)
- Human Index 계산 및 저장
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.database import get_database
from src.api.human_index import get_human_index_calculator

# 수집 대상 종목 (인기 종목들)
TARGET_STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035720", "카카오"),
    ("035420", "NAVER"),
    ("051910", "LG화학"),
    ("006400", "삼성SDI"),
    ("373220", "LG에너지솔루션"),
    ("207940", "삼성바이오로직스"),
    ("005380", "현대차"),
    ("000270", "기아"),
]


async def collect_3months():
    """3개월치 인간지표 수집"""
    calculator = get_human_index_calculator()
    db = get_database()
    
    print("=" * 60)
    print("🚀 3개월 인간지표 수집 시작")
    print("=" * 60)
    print(f"수집 대상: {len(TARGET_STOCKS)}개 종목")
    print(f"수집 기간: 90일")
    print()
    
    results = {}
    
    for i, (ticker, name) in enumerate(TARGET_STOCKS, 1):
        print(f"\n[{i}/{len(TARGET_STOCKS)}] {name} ({ticker}) 수집 중...")
        
        try:
            result = await calculator.collect_all_human_data(ticker, name, days=90)
            
            naver_days = 0
            if result.get('naver') and result['naver'].get('affected_dates'):
                naver_days = len(result['naver']['affected_dates'])
            
            hi = result.get('human_index')
            if hi:
                print(f"   ✅ 완료! Naver: {naver_days}일, "
                      f"관심도: {hi['attention_score']}, "
                      f"FOMO: {hi['fomo_level']}, "
                      f"감성: {hi['crowd_sentiment']}")
                results[ticker] = {"status": "success", "data": hi}
            else:
                print(f"   ⚠️ 데이터 없음")
                results[ticker] = {"status": "no_data"}
                
        except Exception as e:
            print(f"   ❌ 오류: {e}")
            results[ticker] = {"status": "error", "error": str(e)}
        
        # Rate limiting
        await asyncio.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 수집 결과")
    print("=" * 60)
    
    success = sum(1 for r in results.values() if r["status"] == "success")
    no_data = sum(1 for r in results.values() if r["status"] == "no_data")
    errors = sum(1 for r in results.values() if r["status"] == "error")
    
    print(f"✅ 성공: {success}개")
    print(f"⚠️ 데이터없음: {no_data}개")
    print(f"❌ 오류: {errors}개")
    
    # Check DB stats
    print("\n📈 데이터베이스 현황:")
    for table in ['naver_discussion', 'human_index']:
        count = await db.fetch_one(f"SELECT COUNT(*) as cnt FROM {table}")
        print(f"   {table}: {count['cnt']} rows")
    
    return results


async def main():
    results = await collect_3months()
    
    print("\n✅ 3개월 인간지표 수집 완료!")
    print("웹 서비스에서 '인간지표' 탭을 확인하세요.")
    
    return len([r for r in results.values() if r["status"] == "success"]) > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
