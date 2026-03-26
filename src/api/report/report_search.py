from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime

# TODO: 실제 증권사 리포트 크롤링 로직 연동 (한경 컨센서스 등)
# 현재는 Mock Data로 구현

router = APIRouter()
logger = logging.getLogger(__name__)

class ReportItem(BaseModel):
    title: str
    source: str
    date: str
    analyst: str
    target_price: Optional[int] = None
    opinion: Optional[str] = None
    link: Optional[str] = None
    summary: Optional[str] = None
    related_stocks: List[str] = []

@router.get("/search", response_model=List[ReportItem])
async def search_reports(keyword: str = Query(..., min_length=2)):
    """
    증권사 리포트 검색 (키워드 기반)
    """
    logger.info(f"Report search requested for keyword: {keyword}")
    
    # Mock Data (나중에 실제 크롤러 연동)
    mock_reports = [
        ReportItem(
            title="2026년 조선업 전망: 한국 조선업에 다시 오는 두 마리 토끼의 해",
            source="신영증권",
            date="2025-11-17",
            analyst="엄경아",
            target_price=None,
            opinion="Positive",
            link="https://example.com/report1.pdf",
            summary="상선 시황 호조와 미군 MRO/방산 시장 개화의 수혜 기대. 오리엔탈정공 등 기자재주 주목.",
            related_stocks=["014940", "009540", "042660"] # 오리엔탈정공, HD한국조선해양, 한화오션
        ),
        ReportItem(
            title=f"{keyword} 산업 심층 분석: 다가오는 슈퍼사이클",
            source="태광증권",
            date=datetime.now().strftime("%Y-%m-%d"),
            analyst="AI Analyst",
            opinion="Buy",
            summary=f"{keyword} 관련 전방 산업 수요 급증 예상. 밸류체인 전반적 재평가 필요.",
            related_stocks=["005930"]
        )
    ]
    
    # 간단한 필터링
    return [r for r in mock_reports if keyword in r.title or keyword in r.summary]

@router.get("/latest", response_model=List[ReportItem])
async def get_latest_reports(limit: int = 10):
    """최신 리포트 조회"""
    return [
        ReportItem(
            title="2026년 조선업 전망: 한국 조선업에 다시 오는 두 마리 토끼의 해",
            source="신영증권",
            date="2025-11-17",
            analyst="엄경아",
            summary="상선 시황 호조와 미군 MRO/방산 시장 개화의 수혜 기대.",
            related_stocks=["014940", "009540"]
        )
    ]
