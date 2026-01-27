# -*- coding: utf-8 -*-
"""
AI Analyst V2 - Enhanced analysis with pre-calculated indicators.

Design Principle: "계산은 Python이, 해석은 AI가"
- Technical indicators pre-calculated by technical_indicators.py
- Sentiment indicators pre-calculated by human_sentiment_analyst.py
- AI receives structured data, focuses on interpretation
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Literal, Optional

from openai import OpenAI

from .database import Database, get_database
from .technical_indicators import TechnicalSummary, get_technical_calculator
from .human_sentiment_analyst import SentimentSummary, get_sentiment_analyst

logger = logging.getLogger(__name__)


# Response structure types
AnalysisMode = Literal["short", "mid"]


class AIAnalystV2:
    """Enhanced AI Analyst with pre-calculated indicators."""
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.technical = get_technical_calculator()
        self.sentiment = get_sentiment_analyst()
        self.client = None
        self._init_client()
    
    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
    
    async def analyze(
        self, 
        ticker: str, 
        mode: AnalysisMode = "short",
        include_news: bool = True
    ) -> Dict:
        """
        Generate comprehensive analysis with pre-calculated indicators.
        
        Args:
            ticker: Stock ticker code
            mode: "short" for swing trading (1-5 days), "mid" for position trading (1-4 weeks)
            include_news: Whether to include recent news in analysis
        
        Returns:
            Structured analysis result
        """
        # Get stock info
        stock = await self.db.fetch_one(
            "SELECT * FROM stock_info WHERE ticker = ?", (ticker,)
        )
        if not stock:
            return {"error": "Stock not found", "ticker": ticker}
        
        # Pre-calculate all indicators
        tech_summary = await self.technical.calculate_for_ticker(ticker)
        sent_summary = await self.sentiment.analyze_for_ticker(ticker)
        
        # Get additional context
        investor = await self.db.fetch_all(
            "SELECT * FROM daily_investor WHERE ticker = ? ORDER BY date DESC LIMIT 10",
            (ticker,)
        )
        
        news = []
        if include_news:
            news = await self.db.fetch_all(
                "SELECT * FROM stock_news WHERE ticker = ? ORDER BY datetime DESC LIMIT 5",
                (ticker,)
            )
        
        disclosures = await self.db.fetch_all(
            "SELECT * FROM dart_disclosure WHERE ticker = ? ORDER BY date DESC LIMIT 3",
            (ticker,)
        )
        
        # Build context for AI
        context = self._build_enhanced_context(
            stock, tech_summary, sent_summary, investor, news, disclosures, mode
        )
        
        # Generate AI analysis
        if self.client:
            analysis = await self._generate_analysis(
                stock['name'], ticker, context, mode
            )
        else:
            analysis = self._generate_fallback_analysis(
                stock, tech_summary, sent_summary, mode
            )
        
        return {
            "ticker": ticker,
            "name": stock['name'],
            "market": stock.get('market'),
            "mode": mode,
            "generated_at": datetime.now().isoformat(),
            "analysis": analysis,
            "indicators": {
                "technical": tech_summary.to_dict() if tech_summary else None,
                "sentiment": sent_summary.to_dict() if sent_summary else None,
            },
            "raw_data": {
                "investor_flow_10d": self._summarize_investor(investor),
                "recent_news": [n.get('title') for n in news[:3]] if news else [],
                "recent_disclosures": [d.get('title') for d in disclosures] if disclosures else [],
            }
        }
    
    def _build_enhanced_context(
        self, 
        stock: Dict,
        tech: Optional[TechnicalSummary],
        sent: Optional[SentimentSummary],
        investor: List[Dict],
        news: List[Dict],
        disclosures: List[Dict],
        mode: AnalysisMode
    ) -> str:
        """Build context string for GPT prompt with pre-calculated indicators."""
        lines = [
            f"=== {stock['name']} ({stock['ticker']}) - {stock.get('market', 'KRX')} ===",
            f"분석 모드: {'단기 스윙 (1-5일)' if mode == 'short' else '중기 포지션 (1-4주)'}"
        ]
        
        # Technical Indicators (pre-calculated)
        if tech:
            lines.append("\n" + tech.to_prompt_text())
        else:
            lines.append("\n[기술적 지표] 데이터 부족")
        
        # Sentiment Indicators (pre-calculated)
        if sent:
            lines.append("\n" + sent.to_prompt_text())
        else:
            lines.append("\n[투자심리 지표] 데이터 부족")
        
        # Investor Flow
        if investor:
            lines.append("\n[수급 동향 (최근 10일)]:")
            foreign_net = sum(x.get('foreign_net') or 0 for x in investor)
            inst_net = sum(x.get('inst_net') or 0 for x in investor)
            individual_net = sum(x.get('individual_net') or 0 for x in investor)
            
            lines.append(f"  외국인 순매수: {foreign_net:+,}")
            lines.append(f"  기관 순매수: {inst_net:+,}")
            lines.append(f"  개인 순매수: {individual_net:+,}")
            
            # Trend description
            if foreign_net > 0 and inst_net > 0:
                lines.append("  -> 외국인/기관 동반 매수 (긍정적)")
            elif foreign_net < 0 and inst_net < 0:
                lines.append("  -> 외국인/기관 동반 매도 (부정적)")
            elif foreign_net > 0 and inst_net < 0:
                lines.append("  -> 외국인 매수 vs 기관 매도 (혼조)")
        
        # News
        if news:
            lines.append("\n[최근 뉴스]:")
            for n in news[:3]:
                title = n.get('title', '')[:60]
                lines.append(f"  - {title}")
        
        # Disclosures
        if disclosures:
            lines.append("\n[주요 공시]:")
            for d in disclosures:
                title = d.get('title', '')[:50]
                date = d.get('date', '')
                lines.append(f"  - [{date}] {title}")
        
        return "\n".join(lines)
    
    async def _generate_analysis(
        self, 
        name: str, 
        ticker: str, 
        context: str, 
        mode: AnalysisMode
    ) -> Dict:
        """Generate AI analysis with structured output."""
        
        if mode == "short":
            system_prompt = self._get_short_term_prompt()
        else:
            system_prompt = self._get_mid_term_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 종목을 분석해주세요:\n\n{context}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["model_used"] = "gpt-4o"
            return result
            
        except Exception as e:
            logger.error(f"[AIAnalystV2] GPT analysis failed: {e}")
            return {"error": str(e)}
    
    def _get_short_term_prompt(self) -> str:
        """System prompt for short-term swing trading analysis."""
        return '''당신은 한국 주식시장 단기 트레이딩 전문가입니다.
주어진 기술적 지표와 투자심리 데이터를 바탕으로 1-5일 단기 스윙 트레이딩 관점에서 분석하세요.

분석 중점:
1. 기술적 지표 해석 (RSI, MACD, 볼린저 밴드 위치)
2. 단기 추세 판단 (이격도, 거래량)
3. 진입/청산 타이밍 판단
4. 투자심리 과열/공포 여부 (FOMO 지수, 군중 행동)

응답은 반드시 아래 JSON 형식으로:
{
    "summary": {
        "recommendation": "BUY" | "HOLD" | "SELL" | "WAIT",
        "confidence_score": 1-100,
        "time_horizon": "1-3일" | "3-5일",
        "one_liner": "핵심 의견 한 줄"
    },
    "strategy": {
        "entry_price_zone": {"min": 숫자, "max": 숫자},
        "target_price": 숫자,
        "stop_loss": 숫자,
        "position_size": "소형" | "표준" | "공격적"
    },
    "analysis_logic": {
        "bullish_factors": ["상승 요인1", "상승 요인2"],
        "bearish_factors": ["하락 요인1", "하락 요인2"],
        "key_risk": "가장 주의할 리스크",
        "sentiment_warning": "투자심리 관련 경고 (있을 경우)"
    },
    "technical_summary": "기술적 지표 종합 해석 (2-3문장)",
    "action_plan": "구체적 매매 계획 (언제, 어떻게)"
}'''
    
    def _get_mid_term_prompt(self) -> str:
        """System prompt for mid-term position trading analysis."""
        return '''당신은 한국 주식시장 중기 투자 전문가입니다.
주어진 기술적 지표와 투자심리 데이터를 바탕으로 1-4주 중기 포지션 관점에서 분석하세요.

분석 중점:
1. 중기 추세 판단 (MA60, MA120 기준)
2. 수급 동향 분석 (외국인/기관 흐름)
3. 펀더멘털 고려 (있는 경우)
4. 역발상 투자 기회 (스마트머니 힌트 활용)

응답은 반드시 아래 JSON 형식으로:
{
    "summary": {
        "recommendation": "BUY" | "ACCUMULATE" | "HOLD" | "REDUCE" | "SELL",
        "confidence_score": 1-100,
        "time_horizon": "1-2주" | "2-4주",
        "one_liner": "핵심 의견 한 줄"
    },
    "strategy": {
        "entry_price_zone": {"min": 숫자, "max": 숫자},
        "target_price": 숫자,
        "stop_loss": 숫자,
        "accumulation_strategy": "분할 매수 전략 설명"
    },
    "analysis_logic": {
        "bullish_factors": ["상승 요인1", "상승 요인2"],
        "bearish_factors": ["하락 요인1", "하락 요인2"],
        "key_catalyst": "주가 움직임 촉발 요인",
        "contrarian_view": "역발상 관점 (있을 경우)"
    },
    "flow_analysis": "외국인/기관 수급 해석 (2-3문장)",
    "sentiment_analysis": "투자심리 해석 및 군중 행동 분석",
    "action_plan": "구체적 투자 계획"
}'''
    
    def _generate_fallback_analysis(
        self, 
        stock: Dict,
        tech: Optional[TechnicalSummary],
        sent: Optional[SentimentSummary],
        mode: AnalysisMode
    ) -> Dict:
        """Generate rule-based analysis when OpenAI is unavailable."""
        
        recommendation = "HOLD"
        confidence = 50
        bullish = []
        bearish = []
        
        if tech:
            # RSI analysis
            if tech.rsi_signal == "oversold":
                bullish.append("RSI 과매도 구간")
                recommendation = "BUY"
                confidence += 15
            elif tech.rsi_signal == "overbought":
                bearish.append("RSI 과매수 구간")
                recommendation = "SELL" if mode == "short" else "REDUCE"
                confidence += 10
            
            # MACD analysis
            if tech.macd_trend == "bullish_cross":
                bullish.append("MACD 골든크로스")
                confidence += 15
            elif tech.macd_trend == "bearish_cross":
                bearish.append("MACD 데드크로스")
                confidence += 10
            
            # Bollinger analysis
            if tech.bb_position == "below_lower":
                bullish.append("볼린저 하단 이탈 - 반등 기대")
            elif tech.bb_position == "above_upper":
                bearish.append("볼린저 상단 이탈 - 조정 가능")
            
            # Trend
            if tech.short_trend in ["strong_up", "up"]:
                bullish.append(f"단기 추세 {tech.short_trend}")
            elif tech.short_trend in ["strong_down", "down"]:
                bearish.append(f"단기 추세 {tech.short_trend}")
        
        if sent:
            # FOMO alert
            if sent.fomo_alert:
                bearish.append("FOMO 과열 경고")
                if recommendation == "BUY":
                    recommendation = "WAIT"
            
            # Contrarian signal
            if sent.contrarian_signal:
                bullish.append("역발상 매수 신호")
                confidence += 10
            
            # Smart money
            if sent.smart_money_hint == "accumulating":
                bullish.append("스마트머니 매집 추정")
            elif sent.smart_money_hint == "distributing":
                bearish.append("스마트머니 분산 추정")
        
        confidence = min(confidence, 85)  # Cap at 85 for rule-based
        
        return {
            "summary": {
                "recommendation": recommendation,
                "confidence_score": confidence,
                "time_horizon": "1-3일" if mode == "short" else "1-2주",
                "one_liner": f"{stock['name']} - {recommendation} (규칙 기반 분석)"
            },
            "strategy": {
                "entry_price_zone": {
                    "min": tech.support_level if tech else None,
                    "max": tech.current_price if tech else None
                },
                "target_price": tech.resistance_level if tech else None,
                "stop_loss": tech.support_level * 0.97 if tech and tech.support_level else None,
            },
            "analysis_logic": {
                "bullish_factors": bullish if bullish else ["특이사항 없음"],
                "bearish_factors": bearish if bearish else ["특이사항 없음"],
                "key_risk": bearish[0] if bearish else "추가 데이터 필요",
            },
            "technical_summary": tech.to_prompt_text() if tech else "기술적 데이터 부족",
            "note": "OpenAI API 미사용 - 규칙 기반 분석"
        }
    
    def _summarize_investor(self, investor: List[Dict]) -> Dict:
        """Summarize investor flow data."""
        if not investor:
            return {}
        
        return {
            "foreign_net_10d": sum(x.get('foreign_net') or 0 for x in investor),
            "inst_net_10d": sum(x.get('inst_net') or 0 for x in investor),
            "individual_net_10d": sum(x.get('individual_net') or 0 for x in investor),
        }


_analyst_v2_instance: Optional[AIAnalystV2] = None

def get_ai_analyst_v2() -> AIAnalystV2:
    global _analyst_v2_instance
    if _analyst_v2_instance is None:
        _analyst_v2_instance = AIAnalystV2()
    return _analyst_v2_instance
