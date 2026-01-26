import asyncio
import sys
sys.path.insert(0, 'src')
from api import get_stock_master_service, get_human_index_calculator

async def main():
    stock_service = get_stock_master_service()
    human_index = get_human_index_calculator()
    
    print("Top 50 시가총액 종목 데이터 수집 시작...")
    stocks = await stock_service.get_top_stocks_by_market_cap(limit=50)
    
    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        name = stock['name']
        print(f"\n[{idx}/50] {name}({ticker}) 수집 중...")
        try:
            await human_index.collect_all_human_data(ticker, name, days=7)
            print(f"  ✅ 완료")
        except Exception as e:
            print(f"  ❌ 실패: {e}")
    
    print("\n🎉 전체 수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())
