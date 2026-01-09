"""
Stock Screener Module - 주식 조건 검색기
조건: PER 20배 이하 + 쌍바닥 패턴, 외국인/기관 수급 3일 지속, 거래량 100만건 이상
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

# Add paths for KIS API
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
sys.path.append(os.path.join(os.getcwd(), 'examples_user', 'domestic_stock'))

import kis_auth
import domestic_stock_functions as d_func

logger = logging.getLogger(__name__)


class StockScreener:
    """
    주식 조건 검색기
    
    조건:
    1. PER 20배 이하
    2. 쌍바닥 패턴 (60일 기준)
    3. 외국인/기관 순매수 3일 연속
    4. 거래량 100만건 이상
    """
    
    def __init__(self):
        self.last_scan_time: Optional[str] = None
        self.last_results: List[dict] = []
        self._auth_initialized = False
        from stock_code_lookup import StockMaster
        self.sm = StockMaster()
    
    def _ensure_auth(self):
        """KIS API 인증 확인"""
        if not self._auth_initialized:
            try:
                kis_auth.auth()
                self._auth_initialized = True
                logger.info("KIS API 인증 완료")
            except Exception as e:
                logger.error(f"KIS API 인증 실패: {e}")
                raise
    
    def get_high_volume_stocks(self, min_volume: int = 1000000) -> pd.DataFrame:
        """
        거래량 100만건 이상 종목 조회
        
        Args:
            min_volume: 최소 거래량 (기본 100만)
            
        Returns:
            거래량 상위 종목 DataFrame
        """
        self._ensure_auth()
        
        try:
            df = d_func.volume_rank(
                fid_cond_mrkt_div_code="J",  # KRX
                fid_cond_scr_div_code="20171",
                fid_input_iscd="0000",  # 전체
                fid_div_cls_code="0",  # 전체 (보통주+우선주)
                fid_blng_cls_code="0",  # 평균거래량
                fid_trgt_cls_code="111111111",
                fid_trgt_exls_cls_code="0000000000",
                fid_input_price_1="",
                fid_input_price_2="",
                fid_vol_cnt=str(min_volume),
                fid_input_date_1=""
            )
            
            if df is not None and not df.empty:
                logger.info(f"거래량 {min_volume:,} 이상 종목 {len(df)}개 조회 완료")
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"거래량 순위 조회 실패: {e}")
            return pd.DataFrame()
    
    def get_stock_price_info(self, ticker: str) -> Optional[dict]:
        """
        종목 현재가 및 PER 조회
        
        Args:
            ticker: 종목코드 (6자리)
            
        Returns:
            {'price': 현재가, 'per': PER, 'volume': 거래량, ...}
        """
        self._ensure_auth()
        
        try:
            df = d_func.inquire_price(
                env_dv="real",
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=ticker
            )
            
            if df is not None and not df.empty:
                row = df.iloc[0]
                # Try multiple possible name fields
                name = self.sm.get_name(ticker) or row.get('hts_kor_isnm') or row.get('stck_shrn_isnm') or row.get('name') or ticker
                return {
                    'price': int(row.get('stck_prpr', 0)),
                    'per': float(row.get('per', 0)) if row.get('per') else None,
                    'volume': int(row.get('acml_vol', 0)),
                    'name': name,
                    'change_rate': float(row.get('prdy_ctrt', 0)),
                    'sector': row.get('bstp_kor_isnm', '-')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"종목 {ticker} 현재가 조회 실패: {e}")
            return None
    
    def get_daily_prices(self, ticker: str, days: int = 60) -> pd.DataFrame:
        """
        일봉 데이터 조회 (쌍바닥 패턴 분석용)
        
        Args:
            ticker: 종목코드
            days: 조회 기간 (일)
            
        Returns:
            일봉 DataFrame (stck_bsop_date, stck_oprc, stck_hgpr, stck_lwpr, stck_clpr)
        """
        self._ensure_auth()
        
        try:
            df = d_func.inquire_daily_price(
                env_dv="real",
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=ticker,
                fid_period_div_code="D",
                fid_org_adj_prc="0"  # 수정주가
            )
            
            if df is not None and not df.empty:
                # 최근 N일 데이터만 사용
                return df.head(days)
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"종목 {ticker} 일봉 조회 실패: {e}")
            return pd.DataFrame()
    
    def check_double_bottom(self, ticker: str, days: int = 60) -> Tuple[bool, str]:
        """
        쌍바닥 패턴 감지
        
        알고리즘:
        1. 60일 일봉 데이터에서 저점(local minima) 2개 찾기
        2. 두 저점의 가격 차이 5% 이내
        3. 두 저점 사이에 반등 (10% 이상) 존재
        
        Args:
            ticker: 종목코드
            days: 분석 기간
            
        Returns:
            (패턴 존재 여부, 설명 메시지)
        """
        df = self.get_daily_prices(ticker, days)
        
        if df.empty or len(df) < 20:
            return False, "데이터 부족"
        
        try:
            # 종가 데이터 추출 (오래된 순으로 정렬)
            closes = df['stck_clpr'].astype(int).values[::-1]
            
            if len(closes) < 20:
                return False, "데이터 부족"
            
            # Local minima 찾기 (5일 기준)
            window = 5
            minima_indices = []
            
            for i in range(window, len(closes) - window):
                if closes[i] == min(closes[i-window:i+window+1]):
                    minima_indices.append(i)
            
            if len(minima_indices) < 2:
                return False, "저점 2개 미만"
            
            # 가장 최근 2개의 저점
            recent_minima = minima_indices[-2:]
            idx1, idx2 = recent_minima[0], recent_minima[1]
            low1, low2 = closes[idx1], closes[idx2]
            
            # 두 저점 거리 확인 (최소 10일 이상 떨어져 있어야 함)
            if abs(idx2 - idx1) < 10:
                return False, "저점 간격 부족"
            
            # 조건 1: 두 저점 가격 차이 5% 이내
            price_diff = abs(low1 - low2) / max(low1, low2) * 100
            if price_diff > 5:
                return False, f"저점 차이 {price_diff:.1f}% > 5%"
            
            # 조건 2: 두 저점 사이에 반등 10% 이상
            between_prices = closes[idx1:idx2+1]
            peak = max(between_prices)
            min_low = min(low1, low2)
            rebound = (peak - min_low) / min_low * 100
            
            if rebound < 10:
                return False, f"반등 {rebound:.1f}% < 10%"
            
            return True, f"쌍바닥 감지: 저점차 {price_diff:.1f}%, 반등 {rebound:.1f}%"
            
        except Exception as e:
            logger.error(f"쌍바닥 분석 오류 {ticker}: {e}")
            return False, f"분석 오류: {e}"
    
    def check_investor_flow(self, ticker: str, days: int = 3) -> dict:
        """
        외국인/기관 순매수 연속 여부 확인
        
        Args:
            ticker: 종목코드
            days: 연속 일수 (기본 3일)
            
        Returns:
            {
                'foreign_consecutive': True/False,
                'institution_consecutive': True/False,
                'foreign_amounts': [...],
                'institution_amounts': [...]
            }
        """
        self._ensure_auth()
        
        try:
            today = datetime.now().strftime("%Y%m%d")
            df1, df2 = d_func.investor_trade_by_stock_daily(
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=ticker,
                fid_input_date_1=today,
                fid_org_adj_prc="",
                fid_etc_cls_code=""
            )
            
            result = {
                'foreign_consecutive': False,
                'institution_consecutive': False,
                'foreign_amounts': [],
                'institution_amounts': []
            }
            
            if df2 is None or df2.empty:
                return result
            
            # 최근 N일 데이터
            recent = df2.head(days)
            
            if len(recent) < days:
                return result
            
            # 외국인 순매수 (frgn_ntby_qty: 외국인 순매수 수량)
            foreign_buys = []
            # 기관 순매수 (orgn_ntby_qty: 기관 순매수 수량)
            inst_buys = []
            
            for _, row in recent.iterrows():
                frgn = int(row.get('frgn_ntby_qty', 0)) if row.get('frgn_ntby_qty') else 0
                orgn = int(row.get('orgn_ntby_qty', 0)) if row.get('orgn_ntby_qty') else 0
                foreign_buys.append(frgn)
                inst_buys.append(orgn)
            
            result['foreign_amounts'] = foreign_buys
            result['institution_amounts'] = inst_buys
            
            # 연속 순매수 확인 (모두 양수)
            result['foreign_consecutive'] = all(x > 0 for x in foreign_buys)
            result['institution_consecutive'] = all(x > 0 for x in inst_buys)
            
            return result
            
        except Exception as e:
            logger.error(f"투자자 동향 조회 실패 {ticker}: {e}")
            return {
                'foreign_consecutive': False,
                'institution_consecutive': False,
                'foreign_amounts': [],
                'institution_amounts': []
            }
    
    def check_per(self, ticker: str, max_per: float = 20.0) -> Tuple[bool, Optional[float]]:
        # ... (keep existing)
        info = self.get_stock_price_info(ticker)
        
        if info is None or info.get('per') is None:
            return False, None
        
        per = info['per']
        
        # PER이 0 또는 음수인 경우 (적자 기업) 제외
        if per <= 0:
            return False, per
        
        return per <= max_per, per

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """RSI (Relative Strength Index) 계산"""
        if len(prices) < period + 1:
            return None
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def check_momentum_and_trend(self, ticker: str) -> Tuple[bool, dict]:
        """
        Antigravity Optimal 전략: 추세, 모멘텀, 거래량 분석
        1. 추세: 종가 > 20MA > 60MA (정배열 초입/진행)
        2. 모멘텀: RSI 45~65 (에너지 응축 구간)
        3. 거래량: 당일 거래량 > 5일 평균 거래량 * 200%
        """
        df = self.get_daily_prices(ticker, 70) # 60일 이평선을 위해 70일치 가져옴
        if df.empty or len(df) < 65:
            return False, {}

        try:
            # 종가 (정렬: 과거 -> 현재)
            closes = df['stck_clpr'].astype(float).values[::-1]
            vols = df['acml_vol'].astype(float).values[::-1]
            
            closes_series = pd.Series(closes)
            
            # 1. Moving Averages
            ma5 = closes_series.rolling(5).mean().iloc[-1]
            ma20 = closes_series.rolling(20).mean().iloc[-1]
            ma60 = closes_series.rolling(60).mean().iloc[-1]
            current_price = closes[-1]
            
            # 추세 조건: 정배열 (20 > 60) AND 현재가 > 20MA
            trend_ok = (current_price > ma20) and (ma20 > ma60)
            
            # 2. RSI
            rsi = self.calculate_rsi(closes_series, 14)
            # 모멘텀 조건: 30 ~ 70 (과매수/과매도 제외, 넓은 범위) 
            momentum_ok = (rsi is not None) and (30 <= rsi <= 70)
            
            # 3. Volume Spike
            avg_vol_5 = pd.Series(vols).rolling(5).mean().iloc[-2] # 전일까지의 5일 평균
            current_vol = vols[-1]
            vol_spike_ok = current_vol > (avg_vol_5 * 1.5) if avg_vol_5 > 0 else False  # 150%로 완화
            
            # 4. Golden Cross (최근 3일 내 5일선이 20일선 돌파)
            ma5_prev = closes_series.rolling(5).mean().iloc[-4:-1].values
            ma20_prev = closes_series.rolling(20).mean().iloc[-4:-1].values
            golden_cross = any((ma5_prev[i] < ma20_prev[i] and ma5_prev[i+1] > ma20_prev[i+1]) for i in range(len(ma5_prev)-1))

            # 통과 조건: 추세 OR 모멘텀 중 하나만 만족해도 OK (완화)
            passed = trend_ok or momentum_ok

            
            return passed, {
                'rsi': round(rsi, 2) if rsi else None,
                'ma20': round(ma20, 0),
                'ma60': round(ma60, 0),
                'vol_spike': vol_spike_ok,
                'golden_cross': golden_cross,
                'trend_ok': trend_ok,
                'momentum_ok': momentum_ok
            }
        except Exception as e:
            logger.error(f"지표 분석 실패 {ticker}: {e}")
            return False, {}

    def check_financials(self, ticker: str, 
                         min_op_rate: float = 5.0, 
                         max_debt_rate: float = 100.0, 
                         max_rsrv_rate: float = 1000.0) -> Tuple[bool, dict]:
        """
        재무 건전성 확인 (영업이익률, 부채비율, 유보율)
        """
        self._ensure_auth()
        try:
            # 0: 년, 1: 분기
            df = d_func.finance_financial_ratio("0", "J", ticker)
            
            if df is None or df.empty:
                return False, {}
            
            # 가장 최근 연도 데이터 (stac_yymm 이 가장 큰 것)
            row = df.sort_values('stac_yymm', ascending=False).iloc[0]
            
            op_rate = float(row.get('bsop_prfi_inrt', 0)) # 영업이익률
            debt_rate = float(row.get('lblt_rate', 0))    # 부채비율
            rsrv_rate = float(row.get('rsrv_rate', 0))    # 유보율
            
            passed = (op_rate >= min_op_rate) and (debt_rate <= max_debt_rate) and (rsrv_rate <= max_rsrv_rate)
            
            return passed, {
                'op_rate': op_rate,
                'debt_rate': debt_rate,
                'rsrv_rate': rsrv_rate
            }
        except Exception as e:
            logger.error(f"재무 정보 조회 실패 {ticker}: {e}")
            return False, {}

    def scan_all(self, 
                 min_volume: int = 1000000,
                 max_per: float = 20.0,
                 require_double_bottom: bool = True,
                 require_investor_flow: bool = True,
                 min_op_rate: float = 5.0,
                 max_debt_rate: float = 100.0,
                 max_rsrv_rate: float = 1000.0,
                 optimal_mode: bool = False) -> List[dict]:
        """
        전체 조건 검색 실행
        
        1단계: 거래량 100만 이상 종목 필터링
        2단계: PER 20 이하 필터링 (Optimal Mode일 경우 완화)
        3단계: 재무 건전성 확인
        4단계: (일반) 쌍바닥/수급 확인 OR (Optimal) 추세/모멘텀/거래량 확인
        """
        results = []
        self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"=== 주식 검색 시작 ===")
        logger.info(f"조건: 거래량>{min_volume:,}, PER<{max_per}, 쌍바닥={require_double_bottom}, 수급={require_investor_flow}")
        
        # 1단계: 거래량 100만 이상 종목
        volume_df = self.get_high_volume_stocks(min_volume)
        
        if volume_df.empty:
            logger.warning("거래량 조건 충족 종목 없음")
            self.last_results = results
            return results
        
        # 종목 코드 추출
        tickers = volume_df['mksc_shrn_iscd'].tolist() if 'mksc_shrn_iscd' in volume_df.columns else []
        
        if not tickers:
            # 다른 컬럼명 시도
            for col in ['stck_shrn_iscd', 'shrn_iscd', 'iscd']:
                if col in volume_df.columns:
                    tickers = volume_df[col].tolist()
                    break
        
        logger.info(f"1단계: 거래량 조건 충족 {len(tickers)}개 종목")
        
        # 2~4단계: 각 종목별 상세 분석
        for i, ticker in enumerate(tickers):
            try:
                stock_data = {
                    'ticker': ticker,
                    'name': '',
                    'price': 0,
                    'per': None,
                    'volume': 0,
                    'double_bottom': False,
                    'double_bottom_msg': '',
                    'foreign_consecutive': False,
                    'institution_consecutive': False,
                    'score': 0
                }
                
                # 2단계: PER 확인 (max_per >= 9999이면 스킵 - 전체보기 모드)
                # Optimal Mode에서는 성장을 중시하므로 PER 기준을 약간 완화 (30까지)
                current_max_per = 30.0 if optimal_mode else max_per
                skip_filters = (max_per >= 9999)  # 전체보기 모드
                
                if not skip_filters:
                    per_ok, per_value = self.check_per(ticker, current_max_per)
                    stock_data['per'] = per_value
                    
                    if not per_ok:
                        continue
                else:
                    # 전체보기 모드: PER 필터 스킵
                    stock_data['per'] = None
                
                # 2.5단계: 재무 확인 (영업이익률, 부채비율, 유보율)
                if not skip_filters:
                    fin_ok, fin_data = self.check_financials(ticker, min_op_rate, max_debt_rate, max_rsrv_rate)
                    stock_data.update(fin_data)
                    
                    if not fin_ok:
                        continue
                else:
                    # 전체보기 모드: 재무 필터 스킵
                    stock_data.update({'op_rate': None, 'debt_rate': None, 'rsrv_rate': None})

                
                # 기본 정보 추가
                info = self.get_stock_price_info(ticker)
                if info:
                    stock_data['name'] = info.get('name', ticker)
                    stock_data['price'] = info.get('price', 0)
                    stock_data['volume'] = info.get('volume', 0)
                    stock_data['sector'] = info.get('sector', '-')

                if optimal_mode:
                    # [Optimal Mode] 추세/모멘텀/거래량 분석
                    opt_ok, opt_data = self.check_momentum_and_trend(ticker)
                    stock_data.update(opt_data)
                    
                    if not opt_ok:
                        continue
                    
                    # 점수 계산
                    score = 2 # 기본 합격
                    if opt_data['vol_spike']: score += 2
                    if opt_data['golden_cross']: score += 1
                    stock_data['score'] = score
                else:
                    # [Standard Mode] 쌍바닥/수급 분석
                    # 3단계: 쌍바닥 패턴
                    if require_double_bottom:
                        db_ok, db_msg = self.check_double_bottom(ticker)
                        stock_data['double_bottom'] = db_ok
                        stock_data['double_bottom_msg'] = db_msg
                        
                        if not db_ok:
                            continue
                    
                    # 4단계: 외국인/기관 수급
                    if require_investor_flow:
                        flow = self.check_investor_flow(ticker)
                        stock_data['foreign_consecutive'] = flow['foreign_consecutive']
                        stock_data['institution_consecutive'] = flow['institution_consecutive']
                        
                        # 외국인 또는 기관 중 하나라도 3일 연속 순매수
                        if not (flow['foreign_consecutive'] or flow['institution_consecutive']):
                            continue
                    
                    # 점수 계산 (조건 충족 개수)
                    score = 0
                    if per_ok: score += 1
                    if stock_data.get('double_bottom'): score += 1
                    if stock_data.get('foreign_consecutive'): score += 1
                    if stock_data.get('institution_consecutive'): score += 1
                    stock_data['score'] = score
                
                results.append(stock_data)
                logger.info(f"✓ {ticker} {stock_data['name']} - PER:{per_value:.1f}, 점수:{score}")
                
                # API 호출 제한 대응 (초당 요청 제한)
                kis_auth.smart_sleep()
                
            except Exception as e:
                logger.error(f"종목 {ticker} 분석 실패: {e}")
                continue
        
        # 점수순 정렬
        results.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"=== 검색 완료: {len(results)}개 종목 발견 ===")
        self.last_results = results
        
        return results


# CLI 테스트용
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    screener = StockScreener()
    
    # 간단 테스트: 거래량 상위 종목만 조회
    print("=== 거래량 100만 이상 종목 조회 ===")
    df = screener.get_high_volume_stocks()
    if not df.empty:
        print(f"총 {len(df)}개 종목")
        print(df.head(10))
    
    # 전체 스캔 (시간 오래 걸림)
    # results = screener.scan_all()
    # print(f"조건 충족 종목: {len(results)}개")
    # for r in results[:10]:
    #     print(r)
