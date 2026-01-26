import asyncio
import sys
import time
sys.path.insert(0, 'src')
from api import get_collector, get_stock_master_service

async def main():
    print("=" * 60)
    print("전체 종목 데이터 수집 시작")
    print("=" * 60)
    
    stock_service = get_stock_master_service()
    collector = get_collector(is_live=True)
    
    all_tickers = await stock_service.get_all_tickers()
    total = len(all_tickers)
    
    print(f"\n총 {total}개 종목 수집 예정")
    print(f"예상 소요 시간: 약 {total * 0.6 / 60:.0f}분")
    print("\n진행 상황:")
    print("-" * 60)
    
    batch_size = 100
    for i in range(0, total, batch_size):
        batch = all_tickers[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"\n[Batch {batch_num}/{total_batches}] {len(batch)}개 종목 수집 중...")
        
        # 가격 데이터
        result = await collector.collect_all_prices(batch, force=False)
        print(f"  가격: {result['success']}/{result['total']} 성공")
        
        # 투자자 데이터
        result = await collector.collect_all_investors(batch, force=False)
        print(f"  투자자: {result['success']}/{result['total']} 성공")
        
        # 공매도/신용 데이터
        result = await collector.collect_all_short_credit(batch, force=False)
        print(f"  공매도/신용: {result['success']}/{result['total']} 성공")
        
        progress = ((i + len(batch)) / total) * 100
        print(f"  진행률: {progress:.1f}% ({i + len(batch)}/{total})")
        
        # API 과부하 방지를 위한 대기
        if i + batch_size < total:
            print(f"  다음 배치까지 5초 대기...")
            await asyncio.sleep(5)
    
    print("\n" + "=" * 60)
    print("🎉 전체 수집 완료!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
