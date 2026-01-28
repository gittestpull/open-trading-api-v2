# -*- coding: utf-8 -*-
"""
섹터 분석 데이터 수집기
- 특정 종목이 속한 섹터의 1년간 모든 관련 데이터를 수집
- PyKRX를 활용한 업종 지수, 투자자 매매동향, 밸류에이션 수집
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

import pandas as pd
from pykrx import stock

from .database import Database, get_database
from .stock_master import get_stock_master_service

logger = logging.getLogger(__name__)

# KRX 주요 업종 코드 매핑
SECTOR_CODE_MAP = {
    # KOSPI 업종
    "1001": "코스피",
    "1002": "코스피 대형주",
    "1003": "코스피 중형주",
    "1004": "코스피 소형주",
    "1005": "음식료품",
    "1006": "섬유의복",
    "1007": "종이목재",
    "1008": "화학",
    "1009": "의약품",
    "1010": "비금속광물",
    "1011": "철강금속",
    "1012": "기계",
    "1013": "전기전자",
    "1014": "의료정밀",
    "1015": "운수장비",
    "1016": "유통업",
    "1017": "전기가스업",
    "1018": "건설업",
    "1019": "운수창고",
    "1020": "통신업",
    "1021": "금융업",
    "1022": "은행",
    "1024": "증권",
    "1025": "보험",
    "1026": "서비스업",
    "1027": "제조업",
    "1028": "코스피 200",
    "1034": "코스피 100",
    "1035": "코스피 50",
    # KOSDAQ 업종
    "2001": "코스닥",
    "2002": "코스닥 대형주",
    "2003": "코스닥 중형주",
    "2004": "코스닥 소형주",
    "2024": "제조",
    "2025": "음식료·담배",
    "2026": "섬유·의류",
    "2027": "종이·목재",
    "2028": "출판·매체복제",
    "2029": "화학",
    "2030": "제약",
    "2031": "비금속",
    "2032": "금속",
    "2033": "기계·장비",
    "2034": "일반전기전자",
    "2035": "의료·정밀기기",
    "2036": "운송장비·부품",
    "2037": "기타 제조",
    "2041": "건설",
    "2042": "유통",
    "2043": "운송",
    "2044": "금융",
    "2056": "오락·문화",
    "2058": "통신방송서비스",
    "2063": "IT S/W & SVC",
    "2064": "IT H/W",
    "2068": "반도체",
    "2069": "IT부품",
    "2070": "디지털컨텐츠",
}

# 섹터 키워드 매핑 (종목 섹터명 -> 업종 코드)
SECTOR_KEYWORD_MAP = {
    "전기전자": ["1013", "2034"],
    "반도체": ["2068", "1013"],
    "화학": ["1008", "2029"],
    "의약품": ["1009", "2030"],
    "제약": ["1009", "2030"],
    "바이오": ["1009", "2030"],
    "자동차": ["1015"],
    "운수장비": ["1015", "2036"],
    "금융": ["1021", "2044"],
    "은행": ["1022"],
    "증권": ["1024"],
    "보험": ["1025"],
    "건설": ["1018", "2041"],
    "유통": ["1016", "2042"],
    "통신": ["1020", "2043"],
    "서비스": ["1026"],
    "IT": ["2063", "2064"],
    "소프트웨어": ["2063"],
    "하드웨어": ["2064"],
    "철강": ["1011"],
    "기계": ["1012", "2033"],
}


@dataclass
class SectorInfo:
    """섹터 정보 데이터 클래스"""
    sector_code: str
    sector_name: str
    market: str  # KOSPI or KOSDAQ


@dataclass
class SectorAnalysisResult:
    """섹터 분석 결과"""
    ticker: str
    stock_name: str
    sector_info: SectorInfo
    ohlcv_data: pd.DataFrame
    investor_data: pd.DataFrame
    relative_strength: Dict
    sector_leaders: List[Dict]
    sector_laggards: List[Dict]


class SectorAnalysisCollector:
    """섹터 분석 데이터 수집 및 분석 클래스"""

    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.stock_service = get_stock_master_service()
        self._ensure_tables()

    def _ensure_tables(self):
        """섹터 분석 관련 테이블 생성"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 섹터 정보 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_info (
                sector_code TEXT PRIMARY KEY,
                sector_name TEXT NOT NULL,
                market TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 종목-섹터 매핑 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_sector_map (
                ticker TEXT NOT NULL,
                sector_code TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, sector_code)
            )
        """)

        # 섹터 일별 OHLCV 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_ohlcv (
                date TEXT NOT NULL,
                sector_code TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                trade_value INTEGER,
                change_rate REAL,
                PRIMARY KEY (date, sector_code)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sector_ohlcv_code ON sector_ohlcv(sector_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sector_ohlcv_date ON sector_ohlcv(date)")

        # 섹터 투자자별 매매동향 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_investor (
                date TEXT NOT NULL,
                sector_code TEXT NOT NULL,
                foreign_net INTEGER,
                inst_net INTEGER,
                retail_net INTEGER,
                foreign_cum INTEGER,
                inst_cum INTEGER,
                PRIMARY KEY (date, sector_code)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sector_investor_code ON sector_investor(sector_code)")

        # 섹터 밸류에이션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_valuation (
                date TEXT NOT NULL,
                sector_code TEXT NOT NULL,
                avg_per REAL,
                avg_pbr REAL,
                avg_div_yield REAL,
                PRIMARY KEY (date, sector_code)
            )
        """)

        # 섹터 분석 결과 캐시 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_analysis_cache (
                ticker TEXT PRIMARY KEY,
                sector_code TEXT NOT NULL,
                analysis_data TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info("[SectorAnalysis] Tables created/verified")

    async def find_sector_for_stock(self, ticker: str) -> Optional[SectorInfo]:
        """종목의 섹터 정보 조회"""
        # 1. 먼저 DB에서 종목 정보 조회
        stock_info = await self.stock_service.get_stock_info(ticker)
        if not stock_info:
            logger.warning(f"[SectorAnalysis] Stock not found: {ticker}")
            return None

        sector_name = stock_info.get('sector', '')
        market = stock_info.get('market', 'KOSPI')

        # 2. 섹터 키워드로 업종 코드 매핑
        sector_codes = []
        for keyword, codes in SECTOR_KEYWORD_MAP.items():
            if keyword in sector_name:
                sector_codes.extend(codes)
                break

        # 3. 매핑되지 않으면 시장 기준 기본 업종 사용
        if not sector_codes:
            if market == 'KOSDAQ':
                sector_codes = ['2001']  # 코스닥 전체
            else:
                sector_codes = ['1001']  # 코스피 전체

        sector_code = sector_codes[0]
        sector_full_name = SECTOR_CODE_MAP.get(sector_code, sector_name)

        return SectorInfo(
            sector_code=sector_code,
            sector_name=sector_full_name,
            market=market
        )

    async def collect_sector_ohlcv(self, sector_code: str, days: int = 365) -> pd.DataFrame:
        """섹터 OHLCV 데이터 수집 (1년)"""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        logger.info(f"[SectorAnalysis] Collecting OHLCV for {sector_code}: {start_date} ~ {end_date}")

        try:
            df = stock.get_index_ohlcv_by_date(start_date, end_date, sector_code)

            if df.empty:
                logger.warning(f"[SectorAnalysis] No OHLCV data for sector {sector_code}")
                return pd.DataFrame()

            # DB에 저장
            for date_idx, row in df.iterrows():
                date_str = date_idx.strftime("%Y-%m-%d")

                # 변화율 계산
                change_rate = None
                if '등락률' in row:
                    change_rate = row['등락률']

                await self.db.execute("""
                    INSERT INTO sector_ohlcv (date, sector_code, open, high, low, close, volume, trade_value, change_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, sector_code) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume, 
                        trade_value=excluded.trade_value, change_rate=excluded.change_rate
                """, (
                    date_str, sector_code,
                    float(row.get('시가', 0)), float(row.get('고가', 0)),
                    float(row.get('저가', 0)), float(row.get('종가', 0)),
                    int(row.get('거래량', 0)), int(row.get('거래대금', 0)),
                    change_rate
                ))

            logger.info(f"[SectorAnalysis] Saved {len(df)} OHLCV records for {sector_code}")
            return df

        except Exception as e:
            logger.error(f"[SectorAnalysis] Failed to collect OHLCV for {sector_code}: {e}")
            return pd.DataFrame()

    async def collect_sector_investor_flow(self, sector_code: str, days: int = 365) -> pd.DataFrame:
        """섹터 투자자별 매매동향 수집"""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        logger.info(f"[SectorAnalysis] Collecting investor flow for {sector_code}")

        try:
            # 시장 전체 매매동향 (KOSPI/KOSDAQ)
            market = "KOSPI" if sector_code.startswith("1") else "KOSDAQ"

            df = stock.get_market_trading_value_by_date(start_date, end_date, market)

            if df.empty:
                logger.warning(f"[SectorAnalysis] No investor data for {market}")
                return pd.DataFrame()

            # 누적 순매수 계산
            foreign_cum = 0
            inst_cum = 0

            for date_idx, row in df.iterrows():
                date_str = date_idx.strftime("%Y-%m-%d")

                foreign_net = int(row.get('외국인', 0))
                inst_net = int(row.get('기관합계', 0))
                retail_net = int(row.get('개인', 0))

                foreign_cum += foreign_net
                inst_cum += inst_net

                await self.db.execute("""
                    INSERT INTO sector_investor (date, sector_code, foreign_net, inst_net, retail_net, foreign_cum, inst_cum)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, sector_code) DO UPDATE SET
                        foreign_net=excluded.foreign_net, inst_net=excluded.inst_net,
                        retail_net=excluded.retail_net, foreign_cum=excluded.foreign_cum,
                        inst_cum=excluded.inst_cum
                """, (date_str, sector_code, foreign_net, inst_net, retail_net, foreign_cum, inst_cum))

            logger.info(f"[SectorAnalysis] Saved {len(df)} investor records for {sector_code}")
            return df

        except Exception as e:
            logger.error(f"[SectorAnalysis] Failed to collect investor flow: {e}")
            return pd.DataFrame()

    async def collect_sector_stocks(self, sector_code: str) -> List[Dict]:
        """섹터 내 종목 리스트 수집"""
        try:
            today = datetime.now().strftime("%Y%m%d")

            # 해당 업종에 속한 종목들의 시가총액 조회
            market = "KOSPI" if sector_code.startswith("1") else "KOSDAQ"

            # 전체 종목 시가총액 조회
            df = stock.get_market_cap_by_ticker(today, market=market)

            if df.empty:
                return []

            # 상위 50개 종목 (시가총액 기준)
            df = df.nlargest(50, '시가총액')

            stocks = []
            for ticker, row in df.iterrows():
                stocks.append({
                    'ticker': ticker,
                    'market_cap': int(row.get('시가총액', 0)),
                    'volume': int(row.get('거래량', 0)),
                    'trade_value': int(row.get('거래대금', 0))
                })

            return stocks

        except Exception as e:
            logger.error(f"[SectorAnalysis] Failed to collect sector stocks: {e}")
            return []

    async def calculate_relative_strength(self, ticker: str, sector_code: str, days: int = 20) -> Dict:
        """상대 강도(RS) 계산 - 종목 vs 섹터 vs 시장"""
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days*2)).strftime("%Y%m%d")

            # 종목 데이터
            stock_df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)

            # 섹터 데이터
            sector_df = stock.get_index_ohlcv_by_date(start_date, end_date, sector_code)

            # 시장(KOSPI) 데이터
            market_df = stock.get_index_ohlcv_by_date(start_date, end_date, "1001")

            if stock_df.empty or sector_df.empty or market_df.empty:
                return {}

            # 최근 N일 수익률 계산
            stock_return = (stock_df['종가'].iloc[-1] / stock_df['종가'].iloc[-days] - 1) * 100
            sector_return = (sector_df['종가'].iloc[-1] / sector_df['종가'].iloc[-days] - 1) * 100
            market_return = (market_df['종가'].iloc[-1] / market_df['종가'].iloc[-days] - 1) * 100

            # 상대 강도 계산
            rs_vs_sector = stock_return - sector_return
            rs_vs_market = stock_return - market_return
            sector_vs_market = sector_return - market_return

            return {
                'stock_return': round(stock_return, 2),
                'sector_return': round(sector_return, 2),
                'market_return': round(market_return, 2),
                'rs_vs_sector': round(rs_vs_sector, 2),
                'rs_vs_market': round(rs_vs_market, 2),
                'sector_vs_market': round(sector_vs_market, 2),
                'is_sector_leader': rs_vs_sector > 0,
                'is_market_leader': rs_vs_market > 0,
                'sector_is_strong': sector_vs_market > 0,
                'period_days': days
            }

        except Exception as e:
            logger.error(f"[SectorAnalysis] Failed to calculate RS: {e}")
            return {}

    async def analyze_sector(self, ticker: str, days: int = 365) -> Dict:
        """종목의 섹터 종합 분석 실행"""
        logger.info(f"[SectorAnalysis] Starting analysis for {ticker}")

        # 1. 섹터 정보 조회
        sector_info = await self.find_sector_for_stock(ticker)
        if not sector_info:
            return {"error": "Stock not found"}

        stock_info = await self.stock_service.get_stock_info(ticker)

        # 2. 섹터 OHLCV 수집
        ohlcv_df = await self.collect_sector_ohlcv(sector_info.sector_code, days)

        # 3. 투자자 매매동향 수집
        investor_df = await self.collect_sector_investor_flow(sector_info.sector_code, days)

        # 4. 상대 강도 계산
        rs_data = await self.calculate_relative_strength(ticker, sector_info.sector_code)

        # 5. 섹터 내 종목 수집
        sector_stocks = await self.collect_sector_stocks(sector_info.sector_code)

        # 결과 저장
        import json
        result = {
            "ticker": ticker,
            "stock_name": stock_info.get('name', '') if stock_info else '',
            "sector_code": sector_info.sector_code,
            "sector_name": sector_info.sector_name,
            "market": sector_info.market,
            "relative_strength": rs_data,
            "sector_stocks_count": len(sector_stocks),
            "ohlcv_records": len(ohlcv_df) if not ohlcv_df.empty else 0,
            "investor_records": len(investor_df) if not investor_df.empty else 0,
            "collected_at": datetime.now().isoformat()
        }

        await self.db.execute("""
            INSERT INTO sector_analysis_cache (ticker, sector_code, analysis_data, collected_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                sector_code=excluded.sector_code,
                analysis_data=excluded.analysis_data,
                collected_at=excluded.collected_at,
                updated_at=CURRENT_TIMESTAMP
        """, (ticker, sector_info.sector_code, json.dumps(result, ensure_ascii=False), datetime.now().isoformat()))

        logger.info(f"[SectorAnalysis] Analysis complete for {ticker}")
        return result

    async def get_sector_summary(self, ticker: str) -> Dict:
        """섹터 요약 정보 조회"""
        sector_info = await self.find_sector_for_stock(ticker)
        if not sector_info:
            return {"error": "Stock not found"}

        # 최근 OHLCV 데이터
        ohlcv = await self.db.fetch_all("""
            SELECT * FROM sector_ohlcv 
            WHERE sector_code = ?
            ORDER BY date DESC LIMIT 30
        """, (sector_info.sector_code,))

        # 최근 투자자 데이터
        investor = await self.db.fetch_all("""
            SELECT * FROM sector_investor
            WHERE sector_code = ?
            ORDER BY date DESC LIMIT 30
        """, (sector_info.sector_code,))

        # RS 계산
        rs_data = await self.calculate_relative_strength(ticker, sector_info.sector_code)

        return {
            "sector_code": sector_info.sector_code,
            "sector_name": sector_info.sector_name,
            "market": sector_info.market,
            "ohlcv": ohlcv,
            "investor_flow": investor,
            "relative_strength": rs_data
        }

    async def get_sector_history(self, sector_code: str, days: int = 365) -> List[Dict]:
        """섹터 히스토리 데이터 조회"""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        return await self.db.fetch_all("""
            SELECT o.*, i.foreign_net, i.inst_net, i.retail_net, i.foreign_cum, i.inst_cum
            FROM sector_ohlcv o
            LEFT JOIN sector_investor i ON o.date = i.date AND o.sector_code = i.sector_code
            WHERE o.sector_code = ? AND o.date >= ?
            ORDER BY o.date ASC
        """, (sector_code, start_date))

    async def get_rotation_heatmap(self) -> List[Dict]:
        """업종 순환매 히트맵 데이터"""
        sectors = ["1001", "1013", "1009", "1008", "1021", "2001", "2068", "2030"]

        results = []
        for sector_code in sectors:
            sector_name = SECTOR_CODE_MAP.get(sector_code, sector_code)

            # 각 기간별 수익률 계산
            for period, days in [("1W", 5), ("1M", 20), ("3M", 60)]:
                data = await self.db.fetch_all("""
                    SELECT close FROM sector_ohlcv
                    WHERE sector_code = ?
                    ORDER BY date DESC LIMIT ?
                """, (sector_code, days + 1))

                if len(data) > 1:
                    returns = (data[0]['close'] / data[-1]['close'] - 1) * 100
                else:
                    returns = 0

                results.append({
                    "sector_code": sector_code,
                    "sector_name": sector_name,
                    "period": period,
                    "returns": round(returns, 2)
                })

        return results


# 싱글톤 인스턴스
_sector_analysis_instance: Optional[SectorAnalysisCollector] = None

def get_sector_analysis_collector() -> SectorAnalysisCollector:
    """섹터 분석 수집기 싱글톤 인스턴스 반환"""
    global _sector_analysis_instance
    if _sector_analysis_instance is None:
        _sector_analysis_instance = SectorAnalysisCollector()
    return _sector_analysis_instance
