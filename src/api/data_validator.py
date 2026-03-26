# -*- coding: utf-8 -*-
"""
데이터 검증 모듈 (Data Validator)
=================================
[2026-02-08 신규 생성]
[수정 이유: 회장님 요청 - 한국투자증권 API와 네이버 증권 데이터 비교 검증]
[원본 코드: 신규 작성 (기존 없음)]

기능:
1. 한국투자증권 API에서 데이터 수집
2. 네이버 증권에서 동일 데이터 수집
3. 두 소스 비교 → 일치율 계산
4. 불일치 시 경고 및 신뢰할 소스 선택

검증 항목:
- 현재가 (close price)
- 거래량 (volume)
- 등락률 (change rate)
- 외국인/기관 수급 (investor data)

사용법:
    validator = DataValidator()
    result = await validator.validate_stock_data("080160")  # 모두투어
    print(result)
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

import requests
from bs4 import BeautifulSoup

# Path setup for KIS imports
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(base_dir, "src", "core"))
sys.path.insert(0, os.path.join(base_dir, "src", "utils"))
sys.path.insert(0, os.path.join(base_dir, "examples_user"))
sys.path.insert(0, os.path.join(base_dir, "examples_user", "domestic_stock"))

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """데이터 소스 구분"""
    KIS = "한국투자증권"
    NAVER = "네이버증권"
    VERIFIED = "검증됨"
    CONFLICT = "불일치"


@dataclass
class StockData:
    """주식 데이터 구조체"""
    source: DataSource
    ticker: str
    name: str
    current_price: int
    change: int
    change_rate: float
    volume: int
    high: int
    low: int
    open_price: int
    foreign_net: Optional[int] = None  # 외국인 순매수
    institution_net: Optional[int] = None  # 기관 순매수
    individual_net: Optional[int] = None  # 개인 순매수
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source.value,
            "ticker": self.ticker,
            "name": self.name,
            "current_price": self.current_price,
            "change": self.change,
            "change_rate": self.change_rate,
            "volume": self.volume,
            "high": self.high,
            "low": self.low,
            "open": self.open_price,
            "foreign_net": self.foreign_net,
            "institution_net": self.institution_net,
            "individual_net": self.individual_net,
            "timestamp": self.timestamp
        }


@dataclass
class ValidationResult:
    """검증 결과 구조체"""
    is_valid: bool
    match_rate: float  # 0.0 ~ 1.0
    kis_data: Optional[StockData]
    naver_data: Optional[StockData]
    verified_data: Optional[StockData]  # 검증 후 최종 데이터
    discrepancies: List[str]  # 불일치 항목
    warnings: List[str]
    recommendation: str  # 어떤 소스를 신뢰해야 하는지
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "match_rate": f"{self.match_rate * 100:.1f}%",
            "kis_data": self.kis_data.to_dict() if self.kis_data else None,
            "naver_data": self.naver_data.to_dict() if self.naver_data else None,
            "verified_data": self.verified_data.to_dict() if self.verified_data else None,
            "discrepancies": self.discrepancies,
            "warnings": self.warnings,
            "recommendation": self.recommendation
        }


class DataValidator:
    """
    한국투자증권 API + 네이버 증권 이중 검증 클래스
    """
    
    # 허용 오차 범위 설정
    PRICE_TOLERANCE = 0.001  # 가격 0.1% 이내 = 동일
    VOLUME_TOLERANCE = 0.05  # 거래량 5% 이내 = 동일
    INVESTOR_TOLERANCE = 0.10  # 수급 10% 이내 = 동일
    
    def __init__(self, is_live: bool = True):
        """
        Args:
            is_live: True=실전투자, False=모의투자
        """
        self.is_live = is_live
        self._kis_initialized = False
        self._ka = None
        self._functions = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def _init_kis(self) -> bool:
        """한국투자증권 API 초기화"""
        if self._kis_initialized:
            return True
        
        try:
            import kis_auth as ka
            self._ka = ka
            ka.auth()
            
            import domestic_stock_functions as dsf
            self._functions = dsf
            
            self._kis_initialized = True
            logger.info("[DataValidator] KIS API 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"[DataValidator] KIS API 초기화 실패: {e}")
            return False
    
    def get_kis_data(self, ticker: str) -> Optional[StockData]:
        """
        한국투자증권 API에서 주식 데이터 조회
        
        [2026-02-08 수정]
        [수정 이유: KIS API 함수명 수정 (inquire_price, inquire_investor)]
        [원본: get_inquire_price → inquire_price("real"/"demo", "J", ticker)]
        
        Args:
            ticker: 종목코드 (예: "080160")
        
        Returns:
            StockData 또는 None
        """
        if not self._init_kis():
            logger.warning("[DataValidator] KIS API 사용 불가")
            return None
        
        try:
            # KIS API: 현재가 조회
            # 함수 형식: inquire_price(env_dv, market, ticker) → DataFrame
            env_dv = "real" if self.is_live else "demo"
            df = self._functions.inquire_price(env_dv, "J", ticker)
            
            if df is None or df.empty:
                logger.warning(f"[DataValidator] KIS 가격 데이터 없음: {ticker}")
                return None
            
            row = df.iloc[0]
            
            # Helper functions
            def safe_int(val):
                try:
                    return int(float(val or 0))
                except (ValueError, TypeError):
                    return 0
            
            def safe_float(val):
                try:
                    return float(val or 0)
                except (ValueError, TypeError):
                    return 0.0
            
            # KIS API: 투자자별 매매동향 (일별)
            foreign_net = None
            institution_net = None
            individual_net = None
            
            try:
                if hasattr(self._functions, 'inquire_investor'):
                    inv_df = self._functions.inquire_investor(env_dv, "J", ticker)
                    if inv_df is not None and not inv_df.empty:
                        inv_row = inv_df.iloc[0]
                        foreign_net = safe_int(inv_row.get('frgn_ntby_tr_pbmn', 0) or inv_row.get('frgn_ntby_qty', 0))
                        institution_net = safe_int(inv_row.get('orgn_ntby_tr_pbmn', 0) or inv_row.get('orgn_ntby_qty', 0))
                        individual_net = safe_int(inv_row.get('prsn_ntby_tr_pbmn', 0) or inv_row.get('prsn_ntby_qty', 0))
            except Exception as e:
                logger.debug(f"[DataValidator] KIS 투자자 데이터 조회 실패: {e}")
            
            return StockData(
                source=DataSource.KIS,
                ticker=ticker,
                name=str(row.get('prdt_abrv_name', '') or row.get('hts_kor_isnm', '')),
                current_price=safe_int(row.get('stck_prpr', 0)),
                change=safe_int(row.get('prdy_vrss', 0)),
                change_rate=safe_float(row.get('prdy_ctrt', 0)),
                volume=safe_int(row.get('acml_vol', 0)),
                high=safe_int(row.get('stck_hgpr', 0)),
                low=safe_int(row.get('stck_lwpr', 0)),
                open_price=safe_int(row.get('stck_oprc', 0)),
                foreign_net=foreign_net,
                institution_net=institution_net,
                individual_net=individual_net,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
        except Exception as e:
            logger.error(f"[DataValidator] KIS 데이터 조회 실패: {e}")
            return None
    
    def get_naver_data(self, ticker: str) -> Optional[StockData]:
        """
        네이버 증권에서 주식 데이터 조회
        
        Args:
            ticker: 종목코드 (예: "080160")
        
        Returns:
            StockData 또는 None
        """
        try:
            # 네이버 금융 기본 정보
            url = f"https://finance.naver.com/item/main.naver?code={ticker}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 종목명
            name_elem = soup.select_one('div.wrap_company h2 a')
            name = name_elem.get_text(strip=True) if name_elem else ""
            
            # 현재가
            price_elem = soup.select_one('p.no_today span.blind')
            current_price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True).replace(',', '')
                current_price = int(price_text) if price_text.isdigit() else 0
            
            # 전일대비
            change_elem = soup.select_one('p.no_exday em span.blind')
            change = 0
            if change_elem:
                change_text = change_elem.get_text(strip=True).replace(',', '')
                if change_text.lstrip('-').isdigit():
                    change = int(change_text)
            
            # 등락률 (별도 파싱 필요)
            change_rate = 0.0
            rate_elem = soup.select_one('p.no_exday em:nth-of-type(2) span.blind')
            if rate_elem:
                rate_text = rate_elem.get_text(strip=True).replace('%', '')
                try:
                    change_rate = float(rate_text)
                except:
                    pass
            
            # 거래량
            volume = 0
            volume_elem = soup.select_one('table.no_info tr:nth-of-type(1) td:nth-of-type(3) span.blind')
            if volume_elem:
                vol_text = volume_elem.get_text(strip=True).replace(',', '')
                if vol_text.isdigit():
                    volume = int(vol_text)
            
            # 고가/저가/시가 (추가 파싱)
            high = low = open_price = 0
            
            # 투자자별 매매동향 (일별)
            foreign_net = None
            institution_net = None
            individual_net = None
            
            # 네이버 투자자별 매매동향 페이지
            investor_url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
            try:
                inv_response = requests.get(investor_url, headers=self.headers, timeout=10)
                inv_soup = BeautifulSoup(inv_response.text, 'html.parser')
                
                # 최근 1일 데이터 (첫 번째 행)
                rows = inv_soup.select('table.type2 tbody tr')
                for row in rows:
                    tds = row.find_all('td')
                    if len(tds) >= 6:
                        try:
                            # tds[3] = 외국인, tds[4] = 기관
                            foreign_text = tds[4].get_text(strip=True).replace(',', '').replace('+', '')
                            inst_text = tds[5].get_text(strip=True).replace(',', '').replace('+', '')
                            
                            if foreign_text.lstrip('-').isdigit():
                                foreign_net = int(foreign_text)
                            if inst_text.lstrip('-').isdigit():
                                institution_net = int(inst_text)
                            
                            # 개인 = -(외국인 + 기관) 근사치
                            if foreign_net is not None and institution_net is not None:
                                individual_net = -(foreign_net + institution_net)
                            
                            break  # 첫 번째 행만
                        except:
                            pass
            except Exception as e:
                logger.debug(f"[DataValidator] 네이버 투자자 데이터 조회 실패: {e}")
            
            return StockData(
                source=DataSource.NAVER,
                ticker=ticker,
                name=name,
                current_price=current_price,
                change=change,
                change_rate=change_rate,
                volume=volume,
                high=high,
                low=low,
                open_price=open_price,
                foreign_net=foreign_net,
                institution_net=institution_net,
                individual_net=individual_net,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
        except Exception as e:
            logger.error(f"[DataValidator] 네이버 데이터 조회 실패: {e}")
            return None
    
    def _compare_values(self, kis_val, naver_val, tolerance: float) -> Tuple[bool, float]:
        """
        두 값 비교 (오차 범위 내 일치 여부)
        
        Returns:
            (is_match, difference_ratio)
        """
        if kis_val is None or naver_val is None:
            return True, 0.0  # 둘 중 하나 없으면 비교 건너뜀
        
        if kis_val == 0 and naver_val == 0:
            return True, 0.0
        
        if kis_val == 0 or naver_val == 0:
            return False, 1.0  # 한쪽만 0이면 불일치
        
        diff_ratio = abs(kis_val - naver_val) / max(abs(kis_val), abs(naver_val))
        is_match = diff_ratio <= tolerance
        
        return is_match, diff_ratio
    
    def validate(self, ticker: str) -> ValidationResult:
        """
        주식 데이터 이중 검증
        
        Args:
            ticker: 종목코드
        
        Returns:
            ValidationResult
        """
        discrepancies = []
        warnings = []
        match_count = 0
        total_checks = 0
        
        # 1. 데이터 수집
        kis_data = self.get_kis_data(ticker)
        naver_data = self.get_naver_data(ticker)
        
        # 2. 데이터 가용성 체크
        if kis_data is None and naver_data is None:
            return ValidationResult(
                is_valid=False,
                match_rate=0.0,
                kis_data=None,
                naver_data=None,
                verified_data=None,
                discrepancies=["양쪽 데이터 모두 조회 실패"],
                warnings=["데이터 수집 불가"],
                recommendation="데이터 재시도 필요"
            )
        
        if kis_data is None:
            warnings.append("KIS API 데이터 없음 → 네이버 단독 사용")
            return ValidationResult(
                is_valid=True,
                match_rate=0.5,
                kis_data=None,
                naver_data=naver_data,
                verified_data=naver_data,
                discrepancies=[],
                warnings=warnings,
                recommendation="네이버 증권 데이터 사용 (KIS 불가)"
            )
        
        if naver_data is None:
            warnings.append("네이버 데이터 없음 → KIS 단독 사용")
            return ValidationResult(
                is_valid=True,
                match_rate=0.5,
                kis_data=kis_data,
                naver_data=None,
                verified_data=kis_data,
                discrepancies=[],
                warnings=warnings,
                recommendation="한국투자증권 API 데이터 사용 (네이버 불가)"
            )
        
        # 3. 데이터 비교
        
        # 3-1. 현재가 비교
        price_match, price_diff = self._compare_values(
            kis_data.current_price, naver_data.current_price, self.PRICE_TOLERANCE
        )
        total_checks += 1
        if price_match:
            match_count += 1
        else:
            discrepancies.append(
                f"현재가 불일치: KIS={kis_data.current_price:,}원, 네이버={naver_data.current_price:,}원 (차이 {price_diff*100:.2f}%)"
            )
        
        # 3-2. 거래량 비교
        vol_match, vol_diff = self._compare_values(
            kis_data.volume, naver_data.volume, self.VOLUME_TOLERANCE
        )
        total_checks += 1
        if vol_match:
            match_count += 1
        else:
            discrepancies.append(
                f"거래량 불일치: KIS={kis_data.volume:,}, 네이버={naver_data.volume:,} (차이 {vol_diff*100:.2f}%)"
            )
        
        # 3-3. 등락률 비교 (절대값으로 비교)
        # [2026-02-08 수정] KIS는 음수, 네이버는 절대값일 수 있으므로 abs() 비교
        rate_tolerance = 0.5  # 0.5%p 이내
        if kis_data.change_rate is not None and naver_data.change_rate is not None:
            # 절대값으로 비교 (부호 무시)
            rate_diff = abs(abs(kis_data.change_rate) - abs(naver_data.change_rate))
            total_checks += 1
            if rate_diff <= rate_tolerance:
                match_count += 1
            else:
                discrepancies.append(
                    f"등락률 불일치: KIS={kis_data.change_rate:.2f}%, 네이버={naver_data.change_rate:.2f}%"
                )
        
        # 3-4. 외국인 수급 비교
        if kis_data.foreign_net is not None and naver_data.foreign_net is not None:
            frgn_match, frgn_diff = self._compare_values(
                kis_data.foreign_net, naver_data.foreign_net, self.INVESTOR_TOLERANCE
            )
            total_checks += 1
            if frgn_match:
                match_count += 1
            else:
                discrepancies.append(
                    f"외국인 수급 불일치: KIS={kis_data.foreign_net:,}, 네이버={naver_data.foreign_net:,}"
                )
        
        # 3-5. 기관 수급 비교
        if kis_data.institution_net is not None and naver_data.institution_net is not None:
            inst_match, inst_diff = self._compare_values(
                kis_data.institution_net, naver_data.institution_net, self.INVESTOR_TOLERANCE
            )
            total_checks += 1
            if inst_match:
                match_count += 1
            else:
                discrepancies.append(
                    f"기관 수급 불일치: KIS={kis_data.institution_net:,}, 네이버={naver_data.institution_net:,}"
                )
        
        # 4. 일치율 계산
        match_rate = match_count / total_checks if total_checks > 0 else 0.0
        
        # 5. 검증 결과 판정
        is_valid = match_rate >= 0.8  # 80% 이상 일치 = 검증 통과
        
        # 6. 검증된 데이터 선택
        if is_valid:
            # 일치하면 KIS 데이터 우선 (실시간성)
            verified_data = StockData(
                source=DataSource.VERIFIED,
                ticker=kis_data.ticker,
                name=kis_data.name or naver_data.name,
                current_price=kis_data.current_price,
                change=kis_data.change,
                change_rate=kis_data.change_rate,
                volume=kis_data.volume,
                high=kis_data.high,
                low=kis_data.low,
                open_price=kis_data.open_price,
                foreign_net=kis_data.foreign_net or naver_data.foreign_net,
                institution_net=kis_data.institution_net or naver_data.institution_net,
                individual_net=kis_data.individual_net or naver_data.individual_net,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            recommendation = "✅ 데이터 검증 완료 (KIS + 네이버 일치)"
        else:
            # 불일치 시 네이버 우선 (거래소 공식 데이터 기반)
            verified_data = StockData(
                source=DataSource.CONFLICT,
                ticker=naver_data.ticker,
                name=naver_data.name,
                current_price=naver_data.current_price,
                change=naver_data.change,
                change_rate=naver_data.change_rate,
                volume=naver_data.volume,
                high=naver_data.high,
                low=naver_data.low,
                open_price=naver_data.open_price,
                foreign_net=naver_data.foreign_net,
                institution_net=naver_data.institution_net,
                individual_net=naver_data.individual_net,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            recommendation = f"⚠️ 데이터 불일치 ({len(discrepancies)}건) → 네이버 증권 데이터 우선 사용"
            warnings.append("KIS와 네이버 데이터 불일치 - 수동 확인 권장")
        
        return ValidationResult(
            is_valid=is_valid,
            match_rate=match_rate,
            kis_data=kis_data,
            naver_data=naver_data,
            verified_data=verified_data,
            discrepancies=discrepancies,
            warnings=warnings,
            recommendation=recommendation
        )
    
    async def validate_async(self, ticker: str) -> ValidationResult:
        """비동기 검증 (동기 함수 래핑)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.validate, ticker)
    
    def validate_multiple(self, tickers: List[str]) -> Dict[str, ValidationResult]:
        """여러 종목 일괄 검증"""
        results = {}
        for ticker in tickers:
            results[ticker] = self.validate(ticker)
        return results
    
    def format_validation_report(self, result: ValidationResult) -> str:
        """
        검증 결과를 보고서 형식으로 포맷
        """
        lines = [
            "=" * 60,
            f"📊 데이터 검증 보고서",
            "=" * 60,
            f"종목: {result.verified_data.ticker if result.verified_data else 'N/A'} ({result.verified_data.name if result.verified_data else 'N/A'})",
            f"검증 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"일치율: {result.match_rate * 100:.1f}%",
            f"검증 결과: {'✅ 통과' if result.is_valid else '⚠️ 불일치'}",
            "",
            "📌 데이터 비교:",
        ]
        
        if result.kis_data and result.naver_data:
            lines.extend([
                f"| 항목 | KIS | 네이버 |",
                f"|------|-----|--------|",
                f"| 현재가 | {result.kis_data.current_price:,}원 | {result.naver_data.current_price:,}원 |",
                f"| 등락률 | {result.kis_data.change_rate:.2f}% | {result.naver_data.change_rate:.2f}% |",
                f"| 거래량 | {result.kis_data.volume:,} | {result.naver_data.volume:,} |",
                f"| 외국인 | {result.kis_data.foreign_net or 'N/A'} | {result.naver_data.foreign_net or 'N/A'} |",
                f"| 기관 | {result.kis_data.institution_net or 'N/A'} | {result.naver_data.institution_net or 'N/A'} |",
            ])
        
        if result.discrepancies:
            lines.extend([
                "",
                "⚠️ 불일치 항목:",
            ])
            for d in result.discrepancies:
                lines.append(f"  - {d}")
        
        if result.warnings:
            lines.extend([
                "",
                "🔔 경고:",
            ])
            for w in result.warnings:
                lines.append(f"  - {w}")
        
        lines.extend([
            "",
            f"💡 권장: {result.recommendation}",
            "=" * 60,
        ])
        
        return "\n".join(lines)


# CLI 실행용
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    ticker = sys.argv[1] if len(sys.argv) > 1 else "080160"  # 기본값: 모두투어
    
    print(f"\n🔍 {ticker} 데이터 검증 중...")
    
    validator = DataValidator(is_live=True)
    result = validator.validate(ticker)
    
    print(validator.format_validation_report(result))
