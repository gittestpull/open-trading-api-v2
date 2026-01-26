import asyncio
import sys
sys.path.insert(0, 'src')
from api import get_collector, get_stock_master_service

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
    collector = get_collector(is_live=False)
    
    print(f"주요 {len(MAJOR_STOCKS)}개 종목 일일 데이터 수집 시작...\n")
    print("수집 항목: 가격, 등락률, PER, PBR, 외인/기관 수급, 공매도, 신용")
    print("="*60)
    
    # 가격 + 통계 데이터 수집
    result = await collector.collect_all_prices(MAJOR_STOCKS, force=True)
    print(f"\n✅ 가격 데이터: {result}")
    
    # 투자자 수급 데이터 수집
    result = await collector.collect_all_investors(MAJOR_STOCKS, force=True)
    print(f"\n✅ 투자자 데이터: {result}")
    
    # 공매도/신용 데이터 수집
    result = await collector.collect_all_short_credit(MAJOR_STOCKS, force=True)
    print(f"\n✅ 공매도/신용 데이터: {result}")
    
    print("\n🎉 전체 수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())
