# 🤖 AI 투자 리포트 2-Tier 시스템

## 개요

AI 리포트를 **Simple**과 **Deep** 두 가지 모드로 제공합니다.

## 📊 모드 비교

| 항목 | Simple 모드 | Deep 모드 |
|------|-------------|-----------|
| **AI 모델** | GPT-4o-mini | GPT-4o |
| **응답 속도** | ~3초 | ~10초 |
| **비용** | 저렴 (약 1/10) | 고가 |
| **분석 깊이** | 요약 수준 | 상세 분석 |
| **가격 데이터** | 5일 평균 | 5일/20일 평균, 변동성 |
| **수급 분석** | 10일 합계 | 10일 합계 + 최근 5일 비교 |
| **뉴스** | 3개 제목 | 5개 제목 + 요약 |
| **공시** | 3개 제목 (40자) | 5개 제목 (80자) + 유형/영향도 |
| **Key Points** | 3개 | 5개 이상 |
| **분석 길이** | 1-2문장 | 3-5문장 |

---

## 🚀 사용법

### 1. API 호출

#### Simple 모드 (기본)
```bash
curl "http://localhost:8001/api/ai/deepdive/005930"
# 또는
curl "http://localhost:8001/api/ai/deepdive/005930?mode=simple"
```

#### Deep 모드
```bash
curl "http://localhost:8001/api/ai/deepdive/005930?mode=deep"
```

### 2. Python 코드
```python
from src.api.ai_analyst import AIAnalyst
import asyncio

async def get_report():
    analyst = AIAnalyst()
    
    # Simple 모드
    simple_report = await analyst.generate_deep_dive_report('005930', mode='simple')
    
    # Deep 모드
    deep_report = await analyst.generate_deep_dive_report('005930', mode='deep')
    
    return simple_report, deep_report

asyncio.run(get_report())
```

---

## 📋 응답 예시

### Simple 모드 응답
```json
{
  "ticker": "005930",
  "name": "삼성전자",
  "market": "KOSPI",
  "mode": "simple",
  "generated_at": "2026-01-15T11:30:00",
  "analysis": {
    "technical": "단기 보합권. 5일 평균 대비 약세",
    "fundamental": "PER 12.3배로 적정 수준",
    "flow": "외국인 순매수 유지. 긍정적",
    "human_indicator": "관심도 75점으로 정상 범위",
    "summary": "단기 조정 후 재상승 가능. 수급 양호",
    "recommendation": "HOLD",
    "target_price": 150000,
    "risk_level": "MEDIUM",
    "key_points": [
      "외국인 순매수 유지",
      "적정 밸류에이션",
      "단기 조정 중"
    ],
    "model_used": "gpt-4o-mini"
  }
}
```

### Deep 모드 응답
```json
{
  "ticker": "005930",
  "name": "삼성전자",
  "market": "KOSPI",
  "mode": "deep",
  "generated_at": "2026-01-15T11:30:00",
  "analysis": {
    "technical": "현재가는 20일 이동평균(139,200원) 위에서 지지받고 있으며, 최근 20일 변동성은 15.3%로 양호한 수준입니다. 5일 평균 대비 약 2% 상승하여 단기 반등 신호가 나타나고 있습니다.",
    "fundamental": "PER 12.3배, PBR 1.5배로 글로벌 반도체 기업 대비 저평가 구간입니다. EPS 11,580원 기준 목표주가는 150,000원 수준으로 추정됩니다.",
    "flow": "최근 10일간 외국인은 123만주 순매수했으며, 특히 최근 5일간 78만주를 집중 매수하여 매수세가 강화되고 있습니다. 기관도 98만주 순매수하며 동조 매수 중입니다.",
    "human_indicator": "관심도 75.3점, FOMO 지수 45.2점으로 정상 범위에 있습니다. YouTube 조회수와 네이버 토론방 활동이 안정적으로 유지되고 있어 과열이나 소외 구간은 아닙니다.",
    "summary": "기술적/펀더멘털/수급 모두 양호한 상태입니다. 단기 조정 후 재상승 가능성이 높으며, 외국인 매수세가 지속되고 있어 중기 상승 전망을 유지합니다.",
    "recommendation": "BUY",
    "target_price": 155000,
    "risk_level": "MEDIUM",
    "key_points": [
      "20일 이동평균 지지 확인",
      "외국인 최근 5일 집중 매수",
      "글로벌 대비 저평가 구간",
      "변동성 15% 이내로 안정적",
      "AI 반도체 수혜 기대감"
    ],
    "model_used": "gpt-4o"
  }
}
```

---

## 💰 비용 비교

### OpenAI API 가격 (2026년 1월 기준)
| 모델 | Input (1M tokens) | Output (1M tokens) |
|------|-------------------|-------------------|
| GPT-4o | $2.50 | $10.00 |
| GPT-4o-mini | $0.15 | $0.60 |

### 예상 비용 (리포트 1회 생성)
- **Simple 모드**: ~$0.002 (약 3원)
- **Deep 모드**: ~$0.015 (약 20원)

→ **Deep 모드는 Simple 대비 약 7배 비용**

---

## 🎯 추천 사용 시나리오

### Simple 모드
- ✅ 대량 종목 스크리닝 (100개 이상)
- ✅ 빠른 의견 확인
- ✅ 일일 모니터링
- ✅ 비용 절감 필요 시

### Deep 모드
- ✅ 중요 종목 심층 분석
- ✅ 매매 결정 전 최종 검토
- ✅ 투자 리포트 작성
- ✅ 뉴스/공시 상세 분석 필요 시

---

## 🔧 설정

### 환경변수
```bash
# .env 파일
OPENAI_API_KEY=sk-...
```

### 모델 변경
`src/api/ai_analyst.py`에서 모델 변경 가능:
```python
# Line 138
model = "gpt-4o" if is_deep_mode else "gpt-4o-mini"

# 또는 다른 모델 사용
model = "gpt-4-turbo" if is_deep_mode else "gpt-3.5-turbo"
```

---

## 📈 성능 최적화

### 캐싱 (추후 구현 예정)
```python
# 동일 종목 24시간 내 재요청 시 캐시 사용
# Redis 또는 메모리 캐시
```

### 배치 처리
```python
# 여러 종목 동시 분석
stocks = ['005930', '000660', '035420']
reports = await analyst.batch_analyze(stocks, mode='simple')
```

---

## 🐛 문제 해결

### OpenAI API 키 없음
```
analysis: {"error": "..."}
```
→ `.env` 파일에 `OPENAI_API_KEY` 설정

### 느린 응답 속도
- Deep 모드는 10-15초 소요 정상
- Simple 모드 사용 권장

### 비용 폭탄 방지
- 프로덕션에서는 **Simple 모드 기본값** 사용
- Deep 모드는 명시적 요청 시만 허용
- Rate limiting 구현 권장

---

## 📝 향후 개선 계획

1. ✅ **2-Tier 시스템 구현** (완료)
2. ⏳ 캐싱 시스템
3. ⏳ 배치 분석 API
4. ⏳ 스트리밍 응답 (SSE)
5. ⏳ 커스텀 프롬프트 지원
6. ⏳ 분석 히스토리 저장

---

**만든 날짜**: 2026-01-15  
**버전**: 1.0.0
