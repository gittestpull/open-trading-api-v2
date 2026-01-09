"""
Stock Cache Module
전체 종목 리스트를 캐싱하고 로컬에서 필터링하는 모듈

- KOSPI + KOSDAQ 전체 종목 (~3,700개) 캐싱
- 네이버 금융에서 시세 데이터 수집
- 5분마다 백그라운드 갱신
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import urllib.request
import json
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class StockData:
    """개별 종목 데이터
    
    [누가] 네이버 금융에서 수집
    [무엇을] 종목 시세 및 재무 정보
    [언제] 5분마다 자동 갱신
    [어디서] finance.naver.com
    """
    code: str
    name: str
    market: str  # 'kospi' or 'kosdaq'
    price: int = 0
    change_rate: float = 0.0
    volume: int = 0
    market_cap: int = 0
    per: float = 0.0
    # 추가 재무 데이터 (현재 수집 미구현 - 추후 확장 예정)
    op_rate: float = 0.0       # 영업이익률 (%)
    debt_rate: float = 0.0     # 부채비율 (%)
    rsrv_rate: float = 0.0     # 유보율 (%)
    rsi: int = 0               # RSI (14일 기준)
    sector: str = ''           # 업종
    trend_ok: bool = False     # 추세 돌파 여부
    updated_at: Optional[datetime] = None


class StockCache:
    """전체 종목 캐시 매니저"""
    
    def __init__(self):
        self.stocks: Dict[str, StockData] = {}
        self.last_update: Optional[datetime] = None
        self.is_updating: bool = False
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=10)
        
    def _get_naver_stock_list(self, market: str) -> List[Dict]:
        """네이버 금융에서 전체 종목 리스트 가져오기 (시가총액 페이지 활용)"""
        stocks = []
        
        # sosok: 0 = KOSPI, 1 = KOSDAQ
        sosok = "0" if market == "kospi" else "1"
        page = 1
        max_pages = 50  # 보통 코스피/코스닥 각각 40~50페이지
        
        while page <= max_pages:
            url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
            
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    # Naver uses EUC-KR
                    html = response.read().decode('euc-kr', errors='ignore')
                
                # <tr> 태그 단위로 분할하여 각 종목 파싱
                # KIS API처럼 정확하진 않지만 전체 종목 데이터를 긁어오기에 적합
                rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
                
                page_has_data = False
                for row in rows:
                    # 종목 코드와 이름 찾기
                    code_match = re.search(r'href="/item/main\.naver\?code=(\d{6})"[^>]*class="tltle"[^>]*>([^<]+)</a>', row)
                    if not code_match:
                        continue
                    
                    code = code_match.group(1)
                    name = code_match.group(2).strip()
                    page_has_data = True
                    
                    # 수치 데이터 (td.number) 추출
                    # 1:현재가, 2:전일비, 3:등락률, 4:액면가, 5:시가총액, 6:상장주식수, 7:외인비율, 8:거래량, 9:PER, 10:ROE
                    # 실제 HTML 구조에 따라 인덱스가 다를 수 있으므로 td를 모두 뽑아서 분석
                    td_numbers = re.findall(r'<td[^>]*class="number"[^>]*>(.*?)</td>', row, re.DOTALL)
                    
                    price = 0
                    change_rate = 0.0
                    volume = 0
                    per = 0.0
                    
                    if len(td_numbers) >= 8:
                        # 현재가는 첫 번째 td.number
                        price_str = re.sub(r'[^0-9]', '', td_numbers[0])
                        price = int(price_str) if price_str else 0
                        
                        # 등락률은 세 번째 td.number 안의 span 등
                        rate_match = re.search(r'([+-]?\d+\.\d+)%', td_numbers[2])
                        change_rate = float(rate_match.group(1)) if rate_match else 0.0
                        
                        # 거래량은 보통 10번째 근처 (네이버 설정에 따라 다름)
                        # 기본 설정 상으로는 상장주식수(7), 외인비율(8), 거래량(9) 정도 위치
                        # "거래량" 필드가 포함된 td를 찾기 위해 역순 탐색이나 인덱스 확인
                        # 하지만 가장 확실한 건 수치가 큰 필드(상장주식수, 거래량) 중 하나임
                        
                        # 기본 페이지 구조상 10번째 td가 거래량일 가능성이 높음 (N, 이름, 현재가, 전일비, 등락률, 액면가, 시가총액, 상장주식수, 외인비율, 거래량)
                        # regex로 td만 다 뽑으면:
                        all_tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                        if len(all_tds) >= 11:
                            volume_str = re.sub(r'[^0-9]', '', all_tds[10]) # 10번 인덱스가 거래량
                            volume = int(volume_str) if volume_str else 0
                        
                        # PER은 11번 인덱스
                        if len(all_tds) >= 12:
                            per_str = re.sub(r'[^0-9.]', '', all_tds[11])
                            per = float(per_str) if per_str else 0.0

                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                        'price': price,
                        'change_rate': change_rate,
                        'volume': volume,
                        'per': per
                    })
                
                if not page_has_data:
                    break
                    
                # 다음 페이지 버튼 있는지 확인
                if f'page={page + 1}' not in html:
                    break
                    
                page += 1
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Failed to fetch {market} page {page}: {e}")
                break
                
        logger.info(f"Fetched {len(stocks)} stocks from {market}")
        return stocks


    
    def _get_stock_per(self, code: str) -> float:
        """네이버에서 개별 종목 PER 조회"""
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=5) as response:
                html = response.read().decode('euc-kr', errors='ignore')
                
            # PER 파싱
            match = re.search(r'PER.*?<em>([0-9,.]+)</em>', html, re.DOTALL)
            if match:
                return float(match.group(1).replace(',', ''))
        except:
            pass
        return 0.0
    
    async def update_cache(self, include_per: bool = False) -> int:
        """캐시 갱신 (전체 종목 데이터 수집)"""
        if self.is_updating:
            logger.warning("Cache update already in progress")
            return 0
            
        async with self._lock:
            self.is_updating = True
            
        try:
            logger.info("Starting stock cache update...")
            start_time = time.time()
            
            # KOSPI + KOSDAQ 병렬 수집
            loop = asyncio.get_event_loop()
            kospi_task = loop.run_in_executor(
                self._executor, self._get_naver_stock_list, "kospi"
            )
            kosdaq_task = loop.run_in_executor(
                self._executor, self._get_naver_stock_list, "kosdaq"
            )
            
            kospi_stocks, kosdaq_stocks = await asyncio.gather(kospi_task, kosdaq_task)
            
            # 캐시 업데이트
            new_stocks = {}
            now = datetime.now()
            
            for stock in kospi_stocks + kosdaq_stocks:
                new_stocks[stock['code']] = StockData(
                    code=stock['code'],
                    name=stock['name'],
                    market=stock['market'],
                    price=stock['price'],
                    change_rate=stock['change_rate'],
                    volume=stock['volume'],
                    per=0.0,  # PER은 필요시 개별 조회
                    updated_at=now
                )
            
            self.stocks = new_stocks
            self.last_update = now
            
            elapsed = time.time() - start_time
            logger.info(f"Cache updated: {len(self.stocks)} stocks in {elapsed:.1f}s")
            
            return len(self.stocks)
            
        except Exception as e:
            logger.error(f"Cache update failed: {e}")
            return 0
        finally:
            self.is_updating = False
    
    def filter_stocks(
        self,
        min_volume: int = 0,
        max_per: float = 9999,
        min_change_rate: float = -100,
        max_change_rate: float = 100,
        market: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """캐시된 데이터에서 조건 필터링
        
        [누가] StockCache 시스템
        [무엇을] 조건에 맞는 종목 필터링
        [언제] API 호출 시 실시간
        [어디서] 메모리 캐시 데이터
        """
        results = []
        
        for code, stock in self.stocks.items():
            # 필터 적용
            if stock.volume < min_volume:
                continue
            if stock.per > 0 and stock.per > max_per:
                continue
            if stock.change_rate < min_change_rate or stock.change_rate > max_change_rate:
                continue
            if market and stock.market != market:
                continue
                
            results.append({
                'code': stock.code,
                'ticker': stock.code,
                'name': stock.name,
                'market': stock.market,
                'price': stock.price,
                'change_rate': stock.change_rate,
                'volume': stock.volume,
                'per': stock.per if stock.per > 0 else None,
                # 재무 데이터 (현재 수집 중 - 일부 종목은 값이 없을 수 있음)
                'op_rate': stock.op_rate if stock.op_rate != 0 else None,
                'debt_rate': stock.debt_rate if stock.debt_rate != 0 else None,
                'rsrv_rate': stock.rsrv_rate if stock.rsrv_rate != 0 else None,
                'rsi': stock.rsi if stock.rsi != 0 else None,
                'sector': stock.sector or None,
                'trend_ok': stock.trend_ok,
                'updated_at': stock.updated_at.isoformat() if stock.updated_at else None,
                # 데이터 수집 상태 안내
                '_data_status': {
                    'per': '수집됨' if stock.per > 0 else '미수집 (네이버 금융 개별 조회 필요)',
                    'op_rate': '수집됨' if stock.op_rate != 0 else '미구현 (향후 확장 예정)',
                    'debt_rate': '수집됨' if stock.debt_rate != 0 else '미구현 (향후 확장 예정)',
                    'rsrv_rate': '수집됨' if stock.rsrv_rate != 0 else '미구현 (향후 확장 예정)',
                    'rsi': '수집됨' if stock.rsi != 0 else '미구현 (향후 확장 예정)',
                }
            })
        
        # 거래량 순 정렬
        results.sort(key=lambda x: x['volume'], reverse=True)
        
        return results[:limit]
    
    def get_stock(self, code: str) -> Optional[Dict[str, Any]]:
        """개별 종목 조회"""
        stock = self.stocks.get(code)
        if stock:
            return {
                'code': stock.code,
                'ticker': stock.code,
                'name': stock.name,
                'market': stock.market,
                'price': stock.price,
                'change_rate': stock.change_rate,
                'volume': stock.volume,
                'per': stock.per
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            'total_stocks': len(self.stocks),
            'kospi_count': sum(1 for s in self.stocks.values() if s.market == 'kospi'),
            'kosdaq_count': sum(1 for s in self.stocks.values() if s.market == 'kosdaq'),
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'is_updating': self.is_updating
        }


# 전역 싱글톤 인스턴스
_stock_cache: Optional[StockCache] = None


def get_stock_cache() -> StockCache:
    """전역 StockCache 인스턴스 반환"""
    global _stock_cache
    if _stock_cache is None:
        _stock_cache = StockCache()
    return _stock_cache


async def start_cache_refresh_task(interval_minutes: int = 5):
    """백그라운드 캐시 갱신 태스크"""
    cache = get_stock_cache()
    
    # 초기 로드
    await cache.update_cache()
    
    # 주기적 갱신
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            await cache.update_cache()
        except Exception as e:
            logger.error(f"Background cache refresh failed: {e}")
