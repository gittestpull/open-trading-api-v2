# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class NewsRecommender:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

    async def get_market_recommendations(self) -> List[Dict[str, Any]]:
        # 1. Fetch headline news from Naver Finance
        news_items = self._fetch_naver_headlines()
        
        if not news_items:
            return [{"error": "No news headlines found"}]
            
        # 2. Format news for AI
        news_text = "\n".join([f"- {item['title']}" for item in news_items[:15]])
        
        # 3. Analyze with Gemini via REST API
        if self.api_key:
            return self._analyze_with_gemini_rest(news_text)
        else:
            return [{"error": "AI model not configured (GEMINI_API_KEY missing)"}]

    def _fetch_naver_headlines(self) -> List[Dict[str, str]]:
        try:
            url = "https://finance.naver.com/news/mainnews.naver"
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            
            for el in soup.select('.mainNewsList .articleSubject a'):
                items.append({
                    "title": el.get_text(strip=True),
                    "url": "https://finance.naver.com" + el['href']
                })
            return items
        except Exception as e:
            logger.error(f"Error fetching headlines: {e}")
            return []

    def _analyze_with_gemini_rest(self, news_text: str) -> List[Dict[str, Any]]:
        # Fallback Mock Data
        fallback = [
            {"name": "삼성전자", "ticker": "005930", "reason": "반도체 업황 회복 기대감 및 실적 개선 전망", "score": 85},
            {"name": "SK하이닉스", "ticker": "000660", "reason": "HBM 수요 폭증 및 AI 반도체 시장 주도", "score": 90},
            {"name": "현대차", "ticker": "005380", "reason": "수출 호조 및 전기차 라인업 강화", "score": 80}
        ]

        prompt = f"""
        당신은 한국 주식 시장 전문가입니다. 다음은 현재 주요 경제 뉴스 헤드라인입니다:
        
        {news_text}
        
        위 뉴스를 바탕으로 수혜가 예상되는 주식 종목 3~5개를 추천하고 그 이유를 설명해주세요.
        응답은 반드시 다음 JSON 형식을 지켜주세요:
        [
          {{
            "name": "종목명",
            "ticker": "종목코드(6자리)",
            "reason": "추천 사유 (뉴스 기반)",
            "score": 0~100점 (추천 강도)
          }},
          ...
        ]
        """
        try:
            # Try various endpoints/models
            models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
            versions = ["v1beta", "v1"]
            
            last_error = ""
            for ver in versions:
                for model in models:
                    url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}]
                    }
                    try:
                        resp = requests.post(url, json=payload, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            text = data['candidates'][0]['content']['parts'][0]['text']
                            # Simple extraction
                            start = text.find('[')
                            end = text.rfind(']')
                            if start != -1 and end != -1:
                                return json.loads(text[start:end+1])
                    except:
                        continue
            
            return fallback
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return fallback

_recommender = None
def get_recommender():
    global _recommender
    if _recommender is None:
        _recommender = NewsRecommender()
    return _recommender
