# -*- coding: utf-8 -*-
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI

from .database import Database, get_database
from .human_index import get_human_index_calculator

logger = logging.getLogger(__name__)


class AIAnalyst:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.client = None
        self._init_client()
    
    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
    
    async def generate_deep_dive_report(self, ticker: str, mode: str = "simple") -> Dict:
        stock = await self.db.fetch_one(
            "SELECT * FROM stock_info WHERE ticker = ?", (ticker,)
        )
        if not stock:
            return {"error": "Stock not found"}
        
        price_history = await self.db.fetch_all(
            "SELECT * FROM daily_price WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker,)
        )
        
        stats = await self.db.fetch_one(
            "SELECT * FROM daily_stats WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        investor = await self.db.fetch_all(
            "SELECT * FROM daily_investor WHERE ticker = ? ORDER BY date DESC LIMIT 10",
            (ticker,)
        )
        
        human_index = await self.db.fetch_one(
            "SELECT * FROM human_index WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        news = await self.db.fetch_all(
            "SELECT * FROM stock_news WHERE ticker = ? ORDER BY datetime DESC LIMIT 10",
            (ticker,)
        )
        
        disclosures = await self.db.fetch_all(
            "SELECT * FROM dart_disclosure WHERE ticker = ? ORDER BY date DESC LIMIT 5",
            (ticker,)
        )
        
        opentalk_history = await self.db.get_naver_talk_history(ticker, days=30)
        
        context = self._build_context(stock, price_history, stats, investor, human_index, news, disclosures)
        
        is_deep = (mode == "deep")
        if self.client:
            analysis = await self._generate_gpt_analysis(stock['name'], ticker, context, is_deep)
        else:
            analysis = self._generate_fallback_analysis(stock, price_history, stats, investor, human_index)
        
        return {
            "ticker": ticker,
            "name": stock['name'],
            "market": stock['market'],
            "mode": mode,
            "generated_at": datetime.now().isoformat(),
            "analysis": analysis,
            "data": {
                "price": price_history[0] if price_history else None,
                "stats": stats,
                "investor": investor[0] if investor else None,
                "human_index": human_index,
                "recent_news": news[:3],
                "disclosures": disclosures[:3],
                "opentalk_history": opentalk_history
            }
        }
    
    def _build_context(self, stock, price_history, stats, investor, human_index, news, disclosures) -> str:
        lines = [f"종목: {stock['name']} ({stock['ticker']}) - {stock['market']}"]
        
        if price_history:
            p = price_history[0]
            lines.append(f"\n[가격 정보]")
            lines.append(f"현재가: {p.get('close', 0):,}원")
            lines.append(f"등락률: {p.get('change_rate', 0):+.2f}%")
            lines.append(f"거래량: {p.get('volume', 0):,}")
            
            if len(price_history) >= 5:
                prices = [x.get('close', 0) for x in price_history[:5]]
                avg_5 = sum(prices) / len(prices)
                lines.append(f"5일 평균가: {avg_5:,.0f}원")
        
        if stats:
            lines.append(f"\n[밸류에이션]")
            lines.append(f"PER: {stats.get('per', '-')}")
            lines.append(f"PBR: {stats.get('pbr', '-')}")
            lines.append(f"EPS: {stats.get('eps', '-')}")
            lines.append(f"BPS: {stats.get('bps', '-')}")
        
        if investor:
            lines.append(f"\n[수급 동향 (최근 10일)]")
            foreign_total = sum(x.get('foreign_net', 0) for x in investor)
            inst_total = sum(x.get('inst_net', 0) for x in investor)
            lines.append(f"외국인 순매수: {foreign_total:+,}")
            lines.append(f"기관 순매수: {inst_total:+,}")
        
        if human_index:
            lines.append(f"\n[인간 지표]")
            lines.append(f"관심도: {human_index.get('attention_score', 0):.1f}/100")
            lines.append(f"FOMO 지수: {human_index.get('fomo_level', 0):.1f}/100")
            lines.append(f"군중 감성: {human_index.get('crowd_sentiment', 0):.2f}")
        
        if news:
            lines.append(f"\n[최근 뉴스]")
            for n in news[:3]:
                lines.append(f"- {n.get('title', '')[:50]}")
        
        if disclosures:
            lines.append(f"\n[주요 공시]")
            for d in disclosures[:3]:
                lines.append(f"- [{d.get('date', '')}] {d.get('title', '')[:40]}")
        
        return "\n".join(lines)
    
    async def _generate_gpt_analysis(self, name: str, ticker: str, context: str, is_deep: bool = False) -> Dict:
        model = "gpt-4o" if is_deep else "gpt-4o-mini"
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 한국 주식시장 전문 애널리스트입니다.
주어진 데이터를 바탕으로 종목을 분석하고 투자 의견을 제시하세요.

분석 항목:
1. 기술적 분석 (가격 동향, 추세)
2. 펀더멘털 분석 (밸류에이션, 실적)
3. 수급 분석 (외인/기관 동향)
4. 인간 지표 분석 (시장 관심도, FOMO 수준)
5. 종합 의견 및 투자 전략

