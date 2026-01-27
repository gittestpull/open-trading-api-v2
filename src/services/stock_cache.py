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
import os
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import urllib.request
import json
import re
from concurrent.futures import ThreadPoolExecutor
import numpy as np

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
    pbr: float = 0.0           # PBR (주가순자산비율)
    rsi: int = 0               # RSI (14일 기준)
    sector: str = ''           # 업종
    trend_ok: bool = False     # 추세 돌파 여부
    updated_at: Optional[datetime] = None


class StockCache:
    """전체 종목 캐시 매니저
    
    [누가] StockCache 시스템
    [무엇을] KOSPI+KOSDAQ 전체 종목 시세 및 재무 데이터 캐싱
    [언제] 서버 시작 시 + 5분마다 자동 갱신
    [어디서] 네이버 금융에서 수집
    """
    
    def __init__(self):
        self.stocks: Dict[str, StockData] = {}
        self.last_update: Optional[datetime] = None
        self.is_updating: bool = False
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=20)  # 병렬 수집 증가
        
        # 진행률 추적
        self.collection_progress = {
            'step': '',           # 현재 단계
            'current': 0,         # 현재까지 수집된 수
            'total': 0,           # 전체 대상 수
            'message': '',        # 상세 메시지
            'started_at': None,   # 수집 시작 시간
            'errors': 0,          # 에러 수
        }
        
        # Load cache from file if available
        self.load_cache()
    
    def get_progress(self) -> dict:
        """수집 진행률 반환
        
        [누가] UI에서 폴링
        [무엇을] 현재 수집 진행 상황
        [언제] 실시간
        """
        progress = self.collection_progress.copy()
        if progress['total'] > 0:
            progress['percent'] = round(progress['current'] / progress['total'] * 100, 1)
        else:
            progress['percent'] = 0
        progress['is_updating'] = self.is_updating
        return progress

    def _fetch_html(self, url: str) -> str:
        """URL에서 HTML 가져오기 (EUC-KR / UTF-8 자동 감지)"""
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                # Naver Finance usually uses EUC-KR
                try:
                    return data.decode('euc-kr')
                except (UnicodeDecodeError, LookupError):
                    return data.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise

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
                html = self._fetch_html(url)
                
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
                    market_cap = 0
                    per = 0.0
                    
                    if len(td_numbers) >= 8:
                        # 현재가는 첫 번째 td.number
                        price_str = re.sub(r'[^0-9]', '', td_numbers[0])
                        price = int(price_str) if price_str else 0
                        
                        # 등락률은 세 번째 td.number 안의 span 등
                        rate_match = re.search(r'([+-]?\d+\.\d+)%', td_numbers[2])
                        change_rate = float(rate_match.group(1)) if rate_match else 0.0
                        
                        # 시가총액 (보통 6번째 td.number - N, Name 제외하고 숫자만 쳤을때)
                        # 하지만 td.number만 뽑으면 순서가 꼬일 수 있음. all_tds로 접근 권장.
                        
                        # 전체 td 추출 (HTML 순서대로)
                        # 0:N, 1:Name, 2:Price, 3:Diff, 4:Rate, 5:Face, 6:MarketCap, 7:Listed, 8:Foreign, 9:Volume, 10:PER, 11:ROE
                        all_tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                        
                        if len(all_tds) >= 10:
                            # Market Cap (Index 6)
                            mcap_str = re.sub(r'[^0-9]', '', all_tds[6])
                            if mcap_str:
                                # 억 단위인가? 네이버 시총은 '억원' 단위로 표기됨.
                                # 그냥 숫자 그대로 저장 (보통 조 단위는 앞자리에 콤마)
                                # 예: 8,228,297 -> 8228297
                                # StockData에는 int로 저장.
                                market_cap = int(mcap_str)

                            # Volume (Index 9)
                            vol_str = re.sub(r'[^0-9]', '', all_tds[9])
                            volume = int(vol_str) if vol_str else 0
                            
                            # PER (Index 10)
                            # N/A인 경우도 있음
                            per_text = re.sub(r'<[^>]+>', '', all_tds[10]).strip()
                            if per_text and per_text != 'N/A':
                                try:
                                    per = float(per_text.replace(',', ''))
                                except (UnicodeDecodeError, LookupError):
                                    per = 0.0

                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                        'price': price,
                        'change_rate': change_rate,
                        'volume': volume,
                        'market_cap': market_cap,
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
            html = self._fetch_html(url)
                
            # PER 파싱
            match = re.search(r'PER.*?<em>([0-9,.]+)</em>', html, re.DOTALL)
            if match:
                return float(match.group(1).replace(',', ''))
        except Exception:
            pass
        return 0.0
    
    async def update_cache(self, include_per: bool = False, include_financials: bool = True) -> int:
        """캐시 갱신 (전체 종목 데이터 수집)
        
        [누가] StockCache 백그라운드 태스크
        [무엇을] KOSPI+KOSDAQ 전체 종목 시세 수집
        [언제] 서버 시작 시 + 5분마다
        [어디서] 네이버 금융 (기본) + KIS API (재무)
        [왜] 스크리너 필터링용 캐시 데이터
        """
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
            
            all_stocks = kospi_stocks + kosdaq_stocks
            self.collection_progress['step'] = '[1/3] 기본 시세 수집 완료'
            self.collection_progress['total'] = len(all_stocks)
            self.collection_progress['message'] = f'{len(all_stocks)}개 종목 기본 시세 수집 완료'
            logger.info(f"[수집 1/3] 기본 시세 수집 완료: {len(all_stocks)}개 종목")
            
            for stock in all_stocks:
                new_stocks[stock['code']] = StockData(
                    code=stock['code'],
                    name=stock['name'],
                    market=stock['market'],
                    price=stock['price'],
                    change_rate=stock['change_rate'],
                    volume=stock['volume'],
                    market_cap=stock.get('market_cap', 0),
                    per=stock.get('per', 0.0),
                    updated_at=now
                )
            
            # 전체 종목에 대해 재무 데이터 수집 (진행률 추적)
            if include_financials:
                try:
                    # 전체 종목 대상 (거래량 순 정렬)
                    target_stocks = sorted(all_stocks, key=lambda x: x.get('volume', 0), reverse=True)
                    total_count = len(target_stocks)
                    
                    self.collection_progress['step'] = '[2/3] 재무 데이터 수집 중'
                    self.collection_progress['total'] = total_count
                    self.collection_progress['current'] = 0
                    self.collection_progress['message'] = f'0/{total_count}개 종목 재무 데이터 수집 중...'
                    logger.info(f"[수집 2/3] 전체 {total_count}개 종목 재무 데이터 수집 시작...")
                    
                    # 배치 처리 (20개씩 병렬)
                    collected = 0
                    batch_size = 20
                    
                    for batch_start in range(0, total_count, batch_size):
                        batch_end = min(batch_start + batch_size, total_count)
                        batch = target_stocks[batch_start:batch_end]
                        
                        # 배치 병렬 처리
                        tasks = []
                        for stock in batch:
                            code = stock['code']
                            tasks.append(loop.run_in_executor(
                                self._executor, self._collect_stock_financial, code
                            ))
                        
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # 결과 적용
                        for stock, result in zip(batch, results):
                            code = stock['code']
                            if isinstance(result, dict) and code in new_stocks:
                                new_stocks[code].per = result.get('per', 0.0)
                                new_stocks[code].pbr = result.get('pbr', 0.0)
                                new_stocks[code].op_rate = result.get('op_rate', 0.0)
                                new_stocks[code].debt_rate = result.get('debt_rate', 0.0)
                                new_stocks[code].rsrv_rate = result.get('rsrv_rate', 0.0)
                                new_stocks[code].sector = result.get('sector', '')
                                collected += 1
                            else:
                                self.collection_progress['errors'] += 1
                        
                        # 진행률 업데이트
                        self.collection_progress['current'] = batch_end
                        self.collection_progress['message'] = f'{batch_end}/{total_count}개 종목 수집됨 ({collected}개 성공)'
                        
                        # 로그 (100개마다)
                        if batch_end % 100 == 0 or batch_end == total_count:
                            elapsed_so_far = time.time() - start_time
                            eta = (elapsed_so_far / batch_end) * (total_count - batch_end) if batch_end > 0 else 0
                            logger.info(f"[수집 2/3] 재무 데이터: {batch_end}/{total_count} ({collected}개 성공, 예상 남은 시간: {eta:.0f}초)")
                        
                        # Rate limiting: 배치 간 딜레이
                        await asyncio.sleep(0.2)
                    
                    self.collection_progress['step'] = '[2/3] 재무 데이터 수집 완료'
                    self.collection_progress['message'] = f'{total_count}개 종목 중 {collected}개 재무 데이터 수집 완료'
                    logger.info(f"[수집 2/3] 재무 데이터 수집 완료: {collected}/{total_count}개")
                    
                except Exception as e:
                    logger.error(f"재무 데이터 수집 실패: {e}")
                    self.collection_progress['message'] = f'재무 데이터 수집 실패: {e}'
            
            self.stocks = new_stocks
            self.last_update = now
            
            elapsed = time.time() - start_time
            self.collection_progress['step'] = '[3/3] 캐시 갱신 완료'
            self.collection_progress['message'] = f'{len(self.stocks)}개 종목, {elapsed:.1f}초 소요'
            logger.info(f"[수집 3/3] 캐시 갱신 완료: {len(self.stocks)}개 종목, {elapsed:.1f}초 소요")
            
            # Save to file
            self.save_cache()
            
            return len(self.stocks)
            
        except Exception as e:
            logger.error(f"Cache update failed: {e}")
            self.collection_progress['message'] = f'수집 실패: {e}'
            return 0
        finally:
            self.is_updating = False
    
    def _collect_stock_financial(self, code: str) -> dict:
        """개별 종목 데이터 수집 (PER, 재무, RSI)"""
        result = {'per': 0.0, 'pbr': 0.0, 'op_rate': 0.0, 'debt_rate': 0.0, 'rsrv_rate': 0.0, 'sector': '', 'rsi': 0}
        try:
            # PER 수집
            result['per'] = self._get_stock_per(code)
            
            # 재무 데이터 + 업종 수집
            financials = self._get_naver_financials(code)
            result.update(financials)
            
            # RSI 수집/계산
            result['rsi'] = self._get_naver_rsi(code)
            
            # 추세 분석 (RSI와 이평선 활용)
            result['trend_ok'] = self._calculate_trend(code)
            
        except Exception as e:
            logger.debug(f"데이터 수집 실패 {code}: {e}")
        return result

    def _calculate_trend(self, code: str) -> bool:
        """종목의 추세 돌파 여부 판단
        
        [조건] 정배열 (현재가 > 20MA > 60MA)
        """
        try:
            # 60일치 데이터를 얻기 위해 6페이지 정도 수집 (페이지당 10개)
            prices = []
            for page in range(1, 7):
                url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={page}"
                html = self._fetch_html(url)
                
                # <tr onMouseOver...> 행들 내의 첫 번째 <span class="tah p11"> (종가) 추출
                rows = re.findall(r'<tr[^>]*onMouseOver="mouseOver\(this\)"[^>]*>.*?</tr>', html, re.DOTALL)
                if not rows:
                    break
                    
                for row in rows:
                    p_match = re.search(r'<span class="tah p11">([0-9,]+)</span>', row)
                    if p_match:
                        prices.append(int(p_match.group(1).replace(',', '')))
                
                if len(rows) < 10: # 마지막 페이지
                    break
                time.sleep(0.05)
            
            if len(prices) < 60:
                logger.debug(f"Trend Analysis: {code} data length {len(prices)} < 60")
                return False
                
            # 과거순 정렬
            prices = prices[::-1]
            series = pd.Series(prices)
            
            ma20 = series.rolling(20).mean().iloc[-1]
            ma60 = series.rolling(60).mean().iloc[-1]
            current = prices[-1]
            
            # 정배열 조건
            res = (current > ma20) and (ma20 > ma60)
            logger.debug(f"Trend Analysis {code}: current={current}, ma20={ma20:.0f}, ma60={ma60:.0f} -> {res}")
            return res
        except Exception as e:
            logger.error(f"Trend calculation failed for {code}: {e}")
            return False

    def _get_naver_rsi(self, code: str) -> int:
        """네이버 금융 일별 시세로 RSI(14) 계산"""
        try:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
            html = self._fetch_html(url)
            
            # 종가 추출
            prices = []
            rows = re.findall(r'<tr[^>]*onMouseOver="mouseOver\(this\)"[^>]*>.*?</tr>', html, re.DOTALL)
            for row in rows:
                p_match = re.search(r'<span class="tah p11">([0-9,]+)</span>', row)
                if p_match:
                    prices.append(int(p_match.group(1).replace(',', '')))
            
            if len(prices) < 15:
                # 2페이지까지 시도
                url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=2"
                html2 = self._fetch_html(url)
                rows2 = re.findall(r'<tr[^>]*onMouseOver="mouseOver\(this\)"[^>]*>.*?</tr>', html2, re.DOTALL)
                for row in rows2:
                    p_match = re.search(r'<span class="tah p11">([0-9,]+)</span>', row)
                    if p_match:
                        prices.append(int(p_match.group(1).replace(',', '')))

            if len(prices) < 15:
                return 0
                
            # 최근 15개 데이터 사용, 과거순 정렬
            prices = prices[:15][::-1]
            deltas = np.diff(prices)
            
            up = deltas[deltas >= 0].sum() / 14
            down = -deltas[deltas < 0].sum() / 14
            
            if down == 0:
                return 100
            
            rs = up / down
            rsi = 100. - (100. / (1. + rs))
            return int(rsi)
            
        except Exception as e:
            logger.error(f"RSI calculation failed for {code}: {e}")
            return 0
    
    def _get_naver_financials(self, code: str) -> dict:
        """네이버 금융에서 재무 데이터 수집
        
        [누가] StockCache
        [무엇을] 영업이익률, 부채비율, 유보율, 업종
        [어디서] finance.naver.com/item/main.naver
        """

        result = {'op_rate': 0.0, 'debt_rate': 0.0, 'rsrv_rate': 0.0, 'pbr': 0.0, 'sector': ''}
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            html = self._fetch_html(url)
            
            # PBR Extraction
            pbr_match = re.search(r'<em id="_pbr">([0-9.,]+)</em>', html)
            if pbr_match:
                try:
                    result['pbr'] = float(pbr_match.group(1).replace(',', ''))
                except (UnicodeDecodeError, LookupError):
                    pass
            
            # 업종 파싱
            sector_match = re.search(r'업종.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
            if sector_match:
                result['sector'] = sector_match.group(1).strip()
            
            # 재무 데이터 파싱 (Table Header 방식)
            keywords = {"영업이익률": "op_rate", "부채비율": "debt_rate", "유보율": "rsrv_rate"}
            
            for term, key in keywords.items():
                try:
                    # Find the header row
                    header_pattern = re.compile(f'<th[^>]*>.*?<strong>{term}</strong>.*?</th>', re.DOTALL)
                    match = header_pattern.search(html)
                    
                    if match:
                        start_pos = match.end()
                        row_end_match = re.search(r'</tr>', html[start_pos:])
                        if row_end_match:
                            end_pos = start_pos + row_end_match.start()
                            row_html = html[start_pos:end_pos]
                            
                            # Extract all td values
                            tds = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
                            
                            valid_values = []
                            for td_content in tds:
                                # Remove tags
                                clean_text = re.sub(r'<[^>]+>', '', td_content).strip()
                                if clean_text and clean_text != '-' and clean_text != '':
                                    try:
                                        valid_values.append(float(clean_text.replace(',', '')))
                                    except (UnicodeDecodeError, LookupError):
                                        pass
                            
                            if valid_values:
                                # Use the last valid value (usually most recent)
                                result[key] = valid_values[-1]
                except Exception:
                    pass
                
        except Exception as e:
            logger.debug(f"Naver financials failed {code}: {e}")
        
        return result

    
    def filter_stocks(
        self,
        min_volume: int = 0,
        max_volume: int = 0, # 0 means no limit
        min_per: float = 0,
        max_per: float = 0,
        min_pbr: float = 0,
        max_pbr: float = 0,
        min_market_cap: int = 0, # 억 단위
        max_market_cap: int = 0,
        min_op_rate: float = -999,
        max_op_rate: float = 0,
        min_debt_rate: float = 0,
        max_debt_rate: float = 0,
        min_rsrv_rate: float = 0,
        max_rsrv_rate: float = 0,
        optimal_mode: bool = False,
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
            # 1. Volume
            if stock.volume < min_volume:
                continue
            if max_volume > 0 and stock.volume > max_volume:
                continue

            # 2. Market Cap
            # stock.market_cap is in "won" unit? No, usually "억원" based on prev check.
            # Check parsing logic: "8,228,297" -> 8,228,297 (billion won if Naver uses 억)
            # Actually Naver "시가총액" typically displayed in 100 million KRW (억).
            if min_market_cap > 0 and stock.market_cap < min_market_cap:
                continue
            if max_market_cap > 0 and stock.market_cap > max_market_cap:
                continue
            
            # 3. PER
            # PER <= 0 is invalid/loss, usually filtered out if min_per > 0
            if min_per > 0 and stock.per < min_per:
                    continue
            if max_per > 0 and stock.per > max_per:
                continue

            # 4. PBR
            if min_pbr > 0 and stock.pbr < min_pbr:
                continue
            if max_pbr > 0 and stock.pbr > max_pbr:
                continue
            
            # 시장 필터
            if market and stock.market != market:
                continue
                
            # 상세 재무 필터
            # Op Rate (Percent)
            if stock.op_rate < min_op_rate: # Default -999
                continue
            if max_op_rate != 0 and stock.op_rate > max_op_rate:
                continue

            # Debt Rate
            if min_debt_rate > 0 and stock.debt_rate < min_debt_rate:
                continue
            if max_debt_rate > 0 and stock.debt_rate > max_debt_rate:
                continue

            # Rsrv Rate
            if min_rsrv_rate > 0 and stock.rsrv_rate < min_rsrv_rate:
                continue
            if max_rsrv_rate > 0 and stock.rsrv_rate > max_rsrv_rate:
                continue

            # AI 최적 모드 필터 (추세 돌파 또는 RSI 범위)
            if optimal_mode:
                # 추세 돌파 여부 확인 (캐시 수집 시 계산됨)
                # 또는 RSI 30 ~ 70 구간 (에너지 응축)
                momentum_ok = (stock.rsi >= 30 and stock.rsi <= 70)
                if not (stock.trend_ok or momentum_ok):
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
                'pbr': stock.pbr if stock.pbr > 0 else None,
                'market_cap': stock.market_cap,
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
                    'per': '수집됨' if stock.per > 0 else '미수집',
                    'op_rate': '수집됨' if stock.op_rate != 0 else '미수집',
                    'debt_rate': '수집됨' if stock.debt_rate != 0 else '미수집',
                    'rsrv_rate': '수집됨' if stock.rsrv_rate != 0 else '미수집',
                    'rsi': '수집됨' if stock.rsi != 0 else '미수집',
                }
            })
        
        # 거래량 순 정렬
        results.sort(key=lambda x: x.get('volume', 0), reverse=True)
        
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
                'per': stock.per,
                'op_rate': stock.op_rate,
                'debt_rate': stock.debt_rate,
                'rsrv_rate': stock.rsrv_rate,
                'rsi': stock.rsi,
                'sector': stock.sector,
                'updated_at': stock.updated_at.isoformat() if stock.updated_at else None
            }
        return None
    

    def _init_db(self):
        """SQLite DB 초기화"""
        try:
            import sqlite3
            import os
            
            os.makedirs('data', exist_ok=True)
            self.db_path = 'data/stock_cache.db'
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 종목 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    price INTEGER,
                    change_rate REAL,
                    volume INTEGER,
                    market_cap INTEGER,
                    per REAL,
                op_rate REAL,
                debt_rate REAL,
                rsrv_rate REAL,
                pbr REAL,
                rsi INTEGER,
                sector TEXT,
                trend_ok BOOLEAN,
                updated_at DATETIME
            )
        ''')
            
            # 메타데이터 테이블 (마지막 업데이트 시간 등)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # 일별 히스토리 테이블 (추세 분석용)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_history (
                    date TEXT,
                    code TEXT,
                    price INTEGER,
                    volume INTEGER,
                    market_cap INTEGER,
                    per REAL,
                    pbr REAL,
                    op_rate REAL,
                    debt_rate REAL,
                    rsrv_rate REAL,
                    PRIMARY KEY (date, code)
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to init DB: {e}")

    def save_cache(self):
        """캐시 데이터를 SQLite로 저장"""
        try:
            import sqlite3
            
            if not getattr(self, 'db_path', None):
                self._init_db()
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            logger.info(f"Saving to DB Path: {self.db_path}")
            
            # 1. 메타데이터 저장
            last_update_str = self.last_update.isoformat() if self.last_update else None
            cursor.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', 
                          ('last_update', last_update_str))
            
            # 2. 종목 데이터 Bulk Upsert
            stock_data_list = []
            for s in self.stocks.values():
                stock_data_list.append((
                    s.code, s.name, s.market, s.price, s.change_rate, s.volume,
                s.market_cap, s.per, s.op_rate, s.debt_rate, s.rsrv_rate, 
                s.pbr, s.rsi, s.sector, s.trend_ok,
                s.updated_at.isoformat() if s.updated_at else None
            ))
        
            if len(stock_data_list) > 0:
                logger.info(f"First stock sample: {stock_data_list[0]}")
            
            cursor.executemany('''
                INSERT OR REPLACE INTO stocks (
                    code, name, market, price, change_rate, volume, market_cap,
                    per, op_rate, debt_rate, rsrv_rate, pbr, rsi, sector, trend_ok, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', stock_data_list)
            
            # 3. 일별 히스토리 저장 (오늘 날짜 스냅샷)
            from datetime import datetime
            today_str = datetime.now().strftime('%Y-%m-%d')
            history_data_list = []
            
            for s in self.stocks.values():
                history_data_list.append((
                    today_str, s.code, s.price, s.volume, s.market_cap,
                    s.per, s.pbr, s.op_rate, s.debt_rate, s.rsrv_rate
                ))
            
            cursor.executemany('''
                INSERT OR REPLACE INTO daily_history (
                    date, code, price, volume, market_cap,
                    per, pbr, op_rate, debt_rate, rsrv_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', history_data_list)
            
            conn.commit()
            conn.close()
                
            logger.info(f"Saved {len(self.stocks)} stocks to SQLite DB")
            
        except Exception as e:
            logger.error(f"Failed to save cache to DB: {e}")

    def load_cache(self):
        """SQLite에서 캐시 데이터 로드"""
        try:
            import sqlite3
            import os
            from datetime import datetime
            
            self._init_db()
            
            if not os.path.exists(self.db_path):
                return

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 메타데이터 로드
            cursor.execute("SELECT value FROM meta WHERE key='last_update'")
            row = cursor.fetchone()
            if row and row[0]:
                self.last_update = datetime.fromisoformat(row[0])
            
            # 2. 종목 데이터 로드
            cursor.execute("SELECT * FROM stocks")
            rows = cursor.fetchall()
            
            loaded_count = 0
            for row in rows:
                stock = StockData(
                    code=row['code'],
                    name=row['name'],
                    market=row['market'],
                    price=row['price'],
                    change_rate=row['change_rate'],
                    volume=row['volume'],
                    market_cap=row['market_cap'],
                    per=row['per'],
                    op_rate=row['op_rate'],
                debt_rate=row['debt_rate'],
                rsrv_rate=row['rsrv_rate'],
                pbr=row['pbr'] if 'pbr' in row.keys() else 0.0,
                rsi=row['rsi'],
                sector=row['sector'],
                trend_ok=bool(row['trend_ok']),
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                self.stocks[stock.code] = stock
                loaded_count += 1
                
            conn.close()
            logger.info(f"Loaded {loaded_count} stocks from SQLite DB")
            
        except Exception as e:
            logger.error(f"Failed to load cache from DB: {e}")


    def get_stats(self) -> Dict:
        return {
            'total_stocks': len(self.stocks),
            'last_update': self.last_update,
            'is_updating': self.is_updating,
            'collection_progress': self.collection_progress
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
    
    # 초기 로드 (자동 업데이트는 루프에서 체크)
    # await cache.update_cache() 
    
    # 주기적 갱신
    logger.info("Starting stock cache refresh task...")
    
    # Initial delay slightly
    await asyncio.sleep(5)
    
    while True:
        try:
            cache = get_stock_cache()
            
            # 1. Check if update is needed (Daily Check)
            now = datetime.now()
            should_update = True
            
            if cache.last_update:
                # Same day check
                if cache.last_update.date() == now.date():
                    logger.info("Cache already updated today. Skipping update.")
                    should_update = False
                
                # If DB file missing (edge case), force update
                elif not os.path.exists(cache.db_path):
                    should_update = True
            
            if should_update:
                logger.info("Executing scheduled stock cache update...")
                await cache.update_cache()
            
            # Sleep until next check (e.g., check every hour to see if day changed)
            # But the requirement is "once a day". 
            # We can check every hour. If day changed, it will update.
            await asyncio.sleep(3600) 
            
        except Exception as e:
            logger.error(f"Error in cache refresh task: {e}")
            await asyncio.sleep(60)  # Retry on error
