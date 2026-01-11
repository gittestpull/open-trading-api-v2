# -*- coding: utf-8 -*-
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests

from .database import Database, get_database

logger = logging.getLogger(__name__)

DART_API_URL = "https://opendart.fss.or.kr/api"


class DartCollector:
    
    def __init__(self, api_key: str = None, db: Database = None):
        self.api_key = api_key or os.getenv("DART_API_KEY")
        self.db = db or get_database()
    
    def get_corp_code(self, ticker: str) -> Optional[str]:
        if not self.api_key:
            return None
        
        try:
            response = requests.get(
                f"{DART_API_URL}/corpCode.xml",
                params={'crtfc_key': self.api_key},
                timeout=30
            )
            return None
        except Exception:
            return None
    
    def get_disclosures(self, corp_code: str = None, ticker: str = None, 
                        days_back: int = 30) -> List[Dict]:
        if not self.api_key:
            logger.warning("[DART] API key not set")
            return []
        
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
            
            params = {
                'crtfc_key': self.api_key,
                'bgn_de': start_date,
                'end_de': end_date,
                'page_count': 100,
                'sort': 'date',
                'sort_mth': 'desc'
            }
            
            if corp_code:
                params['corp_code'] = corp_code
            
            response = requests.get(
                f"{DART_API_URL}/list.json",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != '000':
                return []
            
            disclosures = []
            for item in data.get('list', []):
                impact = self._analyze_impact(item.get('report_nm', ''))
                disclosures.append({
                    'date': item.get('rcept_dt', ''),
                    'corp_name': item.get('corp_name', ''),
                    'corp_code': item.get('corp_code', ''),
                    'title': item.get('report_nm', ''),
                    'disclosure_type': self._classify_type(item.get('report_nm', '')),
                    'impact_level': impact,
                    'url': f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no', '')}"
                })
            
            return disclosures
        except Exception as e:
            logger.error(f"[DART] Fetch failed: {e}")
            return []
    
    def _classify_type(self, title: str) -> str:
        title_lower = title.lower()
        
        if '수주' in title_lower:
            return 'contract'
        elif '실적' in title_lower or '영업' in title_lower or '매출' in title_lower:
            return 'earnings'
        elif '유상증자' in title_lower:
            return 'capital_increase'
        elif '무상증자' in title_lower:
            return 'bonus_issue'
        elif '배당' in title_lower:
            return 'dividend'
        elif '합병' in title_lower or '인수' in title_lower:
            return 'merger'
        elif '대표' in title_lower or '임원' in title_lower:
            return 'management'
        elif '소송' in title_lower or '분쟁' in title_lower:
            return 'legal'
        else:
            return 'general'
    
    def _analyze_impact(self, title: str) -> str:
        positive_keywords = ['수주', '계약', '배당', '무상증자', '실적개선', '흑자', '매출증가']
        negative_keywords = ['유상증자', '손실', '적자', '소송', '감자', '상폐', '관리종목']
        
        title_lower = title.lower()
        
        pos_count = sum(1 for kw in positive_keywords if kw in title_lower)
        neg_count = sum(1 for kw in negative_keywords if kw in title_lower)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        else:
            return 'neutral'
    
    async def collect_for_stock(self, ticker: str, corp_code: str = None) -> List[Dict]:
        disclosures = self.get_disclosures(corp_code=corp_code, days_back=30)
        
        if not disclosures:
            return []
        
        for d in disclosures:
            try:
                await self.db.execute("""
                    INSERT INTO dart_disclosure (date, ticker, title, disclosure_type, impact_level, url)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, ticker, title) DO UPDATE SET
                        disclosure_type = excluded.disclosure_type,
                        impact_level = excluded.impact_level,
                        url = excluded.url
                """, (d['date'], ticker, d['title'], d['disclosure_type'], d['impact_level'], d['url']))
            except Exception as e:
                logger.debug(f"[DART] Save failed: {e}")
        
        return disclosures
    
    async def get_recent_disclosures(self, ticker: str, limit: int = 10) -> List[Dict]:
        return await self.db.fetch_all(
            "SELECT * FROM dart_disclosure WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker, limit)
        )


_dart_instance: Optional[DartCollector] = None

def get_dart_collector() -> DartCollector:
    global _dart_instance
    if _dart_instance is None:
        _dart_instance = DartCollector()
    return _dart_instance
