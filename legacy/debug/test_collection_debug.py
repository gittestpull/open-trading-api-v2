import sys
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test")

# 경로 설정
sys.path.append(os.getcwd())

from src.api.collector import DataCollector

def test():
    # is_live=True로 설정 (run_web.py와 동일하게)
    collector = DataCollector(is_live=True)
    logger.info("Testing price collection for Samsung Electronics (005930)...")
    
    # KIS 초기화 테스트
    logger.info("Initializing KIS...")
    if not collector._init_kis():
        logger.error("KIS Init failed")
        return

    # 가격 수집 테스트
    logger.info("Collecting price...")
    price = collector.collect_price_sync("005930")
    if price:
        logger.info(f"Price success: {price}")
    else:
        logger.error("Price failed")

    # 수급 수집 테스트
    logger.info("Collecting investor data...")
    investor = collector.collect_investor_sync("005930")
    if investor:
        logger.info(f"Investor success: {investor}")
    else:
        logger.error("Investor failed")

if __name__ == "__main__":
    test()
