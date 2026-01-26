import asyncio
import sys
sys.path.insert(0, 'src')
from api import get_collector

MAJOR_STOCKS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "035720",  # 카카오
    "006400",  # 삼성SDI
    "000270",  # 기아
    "207940",  # 삼성바이오로직스
    "068270",  # 셀트리온
]

async def main():
    print("⚠️  실전 모드로 데이터 수집 시작 (is_live=True)")
    collector = get_collector(is_live=True)
    
    print(f"\n주요 {len(MAJOR_STOCKS)}개 종목 일일 데이터 수집...")
    print("="*60)
    
    result = await collector.collect_all_prices(MAJOR_STOCKS, force=True)
    print(f"\n✅ 가격: {result}")
    
    result = await collector.collect_all_investors(MAJOR_STOCKS, force=True)
    print(f"✅ 투자자: {result}")
    
    result = await collector.collect_all_short_credit(MAJOR_STOCKS, force=True)
    print(f"✅ 공매도/신용: {result}")
    
    print("\n🎉 완료!")

if __name__ == "__main__":
    asyncio.run(main())
