# -*- coding: utf-8 -*-
"""
인간지표(Human Index) 수집 테스트 스크립트
- YouTube 데이터 수집 테스트
- Naver 토론방 데이터 수집 테스트
- Human Index 계산 테스트
"""
import asyncio
import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.database import get_database
from src.api.youtube import get_youtube_collector
from src.api.naver import get_naver_collector
from src.api.human_index import get_human_index_calculator

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

async def test_youtube_collector():
    """YouTube 수집 테스트"""
    print("\n" + "="*60)
    print("🎬 YouTube Collector Test")
    print("="*60)
    
    collector = get_youtube_collector()
    
    # Check API key
    if not collector.api_key:
        print("❌ YOUTUBE_API_KEY not set!")
        return False
    else:
        print(f"✅ YouTube API key found (ending with ...{collector.api_key[-4:]})")
    
    # Test search
    test_stock = "삼성전자"
    print(f"\n📹 Searching videos for: {test_stock}")
    
    videos = collector.search_videos(test_stock, max_results=5, days_back=7)
    
    if videos:
        print(f"✅ Found {len(videos)} videos")
        for v in videos[:3]:
            print(f"   - {v['title'][:50]}... (views: {v['view_count']:,})")
        return True
    else:
        print("❌ No videos found")
        return False


async def test_naver_collector():
    """Naver 토론방 수집 테스트"""
    print("\n" + "="*60)
    print("📝 Naver Discussion Collector Test")
    print("="*60)
    
    collector = get_naver_collector()
    
    # Test with Samsung Electronics (005930)
    test_ticker = "005930"
    print(f"\n🔍 Fetching posts for ticker: {test_ticker}")
    
    posts = collector.get_discussion_posts(test_ticker, max_pages=3, days_back=7)
    
    if posts:
        print(f"✅ Found {len(posts)} posts")
        for p in posts[:3]:
            print(f"   - [{p['date']}] {p['title'][:40]}... (views: {p['views']}, likes: {p['likes']})")
        return True
    else:
        print("❌ No posts found")
        return False


async def test_full_collection():
    """전체 인간지표 수집 테스트"""
    print("\n" + "="*60)
    print("🤖 Full Human Index Collection Test")
    print("="*60)
    
    calculator = get_human_index_calculator()
    
    test_ticker = "005930"  # Samsung Electronics
    test_name = "삼성전자"
    
    print(f"\n📊 Collecting human data for: {test_name} ({test_ticker})")
    print("   This may take a moment...")
    
    try:
        result = await calculator.collect_all_human_data(test_ticker, test_name, days=7)
        
        print("\n=== Collection Results ===")
        
        # YouTube result
        yt = result.get('youtube')
        if yt:
            print(f"✅ YouTube: {len(yt.get('affected_dates', []))} days of data")
        else:
            print("❌ YouTube: No data")
            
        # Naver result
        nv = result.get('naver')
        if nv:
            print(f"✅ Naver: {len(nv.get('affected_dates', []))} days of data")
        else:
            print("❌ Naver: No data")
        
        # Human index
        hi = result.get('human_index')
        if hi:
            print(f"\n📈 Latest Human Index:")
            print(f"   Date: {hi.get('date')}")
            print(f"   Attention Score: {hi.get('attention_score')}/100")
            print(f"   FOMO Level: {hi.get('fomo_level')}/100")
            print(f"   Crowd Sentiment: {hi.get('crowd_sentiment')}")
            return True
        else:
            print("❌ Human Index calculation failed")
            return False
            
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_db_tables():
    """DB 테이블 상태 확인"""
    print("\n" + "="*60)
    print("🗄️ Database Tables Check")
    print("="*60)
    
    db = get_database()
    # create_tables is already called in get_database() singleton
    
    tables = ['youtube_metrics', 'naver_discussion', 'human_index']
    
    for table in tables:
        try:
            count = await db.fetch_one(f"SELECT COUNT(*) as cnt FROM {table}")
            if count:
                print(f"✅ {table}: {count['cnt']} rows")
            else:
                print(f"⚠️ {table}: Empty")
        except Exception as e:
            print(f"❌ {table}: Error - {e}")


async def main():
    print("\n" + "#"*60)
    print("#  Human Index Collection Verification")
    print("#  인간지표 수집 확인 테스트")
    print("#"*60)
    
    results = {}
    
    # 1. Check DB
    await check_db_tables()
    
    # 2. Test YouTube
    results['youtube'] = await test_youtube_collector()
    
    # 3. Test Naver
    results['naver'] = await test_naver_collector()
    
    # 4. Test full collection
    results['full'] = await test_full_collection()
    
    # Summary
    print("\n" + "="*60)
    print("📋 SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ All tests passed! Human index collection is working.")
    else:
        print("\n❌ Some tests failed. Check the details above.")
        
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
