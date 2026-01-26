# -*- coding: utf-8 -*-
"""
Deep Dive 투자 분석 플랫폼 - SQLite Database Manager
"""
import os
import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """SQLite 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "data", "deep_dive.db")
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """동기 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    async def get_async_connection(self) -> aiosqlite.Connection:
        """비동기 연결 반환"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn
    
    def create_tables(self):
        """모든 테이블 생성"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. 종목 마스터
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_info (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT NOT NULL,  -- KOSPI, KOSDAQ
                sector TEXT,
                listed_shares INTEGER,
                market_cap INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 일별 시세
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_price (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                open INTEGER,
                high INTEGER,
                low INTEGER,
                close INTEGER,
                volume INTEGER,
                market_cap INTEGER,
                change_rate REAL,
                UNIQUE(date, ticker)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_price_ticker ON daily_price(ticker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_price_date ON daily_price(date)")
        
        # 3. 일별 재무지표
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                per REAL,
                pbr REAL,
                roe REAL,
                eps INTEGER,
                bps INTEGER,
                dividend_yield REAL,
                UNIQUE(date, ticker)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_ticker ON daily_stats(ticker)")
        
        # 4. 일별 수급 (투자자별)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_investor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                foreign_net INTEGER,  -- 외국인 순매수 (금액)
                inst_net INTEGER,     -- 기관 순매수
                retail_net INTEGER,   -- 개인 순매수
                foreign_ratio REAL,   -- 외국인 보유비율
                UNIQUE(date, ticker)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_investor_ticker ON daily_investor(ticker)")
        
        # 5. 일별 공매도/신용
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_short_credit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                short_volume INTEGER,      -- 공매도 거래량
                short_ratio REAL,          -- 공매도 비율
                short_balance INTEGER,     -- 공매도 잔고
                credit_balance INTEGER,    -- 신용 잔고
                credit_ratio REAL,         -- 신용 비율
                UNIQUE(date, ticker)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_short_credit_ticker ON daily_short_credit(ticker)")
        
        # 6. 뉴스
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT,
                date TEXT, 
                ticker TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                sentiment_score REAL,  -- -1 ~ 1
                source TEXT,
                url TEXT,
                link TEXT,
                provider TEXT,
                UNIQUE(ticker, link)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_ticker ON stock_news(ticker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_date ON stock_news(date)")
        
        # News Metrics (Daily aggregated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                news_count INTEGER,
                sentiment_score REAL,
                UNIQUE(date, ticker)
            )
        """)

        # 7. DART 공시
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dart_disclosure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                title TEXT NOT NULL,
                disclosure_type TEXT,  -- 수주, 실적, 유증 등
                impact_level TEXT,     -- positive, negative, neutral
                url TEXT,
                UNIQUE(date, ticker, title)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dart_disclosure_ticker ON dart_disclosure(ticker)")
        
        # 8. 유튜브 지표 (Phase 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS youtube_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                video_count INTEGER,
                total_views INTEGER,
                avg_likes INTEGER,
                sentiment_score REAL,
                UNIQUE(date, ticker)
            )
        """)
        
        # 9. 네이버 토론실 (Phase 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS naver_discussion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                post_count INTEGER,
                avg_views INTEGER,
                like_ratio REAL,
                sentiment_score REAL,
                UNIQUE(date, ticker)
            )
        """)
        
        # 10. 인간 지표 종합 (Phase 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                attention_score REAL,   -- 관심도 0~100
                fomo_level REAL,        -- FOMO 지수 0~100
                crowd_sentiment REAL,   -- 군중 감성 -1~1
                UNIQUE(date, ticker)
            )
        """)
        
        # 11. 업종/테마 일별
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                sector_code TEXT NOT NULL,
                sector_name TEXT NOT NULL,
                change_rate REAL,
                volume INTEGER,
                foreign_net INTEGER,
                UNIQUE(date, sector_code)
            )
        """)
        
        # 12. 해외 시장
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,  -- SPY, QQQ, DXY, VIX 등
                close_price REAL,
                change_rate REAL,
                UNIQUE(date, symbol)
            )
        """)
        
        # 13. 알림 규칙
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                condition TEXT NOT NULL,  -- JSON 형태로 조건 저장
                channel TEXT NOT NULL,    -- telegram, email 등
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 14. 백테스트 결과
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                total_return REAL,
                win_rate REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                params TEXT,  -- JSON
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 15. 매매 일지
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,  -- BUY, SELL
                price REAL NOT NULL,
                qty INTEGER NOT NULL,
                thesis TEXT,          -- 매매 근거
                ai_feedback TEXT,     -- AI 피드백
                pnl REAL,             -- 실현 손익
                date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_journal_ticker ON trade_journal(ticker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_journal_date ON trade_journal(date)")
        
        # 16. 데이터 수집 로그
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                collection_type TEXT NOT NULL,  -- price, stats, investor, etc.
                total_count INTEGER,
                success_count INTEGER,
                failed_count INTEGER,
                duration_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 17. 섹터 분석 결과
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sector_analysis (
                sector_name TEXT PRIMARY KEY,
                data TEXT NOT NULL,  -- JSON data
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 18. 시스템 설정 (System Config)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 마이그레이션 실행
        self._migrate_tables(conn)
        
        conn.commit()
        conn.close()
        print(f"[Database] All tables created at {self.db_path}")

    def _migrate_tables(self, conn: sqlite3.Connection):
        """스키마 변경사항 마이그레이션"""
        cursor = conn.cursor()
        
        # 1. daily_investor: inst_net 추가
        try:
            cursor.execute("SELECT inst_net FROM daily_investor LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating daily_investor: adding inst_net column")
            cursor.execute("ALTER TABLE daily_investor ADD COLUMN inst_net INTEGER")
            
        # 2. daily_investor: retail_net 추가
        try:
            cursor.execute("SELECT retail_net FROM daily_investor LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating daily_investor: adding retail_net column")
            cursor.execute("ALTER TABLE daily_investor ADD COLUMN retail_net INTEGER")
            
        # 3. daily_investor: foreign_ratio 추가
        try:
            cursor.execute("SELECT foreign_ratio FROM daily_investor LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating daily_investor: adding foreign_ratio column")
            cursor.execute("ALTER TABLE daily_investor ADD COLUMN foreign_ratio REAL")
        
        # 4. stock_news: link, provider, date 추가
        try:
            cursor.execute("SELECT link FROM stock_news LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating stock_news: adding link column")
            cursor.execute("ALTER TABLE stock_news ADD COLUMN link TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_news_ticker_link ON stock_news(ticker, link)")
        
        try:
            cursor.execute("SELECT provider FROM stock_news LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating stock_news: adding provider column")
            cursor.execute("ALTER TABLE stock_news ADD COLUMN provider TEXT")
        
        try:
            cursor.execute("SELECT date FROM stock_news LIMIT 1")
        except sqlite3.OperationalError:
             print("[Database] Migrating stock_news: adding date column")
             cursor.execute("ALTER TABLE stock_news ADD COLUMN date TEXT")
             cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_news_date ON stock_news(date)")
        
        # 5. stock_info: fwd_eps 추가
        try:
            cursor.execute("SELECT fwd_eps FROM stock_info LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating stock_info: adding fwd_eps column")
            cursor.execute("ALTER TABLE stock_info ADD COLUMN fwd_eps REAL")

        # 6. stock_info: opentalk_users 추가
        try:
            cursor.execute("SELECT opentalk_users FROM stock_info LIMIT 1")
        except sqlite3.OperationalError:
            print("[Database] Migrating stock_info: adding opentalk_users column")
            cursor.execute("ALTER TABLE stock_info ADD COLUMN opentalk_users INTEGER")
    
    async def execute(self, query: str, params: tuple = ()) -> None:
        """비동기 쿼리 실행 (INSERT, UPDATE, DELETE)"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(query, params)
            await conn.commit()
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """비동기 배치 실행"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executemany(query, params_list)
            await conn.commit()
    
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """비동기 단일 행 조회"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """비동기 다중 행 조회"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def upsert_stock_info(self, stocks: List[Dict]) -> int:
        """종목 정보 upsert"""
        query = """
            INSERT INTO stock_info (ticker, name, market, sector, listed_shares, market_cap, fwd_eps, opentalk_users, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                fwd_eps = excluded.fwd_eps,
                opentalk_users = excluded.opentalk_users,
                sector = excluded.sector,
                listed_shares = excluded.listed_shares,
                market_cap = excluded.market_cap,
                updated_at = excluded.updated_at
        """
        now = datetime.now().isoformat()
        params = [
            (s['ticker'], s['name'], s['market'], s.get('sector'), 
             s.get('listed_shares'), s.get('market_cap'), s.get('fwd_eps'), s.get('opentalk_users'), now)
            for s in stocks
        ]
        await self.execute_many(query, params)
        return len(params)
    
    async def upsert_daily_price(self, data: List[Dict]) -> int:
        """일별 시세 upsert"""
        query = """
            INSERT INTO daily_price (date, ticker, open, high, low, close, volume, market_cap, change_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                market_cap = excluded.market_cap,
                change_rate = excluded.change_rate
        """
        params = [
            (d['date'], d['ticker'], d.get('open'), d.get('high'), d.get('low'),
             d.get('close'), d.get('volume'), d.get('market_cap'), d.get('change_rate'))
            for d in data
        ]
        await self.execute_many(query, params)
        return len(params)
    
    async def upsert_daily_stats(self, data: List[Dict]) -> int:
        """일별 재무지표 upsert"""
        query = """
            INSERT INTO daily_stats (date, ticker, per, pbr, roe, eps, bps, dividend_yield)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                per = excluded.per,
                pbr = excluded.pbr,
                roe = excluded.roe,
                eps = excluded.eps,
                bps = excluded.bps,
                dividend_yield = excluded.dividend_yield
        """
        params = [
            (d['date'], d['ticker'], d.get('per'), d.get('pbr'), d.get('roe'),
             d.get('eps'), d.get('bps'), d.get('dividend_yield'))
            for d in data
        ]
        await self.execute_many(query, params)
        return len(params)
    
    async def upsert_daily_investor(self, data: List[Dict]) -> int:
        """일별 수급 upsert"""
        query = """
            INSERT INTO daily_investor (date, ticker, foreign_net, inst_net, retail_net, foreign_ratio)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                foreign_net = excluded.foreign_net,
                inst_net = excluded.inst_net,
                retail_net = excluded.retail_net,
                foreign_ratio = excluded.foreign_ratio
        """
        params = [
            (d['date'], d['ticker'], d.get('foreign_net'), d.get('inst_net'),
             d.get('retail_net'), d.get('foreign_ratio'))
            for d in data
        ]
        await self.execute_many(query, params)
        return len(params)
    
    async def upsert_daily_short_credit(self, data: List[Dict]) -> int:
        """공매도/신용 upsert"""
        query = """
            INSERT INTO daily_short_credit (date, ticker, short_volume, short_ratio, short_balance, credit_balance, credit_ratio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                short_volume = excluded.short_volume,
                short_ratio = excluded.short_ratio,
                short_balance = excluded.short_balance,
                credit_balance = excluded.credit_balance,
                credit_ratio = excluded.credit_ratio
        """
        params = [
            (d['date'], d['ticker'], d.get('short_volume'), d.get('short_ratio'),
             d.get('short_balance'), d.get('credit_balance'), d.get('credit_ratio'))
            for d in data
        ]
        await self.execute_many(query, params)
        return len(params)
    
    async def log_collection(self, collection_type: str, total: int, success: int, failed: int, duration: float):
        """수집 로그 기록"""
        query = """
            INSERT INTO collection_log (date, collection_type, total_count, success_count, failed_count, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        await self.execute(query, (today, collection_type, total, success, failed, duration))

    async def get_config(self, key: str) -> Optional[str]:
        """시스템 설정 조회"""
        row = await self.fetch_one("SELECT value FROM system_config WHERE key = ?", (key,))
        return row['value'] if row else None

    async def set_config(self, key: str, value: str):
        """시스템 설정 저장"""
        query = """
            INSERT INTO system_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """
        await self.execute(query, (key, value))


# 싱글톤 인스턴스
_db_instance: Optional[Database] = None

def get_database() -> Database:
    """데이터베이스 싱글톤 인스턴스 반환"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.create_tables()
    return _db_instance
