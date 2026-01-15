# YouTube 종목 뉴스 수집기

YouTube API를 활용하여 한국/해외 주식 종목 관련 뉴스 및 분석 영상을 자동으로 수집하는 도구입니다.

## 주요 기능

- 🔍 **종목명 검색**: "삼성전자", "테슬라" 등 종목명으로 간편하게 검색
- 📊 **상세 통계**: 조회수, 좋아요, 댓글 수 등 메타데이터 수집
- 💾 **다양한 저장 형식**: JSON, CSV 형식으로 저장 (Excel 호환)
- 🎯 **키워드 필터링**: "전망", "분석" 등 추가 키워드로 정확도 향상
- ⏰ **날짜 범위 설정**: 최근 N일 내 영상만 선택적 수집
- 📈 **정렬 옵션**: 관련도, 최신순, 조회수, 평점 등 다양한 정렬 기준

## 설치 및 설정

### 1. YouTube API 키 확인

`.env` 파일에 이미 설정되어 있습니다:
```
YOUTUBE_API_KEY=AIzaSyA7nHrRqbIPczeWIHSvJ-4eqsgJvM0ZaA0
```

### 2. 의존성 설치

이미 `google-api-python-client`가 설치되어 있으므로 추가 작업 불필요합니다.

## 사용 방법

### CLI 기본 사용

```bash
# 기본 사용 (최근 7일, 50개 영상)
uv run python youtube_news_collector.py "삼성전자"

# 최대 개수 지정
uv run python youtube_news_collector.py "테슬라" --max-results 30

# 검색 기간 지정 (최근 3일)
uv run python youtube_news_collector.py "SK하이닉스" --days 3

# 추가 키워드로 정확도 향상
uv run python youtube_news_collector.py "NAVER" --keywords "전망" "분석"

# 조회수 순 정렬
uv run python youtube_news_collector.py "카카오" --order viewCount

# 최신순 정렬
uv run python youtube_news_collector.py "Apple" --order date

# 파일 저장 안함 (화면 출력만)
uv run python youtube_news_collector.py "삼성전자" --no-save

# 상위 5개만 출력
uv run python youtube_news_collector.py "삼성전자" --top 5
```

### Python 코드에서 사용

```python
from youtube_news_collector import YouTubeNewsCollector

# 수집기 초기화
collector = YouTubeNewsCollector()

# 영상 검색
videos = collector.search_stock_news(
    ticker_name="삼성전자",
    max_results=50,
    days_back=7,
    order="relevance",
    include_keywords=["전망", "분석"]
)

# 결과 저장
collector.save_to_json("samsung_news.json")
collector.save_to_csv("samsung_news.csv")

# 상위 10개 조회
top_videos = collector.get_top_videos(top_n=10, sort_by="view_count")
print(top_videos)
```

### 여러 종목 일괄 수집

```python
from youtube_news_collector import YouTubeNewsCollector

collector = YouTubeNewsCollector()
stocks = ["삼성전자", "SK하이닉스", "NAVER", "카카오"]

for stock in stocks:
    collector.search_stock_news(
        ticker_name=stock,
        max_results=30,
        days_back=7
    )

# 모든 결과를 하나의 파일로 저장
collector.save_to_csv("all_stocks_news.csv")
```

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `ticker` | 종목명 (필수) | - |
| `--max-results` | 최대 수집 개수 | 50 |
| `--days` | 검색 기간 (일) | 7 |
| `--keywords` | 추가 검색 키워드 | None |
| `--order` | 정렬 기준 (relevance/date/viewCount/rating) | relevance |
| `--top` | 상위 N개 출력 | 10 |
| `--no-save` | 파일 저장 안함 | False |

## 수집 데이터 필드

| 필드명 | 설명 |
|--------|------|
| `ticker_name` | 종목명 |
| `video_id` | YouTube 비디오 ID |
| `title` | 영상 제목 |
| `description` | 영상 설명 (500자 제한) |
| `channel_title` | 채널명 |
| `published_at` | 게시일시 |
| `view_count` | 조회수 |
| `like_count` | 좋아요 수 |
| `comment_count` | 댓글 수 |
| `url` | YouTube URL |
| `thumbnail` | 썸네일 이미지 URL |
| `collected_at` | 수집일시 |

## 저장 파일 위치

모든 파일은 `data/` 폴더에 저장됩니다:

```
open-trading-api/
└── data/
    ├── youtube_news_20260115_114250.json
    ├── youtube_news_20260115_114250.csv
    └── ...
```

## 예제 스크립트

`example_youtube_usage.py` 파일에서 다양한 사용 예제를 확인할 수 있습니다:

```bash
uv run python example_youtube_usage.py
```

## 주의사항

1. **YouTube API 할당량**: YouTube Data API v3는 일일 할당량이 있습니다 (기본 10,000 units)
   - 검색 1회: 100 units
   - 영상 상세정보 조회: 1 unit
   - 하루 약 100회 검색 가능 (영상 50개씩)

2. **최대 결과 수**: API 제한으로 인해 1회 검색 시 최대 50개까지만 수집 가능

3. **한국어 컨텐츠**: `regionCode='KR'`, `relevanceLanguage='ko'` 설정으로 한국어 영상 우선 수집

## 트러블슈팅

### API 키 오류
```
ValueError: YouTube API key not found
```
→ `.env` 파일에 `YOUTUBE_API_KEY` 확인

### 할당량 초과
```
HttpError 403: quotaExceeded
```
→ 24시간 후 재시도 또는 Google Cloud Console에서 할당량 확인

## 활용 방안

1. **트레이딩 신호 분석**: 영상 급증/조회수 급증 시 관심도 증가로 판단
2. **감성 분석**: 제목/설명에서 긍정/부정 키워드 추출
3. **채널 신뢰도**: 특정 채널의 예측 정확도 추적
4. **이슈 조기 감지**: 갑작스런 영상 증가 패턴 포착

## 라이선스

KIS Open API 샘플 코드 저장소와 동일한 라이선스를 따릅니다.