응답은 JSON 형식으로:
{
    "technical": "기술적 분석 내용",
    "fundamental": "펀더멘털 분석 내용",
    "flow": "수급 분석 내용",
    "human_indicator": "인간 지표 분석 내용",
    "summary": "종합 의견 (2-3문장)",
    "recommendation": "BUY/HOLD/SELL",
    "target_price": 목표가(숫자),
    "risk_level": "HIGH/MEDIUM/LOW",
    "key_points": ["핵심 포인트1", "핵심 포인트2", "핵심 포인트3"]
}"""
                    },
                    {
                        "role": "user",
                        "content": f"다음 종목을 분석해주세요:\n\n{context}"
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            result["model_used"] = model
            return result
        except Exception as e:
            logger.error(f"[AIAnalyst] GPT analysis failed: {e}")
            return {"error": str(e)}
    
    def _generate_fallback_analysis(self, stock, price_history, stats, investor, human_index) -> Dict:
        technical = "데이터 부족으로 상세 분석 불가"
        recommendation = "HOLD"
        risk_level = "MEDIUM"
        key_points = []
        
        if price_history:
            p = price_history[0]
            change = p.get('change_rate', 0)
            if change > 3:
                technical = "단기 강세 흐름. 추격 매수 주의"
                key_points.append("단기 급등으로 조정 가능성")
            elif change < -3:
                technical = "단기 약세 흐름. 지지선 확인 필요"
                key_points.append("급락 후 반등 가능성 모니터링")
            else:
                technical = "보합권 등락. 방향성 탐색 중"
        
        fundamental = "밸류에이션 데이터 확인 필요"
        if stats:
            per = stats.get('per', 0)
            pbr = stats.get('pbr', 0)
            if per and 0 < per < 10:
                fundamental = f"PER {per:.1f}배로 저평가 구간"
                recommendation = "BUY"
                key_points.append("저PER 매력")
            elif per and per > 30:
                fundamental = f"PER {per:.1f}배로 고평가 구간"
                recommendation = "SELL" if not investor else "HOLD"
                key_points.append("높은 밸류에이션 부담")
        
        flow = "수급 데이터 확인 필요"
        if investor:
            foreign_net = sum(x.get('foreign_net', 0) for x in investor)
            if foreign_net > 0:
                flow = f"외국인 순매수 {foreign_net:+,} 긍정적"
                key_points.append("외국인 매수세 유입")
            else:
                flow = f"외국인 순매도 {foreign_net:,} 주의 필요"
        
        human_indicator = "인간 지표 데이터 없음"
        if human_index:
            fomo = human_index.get('fomo_level', 0)
            attention = human_index.get('attention_score', 0)
            if fomo > 70:
                human_indicator = f"FOMO 지수 {fomo:.0f}점으로 과열 경고"
                risk_level = "HIGH"
                key_points.append("과열 구간 - 신규 진입 주의")
            elif attention < 20:
                human_indicator = f"관심도 {attention:.0f}점으로 소외 구간"
                key_points.append("관심 소멸 - 역발상 기회 가능")
            else:
                human_indicator = f"관심도 {attention:.0f}점, FOMO {fomo:.0f}점 - 정상 범위"
        
        return {
            "technical": technical,
            "fundamental": fundamental,
            "flow": flow,
            "human_indicator": human_indicator,
            "summary": f"{stock['name']}은(는) 현재 {recommendation} 의견입니다. " + 
                       (key_points[0] if key_points else "추가 데이터 수집 후 재분석 권장"),
            "recommendation": recommendation,
            "target_price": None,
            "risk_level": risk_level,
            "key_points": key_points if key_points else ["추가 데이터 수집 필요"]
        }
    
    async def compare_stocks(self, tickers: List[str]) -> Dict:
        comparisons = []
        
        for ticker in tickers[:5]:
            report = await self.generate_deep_dive_report(ticker)
            if "error" not in report:
                comparisons.append({
                    "ticker": ticker,
                    "name": report.get("name"),
                    "recommendation": report.get("analysis", {}).get("recommendation"),
                    "risk_level": report.get("analysis", {}).get("risk_level"),
                    "key_points": report.get("analysis", {}).get("key_points", [])[:2]
                })
        
        return {
            "compared_at": datetime.now().isoformat(),
            "stocks": comparisons
        }

    async def get_global_sector_leaders(self, sector: str, force_refresh: bool = False) -> Dict:
        # Determine if input is a specific Ticker/Company or a Sector
        is_company_query = False
        
        # Simple heuristic: If it looks like a ticker (all uppercase, numbers) or contains specific company names
        # But for robustness, we will let GPT/Search determine context.
        # However, we can hint prompt based on input.
        
        # 1. Check DB first (unless forced)
        if not force_refresh:
            db_result = await self.db.fetch_one(
                "SELECT * FROM sector_analysis WHERE sector_name = ?",
                (sector,)
            )
            
            if db_result:
                import json
                try:
                    data = json.loads(db_result['data'])
                    return data
                except json.JSONDecodeError:
                    pass  # Fallback to AI if JSON is corrupt

        if not self.client:
            return {"error": "OpenAI client not initialized"}
        
        # 2. Perform Web Search for latest data
        search_context = ""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = []
                
                # Query 1: Global/English (General)
                # Check if it's a company name or ticker
                q_en = f"{sector} stock competitors suppliers value chain ecosystem 2025"
                results.extend(list(ddgs.text(q_en, max_results=3)))
                
                # Query 2: Korean Specific
                q_kr = f"{sector} 관련주 테마주 밸류체인 경쟁사 2025"
                results.extend(list(ddgs.text(q_kr, max_results=3)))

                # Query 3: Specific Region Niche
                q_niche = f"Top companies related to {sector} supply chain list"
                results.extend(list(ddgs.text(q_niche, max_results=2)))
                
                if results:
                    search_context = "\n".join([f"- [{r.get('title', 'No Title')}] {r.get('body', '')}" for r in results])
                    logger.info(f"[AIAnalyst] Web Search Context found: {len(results)} items")
                else:
                    logger.warning("[AIAnalyst] Web Search returned no results")
                    
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            search_context = "Web search unavailable."

        try:
            prompt = f"""
            Analyze the global market ecosystem for the input: '{sector}'.
            
            [LATEST REAL-TIME WEB SEARCH RESULTS (2024-2025)]
            {search_context}
            
            IMPORTANT INSTRUCTIONS:
            1. **Determine Input Type**: 
               - Is '{sector}' a specific COMPANY/TICKER (e.g. "Samsung Electronics", "TSLA", "005930")?
               - Or is it a SECTOR (e.g. "Semiconductor", "Shipbuilding")?
            
            2. **If COMPANY/TICKER**:
               - Identify its **Industry/Sector**.
               - Find its **Key Competitors** (Rivals).
               - Find its **Key Suppliers/Vendors** (Value Chain).
               - Find its **Key Customers** (if B2B).
               - The goal is to show the "Ecosystem" around this specific company.
            
            3. **If SECTOR**:
               - Continue with previous logic: Find Leaders & Key Vendors.

            4. **CRITICAL**: Use the MOST UP-TO-DATE company names and tickers as of 2024/2025.
            
            Identify 5-8 companies related to '{sector}' in each region:
            1. South Korea (KR)
            2. United States (US)
            3. Japan (JP)
            4. China (CN)

            For each company, provide:
            - Ticker Symbol
            - Exchange Code
            - Company Name
            - Type: 
              - If input was Sector: "Leader", "Vendor"
              - If input was Company: "Competitor", "Supplier", "Customer", "Partner"
            - Related Leader/Entity: If Supplier/Customer, who are they related to? (Usually the input company)
            - Selection Logic: Why selected? (e.g. "Main rival in memory chips", "Supplies camera modules to {sector}")

            Return the response in strict JSON format:
            {{
                "sector": "{sector}",
                "input_type": "Company" or "Sector",
                "KR": [{{ "ticker": "...", "exchange": "...", "name": "...", "type": "...", "related_to": "...", "logic": "..." }}, ...],
                "US": [{{ "ticker": "...", "exchange": "...", "name": "...", "type": "...", "related_to": "...", "logic": "..." }}, ...],
                "JP": [{{ "ticker": "...", "exchange": "...", "name": "...", "type": "...", "related_to": "...", "logic": "..." }}, ...],
                "CN": [{{ "ticker": "...", "exchange": "...", "name": "...", "type": "...", "related_to": "...", "logic": "..." }}, ...]
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a global equity research analyst specializing in sector analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            # 2. Save to DB
            await self.db.execute(
                """
                INSERT INTO sector_analysis (sector_name, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(sector_name) DO UPDATE SET
                    data = excluded.data,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (sector, json.dumps(result, ensure_ascii=False))
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[AIAnalyst] Global sector analysis failed: {e}")
            return {"error": str(e)}

    async def get_saved_sectors(self) -> List[Dict]:
        """저장된 섹터 목록 조회"""
        rows = await self.db.fetch_all(
            "SELECT sector_name, updated_at FROM sector_analysis ORDER BY updated_at DESC"
        )
        return rows

    async def update_sector_data(self, sector: str, data: Dict) -> bool:
        """섹터 데이터 수동 업데이트"""
        import json
        try:
            await self.db.execute(
                """
                UPDATE sector_analysis 
                SET data = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE sector_name = ?
                """,
                (json.dumps(data, ensure_ascii=False), sector)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update sector data: {e}")
            return False


_analyst_instance: Optional[AIAnalyst] = None

def get_ai_analyst() -> AIAnalyst:
    global _analyst_instance
    if _analyst_instance is None:
        _analyst_instance = AIAnalyst()
    return _analyst_instance
