# -*- coding: utf-8 -*-
"""
Human Sentiment Analyst - FOMO/관심도 기반 투자심리 분석.

Design Principle: "계산은 Python이, 해석은 AI가"
- 휴먼지표 데이터를 구조화하여 AI 프롬프트에 주입
- 역발상 투자 시그널 감지
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .database import Database, get_database
from .human_index import get_human_index_calculator

logger = logging.getLogger(__name__)


@dataclass
class SentimentSummary:
    """Pre-calculated sentiment indicators for AI consumption."""
    ticker: str
    stock_name: str
    calculated_at: str
    
    # Current Values
    attention_score: float       # 0-100, 관심도
    fomo_level: float           # 0-100, FOMO 지수
    crowd_sentiment: float      # -1 to 1, 군중 감성
    
    # Trend (vs 7 days ago)
    attention_trend: str        # "rising", "stable", "falling"
    attention_change_7d: float  # % change
    fomo_trend: str
    fomo_change_7d: float
    
    # YouTube Metrics
    youtube_video_count: int
    youtube_total_views: int
    youtube_sentiment: Optional[float]
    youtube_signal: str         # "viral", "active", "normal", "quiet"
    
    # Naver Metrics
    naver_post_count: int
    naver_like_ratio: Optional[float]
    naver_sentiment: Optional[float]
    naver_signal: str           # "hot", "active", "normal", "quiet"
    
    # Investment Signals
    fomo_alert: bool            # FOMO >= 70
    contrarian_signal: bool     # Attention < 20 AND sentiment < 0
    sentiment_extreme: str      # "euphoria", "fear", "neutral"
    
    # Composite Score
    crowd_behavior_score: float  # 0-100, 군중 행동 점수 (높을수록 과열)
    smart_money_hint: str        # "accumulating", "distributing", "neutral"
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "calculated_at": self.calculated_at,
            "current": {
                "attention_score": self.attention_score,
                "fomo_level": self.fomo_level,
                "crowd_sentiment": self.crowd_sentiment,
            },
            "trend_7d": {
                "attention_trend": self.attention_trend,
                "attention_change_pct": self.attention_change_7d,
                "fomo_trend": self.fomo_trend,
                "fomo_change_pct": self.fomo_change_7d,
            },
            "youtube": {
                "video_count": self.youtube_video_count,
                "total_views": self.youtube_total_views,
                "sentiment": self.youtube_sentiment,
                "signal": self.youtube_signal,
            },
            "naver": {
                "post_count": self.naver_post_count,
                "like_ratio": self.naver_like_ratio,
                "sentiment": self.naver_sentiment,
                "signal": self.naver_signal,
            },
            "signals": {
                "fomo_alert": self.fomo_alert,
                "contrarian_signal": self.contrarian_signal,
                "sentiment_extreme": self.sentiment_extreme,
                "crowd_behavior_score": self.crowd_behavior_score,
                "smart_money_hint": self.smart_money_hint,
            },
        }
    
    def to_prompt_text(self) -> str:
        """Generate text summary for GPT prompt injection."""
        lines = [
            f"[투자심리 지표 - {self.stock_name} ({self.ticker})]",
            "",
            "현재 상태:",
            f"  관심도: {self.attention_score:.1f}/100 ({self.attention_trend}, 7일 전 대비 {self.attention_change_7d:+.1f}%)",
            f"  FOMO 지수: {self.fomo_level:.1f}/100 ({self.fomo_trend}, 7일 전 대비 {self.fomo_change_7d:+.1f}%)",
            f"  군중 감성: {self.crowd_sentiment:+.2f} (-1=공포, +1=탐욕)",
            "",
            "소셜 미디어:",
            f"  유튜브: 영상 {self.youtube_video_count}개, 조회수 {self.youtube_total_views:,}회 → {self.youtube_signal}",
            f"  네이버: 게시글 {self.naver_post_count}개, 좋아요 비율 {(self.naver_like_ratio or 0)*100:.0f}% → {self.naver_signal}",
            "",
            "투자 시그널:",
        ]
        
        if self.fomo_alert:
            lines.append("  ⚠️ FOMO 경고: 과열 구간 - 신규 진입 주의")
        if self.contrarian_signal:
            lines.append("  💡 역발상 신호: 관심 소멸 + 부정적 감성 - 바닥 탐색 구간")
        
        lines.append(f"  군중 행동 점수: {self.crowd_behavior_score:.0f}/100 (높을수록 과열)")
        lines.append(f"  감성 극단: {self.sentiment_extreme}")
        lines.append(f"  스마트머니 힌트: {self.smart_money_hint}")
        
        return "\n".join(lines)


class HumanSentimentAnalyst:
    """Analyze human sentiment indicators for investment signals."""
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.human_index = get_human_index_calculator()
    
    async def analyze_for_ticker(self, ticker: str) -> Optional[SentimentSummary]:
        """Calculate all sentiment indicators for a ticker."""
        
        # Get stock info
        stock = await self.db.fetch_one(
            "SELECT * FROM stock_info WHERE ticker = ?", (ticker,)
        )
        if not stock:
            logger.warning(f"[SentimentAnalyst] Stock not found: {ticker}")
            return None
        
        stock_name = stock.get('name', ticker)
        
        # Get current human index
        current_hi = await self.db.fetch_one(
            "SELECT * FROM human_index WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        if not current_hi:
            logger.warning(f"[SentimentAnalyst] No human index data for {ticker}")
            return self._create_empty_summary(ticker, stock_name)
        
        # Get 7-day-old human index for trend
        hi_7d_ago = await self.db.fetch_one(
            "SELECT * FROM human_index WHERE ticker = ? ORDER BY date DESC LIMIT 1 OFFSET 7",
            (ticker,)
        )
        
        # Get YouTube metrics
        youtube = await self.db.fetch_one(
            "SELECT * FROM youtube_metrics WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        # Get Naver metrics  
        naver = await self.db.fetch_one(
            "SELECT * FROM naver_discussion WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        # Extract values with safe defaults
        attention = current_hi.get('attention_score') or 0
        fomo = current_hi.get('fomo_level') or 0
        sentiment = current_hi.get('crowd_sentiment') or 0
        
        # Calculate trends
        attention_7d_ago = (hi_7d_ago.get('attention_score') or attention) if hi_7d_ago else attention
        fomo_7d_ago = (hi_7d_ago.get('fomo_level') or fomo) if hi_7d_ago else fomo
        
        attention_change = self._calc_pct_change(attention, attention_7d_ago)
        fomo_change = self._calc_pct_change(fomo, fomo_7d_ago)
        
        attention_trend = self._interpret_trend(attention_change)
        fomo_trend = self._interpret_trend(fomo_change)
        
        # YouTube analysis
        yt_video_count = (youtube.get('video_count') or 0) if youtube else 0
        yt_views = (youtube.get('total_views') or 0) if youtube else 0
        yt_sentiment = youtube.get('sentiment_score') if youtube else None
        yt_signal = self._interpret_youtube_signal(yt_video_count, yt_views)
        
        # Naver analysis
        nv_post_count = (naver.get('post_count') or 0) if naver else 0
        nv_like_ratio = naver.get('like_ratio') if naver else None
        nv_sentiment = naver.get('sentiment_score') if naver else None
        nv_signal = self._interpret_naver_signal(nv_post_count, nv_like_ratio)
        
        # Investment signals
        fomo_alert = fomo >= 70
        contrarian_signal = attention < 20 and sentiment < 0
        sentiment_extreme = self._interpret_sentiment_extreme(sentiment, fomo)
        
        # Composite scores
        crowd_behavior = self._calc_crowd_behavior_score(attention, fomo, sentiment, yt_video_count, nv_post_count)
        smart_money = self._analyze_smart_money(attention, fomo, sentiment, attention_trend, fomo_trend)
        
        return SentimentSummary(
            ticker=ticker,
            stock_name=stock_name,
            calculated_at=datetime.now().isoformat(),
            attention_score=attention,
            fomo_level=fomo,
            crowd_sentiment=sentiment,
            attention_trend=attention_trend,
            attention_change_7d=attention_change,
            fomo_trend=fomo_trend,
            fomo_change_7d=fomo_change,
            youtube_video_count=yt_video_count,
            youtube_total_views=yt_views,
            youtube_sentiment=yt_sentiment,
            youtube_signal=yt_signal,
            naver_post_count=nv_post_count,
            naver_like_ratio=nv_like_ratio,
            naver_sentiment=nv_sentiment,
            naver_signal=nv_signal,
            fomo_alert=fomo_alert,
            contrarian_signal=contrarian_signal,
            sentiment_extreme=sentiment_extreme,
            crowd_behavior_score=crowd_behavior,
            smart_money_hint=smart_money,
        )
    
    def _create_empty_summary(self, ticker: str, stock_name: str) -> SentimentSummary:
        """Create empty summary when no data available."""
        return SentimentSummary(
            ticker=ticker,
            stock_name=stock_name,
            calculated_at=datetime.now().isoformat(),
            attention_score=0,
            fomo_level=0,
            crowd_sentiment=0,
            attention_trend="unknown",
            attention_change_7d=0,
            fomo_trend="unknown",
            fomo_change_7d=0,
            youtube_video_count=0,
            youtube_total_views=0,
            youtube_sentiment=None,
            youtube_signal="unknown",
            naver_post_count=0,
            naver_like_ratio=None,
            naver_sentiment=None,
            naver_signal="unknown",
            fomo_alert=False,
            contrarian_signal=False,
            sentiment_extreme="unknown",
            crowd_behavior_score=0,
            smart_money_hint="unknown",
        )
    
    def _calc_pct_change(self, current: float, past: float) -> float:
        if past == 0:
            return 0 if current == 0 else 100
        return round((current - past) / past * 100, 1)
    
    def _interpret_trend(self, pct_change: float) -> str:
        if pct_change > 20:
            return "rising_fast"
        elif pct_change > 5:
            return "rising"
        elif pct_change < -20:
            return "falling_fast"
        elif pct_change < -5:
            return "falling"
        return "stable"
    
    def _interpret_youtube_signal(self, video_count: int, views: int) -> str:
        if video_count >= 15 or views >= 100000:
            return "viral"
        elif video_count >= 8 or views >= 30000:
            return "active"
        elif video_count >= 3 or views >= 5000:
            return "normal"
        return "quiet"
    
    def _interpret_naver_signal(self, post_count: int, like_ratio: Optional[float]) -> str:
        if post_count >= 30:
            return "hot"
        elif post_count >= 15:
            return "active"
        elif post_count >= 5:
            return "normal"
        return "quiet"
    
    def _interpret_sentiment_extreme(self, sentiment: float, fomo: float) -> str:
        if sentiment > 0.5 and fomo > 60:
            return "euphoria"
        elif sentiment < -0.3 or fomo < 20:
            return "fear"
        return "neutral"
    
    def _calc_crowd_behavior_score(self, attention: float, fomo: float, sentiment: float, 
                                    yt_videos: int, nv_posts: int) -> float:
        """
        0-100 점수. 높을수록 군중이 과열 상태.
        - 높은 관심도 + 높은 FOMO + 긍정 감성 + 많은 콘텐츠 = 과열
        """
        score = 0
        
        # Attention contributes 30%
        score += min(attention * 0.3, 30)
        
        # FOMO contributes 40%
        score += min(fomo * 0.4, 40)
        
        # Sentiment contributes 20% (0 at neutral, max at extreme positive)
        sentiment_contrib = max(0, (sentiment + 1) / 2 * 20)  # -1 to 1 → 0 to 20
        score += sentiment_contrib
        
        # Content volume contributes 10%
        content_score = min((yt_videos + nv_posts) / 40 * 10, 10)
        score += content_score
        
        return round(min(score, 100), 1)
    
    def _analyze_smart_money(self, attention: float, fomo: float, sentiment: float,
                              attention_trend: str, fomo_trend: str) -> str:
        """
        스마트머니 행동 추정 (역발상).
        - 군중이 팔 때 사고, 군중이 살 때 파는 패턴 감지
        """
        # Contrarian accumulation: Low attention, low FOMO, negative sentiment
        if attention < 25 and fomo < 30 and sentiment < 0:
            return "accumulating"
        
        # Contrarian distribution: High attention, high FOMO, positive sentiment
        if attention > 70 and fomo > 60 and sentiment > 0.3:
            return "distributing"
        
        # Rising attention but falling FOMO suggests smart money buying
        if attention_trend in ["rising", "rising_fast"] and fomo_trend in ["falling", "falling_fast"]:
            return "accumulating"
        
        # Falling attention but rising FOMO suggests retail chasing
        if attention_trend in ["falling", "falling_fast"] and fomo_trend in ["rising", "rising_fast"]:
            return "distributing"
        
        return "neutral"
    
    async def get_fomo_alert_stocks(self, threshold: float = 70) -> List[Dict]:
        """Get stocks with high FOMO levels."""
        return await self.human_index.get_fomo_alert_stocks(threshold)
    
    async def get_contrarian_opportunities(self, attention_threshold: float = 20) -> List[Dict]:
        """Get stocks with low attention and negative sentiment."""
        return await self.human_index.get_bottom_signal_stocks(attention_threshold)


_analyst_instance: Optional[HumanSentimentAnalyst] = None

def get_sentiment_analyst() -> HumanSentimentAnalyst:
    global _analyst_instance
    if _analyst_instance is None:
        _analyst_instance = HumanSentimentAnalyst()
    return _analyst_instance
