import asyncio
import sys
sys.path.insert(0, 'src')
from api import get_human_index_calculator

MAJOR_STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035420", "NAVER"),
    ("005380", "현대차"),
    ("051910", "LG화학"),
    ("035720", "카카오"),
    ("006400", "삼성SDI"),
    ("000270", "기아"),
    ("207940", "삼성바이오로직스"),
    ("068270", "셀트리온"),
    ("105560", "KB금융"),
    ("055550", "신한지주"),
    ("012330", "현대모비스"),
    ("096770", "SK이노베이션"),
    ("028260", "삼성물산"),
    ("066570", "LG전자"),
    ("003550", "LG"),
    ("017670", "SK텔레콤"),
    ("034020", "두산에너빌리티"),
    ("032830", "삼성생명"),
]

async def main():
    human_index = get_human_index_calculator()
    
    print(f"주요 {len(MAJOR_STOCKS)}개 종목 데이터 수집 시작...\n")
    
    for idx, (ticker, name) in enumerate(MAJOR_STOCKS, 1):
        print(f"[{idx}/{len(MAJOR_STOCKS)}] {name}({ticker}) 수집 중...", flush=True)
        try:
            result = await human_index.collect_all_human_data(ticker, name, days=7)
            print(f"  ✅ 완료: {result.get('collected', False)}")
        except Exception as e:
            print(f"  ❌ 실패: {e}")
    
    print("\n🎉 전체 수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())
