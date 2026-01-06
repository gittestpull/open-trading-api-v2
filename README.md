**[당사에서 제공하는 샘플코드에 대한 유의사항]**

- 샘플 코드는 한국투자증권 Open API(KIS Developers)를 연동하는 예시입니다. 고객님의 개발 부담을 줄이고자 참고용으로 제공되고 있습니다.
- 샘플 코드는 별도의 공지 없이 지속적으로 업데이트될 수 있습니다.
- 샘플 코드를 활용하여 제작한 고객님의 프로그램으로 인한 손해에 대해서는 당사에서 책임지지 않습니다.

# KIS Open API 샘플 코드 저장소 (LLM 지원)

## 1. 제작 의도 및 대상

### 🎯 제작 의도

이 저장소는 **ChatGPT, Claude 등 LLM(Large Language Model)** 기반 자동화 환경과 Python 개발자 모두가
**한국투자증권(Korea Investment & Securities) Open API를 쉽게 이해하고 활용**할 수 있도록 구성된 샘플 코드 모음입니다.

- `examples_llm/`: LLM이 단일 API 기능을 쉽게 탐색하고 호출할 수 있도록 구성된 기능 단위 샘플 코드
- `examples_user/`: 사용자가 실제 투자 및 자동매매 구현에 활용할 수 있도록 상품별로 통합된 API 호출 예제 코드

> AI와 사람이 모두 활용하기 쉬운 구조를 지향합니다.

[한국투자증권 Open API 포털 바로가기](https://apiportal.koreainvestment.com/)

### 👤 대상 사용자

- 한국투자증권 Open API를 처음 사용하는 Python 개발자
- 기존 Open API 사용자 중 코드 개선 및 구조 학습이 필요한 사용자
- LLM 기반 코드 에이전트를 활용해 종목 검색, 시세 분석, 자동매매 등을 구현하고자 하는 사용자

## 2. 폴더 구조 및 주요 파일 설명

### 2.1. 폴더 구조

```
# 프로젝트 구조
.
├── README.md                    # 프로젝트 설명서
├── kis_devlp.yaml               # API 설정 파일 (개인정보 입력 필요)
├── pyproject.toml               # (uv)프로젝트 의존성 관리
├── uv.lock                      # (uv)의존성 락 파일
│
├── monitor_scalp_universal.py   # [Core] 범용 스캘핑 봇 (국내/해외 통합)
├── monitor_scalp_llm.py         # [Core] AI 지능형 스캘퍼 (GPT-5.2 기반)
├── visualize_investor_trends.py # [Analysis] 심층 차트 제너레이터 (이미지 생성)
├── analyze_chart_data.py        # [Analysis] 데이터 해석기 (리포트 출력)
│
├── custom_scripts/
│   └── leading_stock_finder.py  # [Tool] 실시간 주도주 검색기
│
├── stock_code_lookup.py         # [Module] 종목명 <-> 종목코드 변환 모듈
├── examples_llm/                # [Sample] LLM용 기능 단위 샘플 코드
├── examples_user/               # [Sample] 사용자용 통합 예제 코드
├── legacy/                      # 구 샘플코드 보관
├── scalp_data/                   # 봇 거래 상태 데이터 (JSON)
└── stock_info/                  # 종목정보파일 참고 데이터
```

### 2.2. 지원되는 주요 API 카테고리

- 아래 카테고리 및 폴더 구조는 examples_llm/, examples_user/ 폴더 모두 동일하게 적용됩니다.

| 카테고리 | 설명 | 폴더명 |
| --- | --- | --- |
| 국내주식 | 국내 주식 시세, 주문, 잔고 등 | `domestic_stock` |
| 국내채권 | 국내 채권 시세, 주문 등 | `domestic_bond` |
| 국내선물옵션 | 국내 파생상품 관련 | `domestic_futureoption` |
| 해외주식 | 해외 주식 시세, 주문 등 | `overseas_stock` |
| 해외선물옵션 | 해외 파생상품 관련 | `overseas_futureoption` |
| ELW | ELW 시세 API | `elw` |
| ETF/ETN | ETF, ETN 시세 API | `etfetn` |

### 2.3. 주요 파일 설명

### `examples_llm/` - llm용 기능 단위 샘플 코드

**API별 개별 폴더 구조**: 단일 API 기능을 독립 폴더로 분리하여, LLM이 관련 코드를 쉽게 탐색할 수 있도록 구성
- **한줄 호출 파일**: `[함수명].py` – 단일 기능을 호출하는 최소 단위 코드 (예: `inquire_price.py`)
- **테스트 파일**: `chk_[함수명].py` – 호출 결과를 검증하는 테스트 실행 코드 (예: `chk_inquire_price.py`)

### `examples_user/` - 사용자용 통합 예제 코드

**카테고리별 개별 폴더 구조**: 카테고리(상품)별로 모든 기능을 통합하여, 사용자가 쉽게 샘플 코드를 탐색하고 실행할 수 있도록 구성
- **통합 함수 파일**: `[카테고리]_functions.py` - 해당 카테고리의 모든 API 기능이 통합된 함수 모음
- **실행 예제 파일**: `[카테고리]_examples.py` - 실제 사용 예제를 기반으로 한 실행 코드
- **웹소켓 통합 함수 파일 및 실행 예제 파일**: `[카테고리]_functions_ws.py`, `[카테고리]_examples_ws.py`

### `kis_auth.py` - 인증 및 공통 기능

- 접근토큰 발급 및 관리
- API 호출 공통 함수
- 실전투자/모의투자 환경 전환 지원
- 웹소켓 연결 설정 기능 제공

## 3. 사전 환경설정 안내

### 3.1. Python 환경 요구사항

- **Python 3.9 이상** 필요
- **uv** **패키지 매니저 사용** 권장 (빠르고 간편한 의존성 관리)

### 3.2. uv 설치 방법

- 간편 설정을 위해 uv를 권장합니다

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 설치 확인
uv --version
# uv 0.x.x ... -> 설치 완료
```

### 3.3. 프로젝트 클론 및 환경 설정

```bash
# 저장소 클론
git clone https://github.com/koreainvestment/open-trading-api
cd open-trading-api/kis_github

# uv를 사용한 의존성 설치 - 한줄로 끝
uv sync
```

### 3.4. KIS Open API 신청 및 설정

🍀 [서비스 신청 안내 바로가기](https://apiportal.koreainvestment.com/about-howto)
1. 한국투자증권 **계좌 개설 및 ID 연결**
2. 한국투자증권 홈페이지 or 앱에서 **Open API 서비스 신청**
3. **앱키(App Key)**, **앱시크릿(App Secret)** 발급
4. **모의투자** 및 **실전투자** 앱키 각각 준비

### 3.5. kis_devlp.yaml 설정

- 본인의 계정 설정을 위해 `kis_devlp.yaml` 파일을 열어 다음과 같이 수정합니다.
1. **프로젝트 루트에 위치한** `kis_devlp.yaml` 파일 열기
2. **앱키와 앱시크릿** 정보 입력
3. **HTS ID** 정보 입력
4. **계좌번호** 정보 입력 (앞 8자리와 뒤 2자리 구분)
5. **저장** 후 닫기

```yaml
# 실전투자
my_app: "여기에 실전투자 앱키 입력"
my_sec: "여기에 실전투자 앱시크릿 입력"

# 모의투자
paper_app: "여기에 모의투자 앱키 입력"
paper_sec: "여기에 모의투자 앱시크릿 입력"

# HTS ID(KIS Developers 고객 ID) - 체결통보, 나의 조건 목록 확인 등에 사용됩니다.
my_htsid: "사용자 HTS ID"

# 계좌번호 앞 8자리
my_acct_stock: "증권계좌 8자리"
my_acct_future: "선물옵션계좌 8자리"
my_paper_stock: "모의투자 증권계좌 8자리"
my_paper_future: "모의투자 선물옵션계좌 8자리"

# 계좌번호 뒤 2자리
my_prod: "01" # 종합계좌
# my_prod: "03" # 국내선물옵션 계좌
# my_prod: "08" # 해외선물옵션 계좌
# my_prod: "22" # 연금저축 계좌
# my_prod: "29" # 퇴직연금 계좌

# User-Agent(기본값 사용 권장, 변경 불필요)
my_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### 3.6. kis_auth.py 설정 경로 수정

- `kis_auth.py`의 config_root 경로를 본인 환경에 맞게 수정해줍니다. 발급된 토큰 파일이 저장될 경로로, 제3자가 찾기 어렵도록 설정하는것을 권장합니다.

```yaml
# kis_auth.py 39번째 줄
# windows - C:\Users\사용자이름\KIS\config
# Linux/macOS - /home/사용자이름/KIS/config
# config_root = os.path.join(os.path.expanduser("~"), "KIS", "config")
config_root = os.path.join(os.path.expanduser("~"), "폴더 경로", "config")
```
### 3.7. 실행파일 내 인증 설정 검토

- 실행하려는 파일에서 인증 관련 설정을 검토 혹은 변경해줍니다. 국내주식 기능 전체를 이용하시려면, `domestic_stock/domestic_stock_examples.py` 파일을 확인해주세요. 
ka.auth() 함수의 svr, product 매개변수를 아래와 같이 수정하면 실전환경(prod)에서 위탁계좌(-01)로 매매 테스트가 가능합니다.

```python
import kis_auth as ka

# 실전투자 인증
ka.auth(svr="prod", product="01") # 모의투자: svr="vps"
```

## 4. 샘플 코드 실행

### 4.1. 샘플 코드 실행

- **examples_user 기준**

```bash
# 국내주식 샘플 코드 실행 (examples_user/domestic_stock/)
python domestic_stock_examples.py # REST 방식
python domestic_stock_examples_ws.py  # Websocket 방식 
```

domestic_stock_examples.py에는 여러 함수가 포함되어 있으므로, 사용하려는 함수만 남기고 나머지는 주석 처리한 후, 입력값을 수정하여 호출해 주세요.

- **examples_llm 기준**

```bash
# 국내주식 > 주식현재가 시세 샘플 코드 실행 (examples_llm/domestic_stock/inquire_price/)
python chk_inquire_price.py
```

examples_llm 은 각 기능별로 개별 실행 파일(chk_*.py)이 분리되어 있어, 특정 기능만 테스트하고자 할 때 유용합니다.

### 4.2. 예제 코드 샘플 (examples_user)

```python
# REST API 호출 예제 - domestic_stock_examples.py
import sys
import logging
import pandas as pd
sys.path.extend(['..', '.'])

import kis_auth as ka
from domestic_stock_functions import *

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 인증
ka.auth()
trenv = ka.getTREnv()

# 삼성전자 현재가 시세 조회
result = inquire_price(env_dv="real", fid_cond_mrkt_div_code="J", fid_input_iscd="005930")
print(result)
```

```python
# 웹소켓 호출 예제 - domestic_stock_examples_ws.py
import sys
import logging
import pandas as pd
sys.path.extend(['..', '.'])

import kis_auth as ka
from domestic_stock_functions_ws import *

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 인증
ka.auth()
ka.auth_ws()
trenv = ka.getTREnv()

# 웹소켓 선언
kws = ka.KISWebSocket(api_url="/tryitout")

# 삼성전자, sk하이닉스 실시간 호가 구독
kws.subscribe(request=asking_price_krx, data=["005930", "000660"])
```

## 6. 고급 자동매매 봇 (Advanced Trading Bots)

이 저장소는 단순 API 예제를 넘어, 실제 매매에 활용 가능한 고성능 자동매매 스크립트를 포함하고 있습니다.

### 6.1. `monitor_scalp_universal.py` (범용 스캘핑 봇)
국내(KOSPI/KOSDAQ) 및 해외(NASDAQ/NYSE) 주식을 단일 로직으로 매매할 수 있는 스캘퍼입니다.

#### 전략 개요
- **매수 조건 (Triple-Threat Entry)**: 아래 3가지 조건 중 하나라도 충족 시 매수 진입
  - **RSI 과매도**: 1분봉 RSI(9)가 30 이하
  - **볼린저 밴드 하단**: 현재가 또는 분봉 저가가 BB(20, 2) 하단 터치
  - **수동 지정가**: `--buy_price` 옵션으로 지정한 가격까지 하락
- **매도 조건**:
  - 목표 수익률 달성 (기본 0.5%)
  - 볼린저 밴드 상단 터치 + 수익률 0.5% 이상
- **자금 관리**: 물타기(Pyramiding) 전략 (1:2:4:8 비중 배분, 최대 4단계)
- **안전 기능**: 
  - **수량 불일치 감지**: 로컬 상태와 실제 계좌 수량 불일치 시 로그에 경고 출력.
  - **API 호출 최적화**: 잔고(매매 시) 및 수급 데이터(10분 주기) 캐싱으로 호출 제한 방지.
  - **투자자 수급 연동**: 국내 주식에 대해 외인/기관 순매수 동향 실시간(10분 단위) 표시.
- **NXT 연장 거래 지원**: 정규장(KRX) 외 시간에도 NXT(넥스트레이드)를 통해 자동 거래.
  - **NXT 프리마켓**: 08:00 ~ 08:50 (정규장 전)
  - **NXT 애프터마켓**: 15:40 ~ 18:00 (정규장 후)
  - 로그에 `[KRX]`, `[NXT_PRE]`, `[NXT_POST]` 세션 태그가 표시됩니다.
- **시간대별 우선 매수 조건**: 시간대에 따라 다른 하락 기준을 적용하여 최우선 매수 트리거.
  - **08:00~10:00**: 전일 종가 대비 -2% 하락 시 매수 (개장 초반 변동성 활용)
  - **10:00 이후**: 당일 최고가 대비 -2% 하락 시 매수 (추세 되돌림 포착)
- **호가창 필터 (`--orderbook`)**: 매수잔량 > 매도잔량일 때만 진입 (수급 확인)
- **모멘텀 모드 (`--momentum`)**: 전일 고가 돌파 시 매수하는 브레이크아웃 전략
  - 역추세(하락 시 매수) 대신 순추세(상승 시 매수) 전략 사용
  - 기존 조건(RSI, BB 등)과 OR 조건으로 함께 사용 가능

#### CLI 옵션
| 옵션 | 설명 | 기본값 | 예시 |
|------|------|--------|------|
| `--ticker` | 종목코드 또는 종목명 (필수) | - | `014940`, `TSLA`, `"삼성중공업"` |
| `--budget` | 총 매매 예산 (원/달러) | 1,000,000 | `100000`, `5000` |
| `--target` | 목표 수익률 (소수) | 0.005 (0.5%) | `0.01` (1%), `0.02` (2%) |
| `--buy_price` | 수동 매수 진입가 | 0 (비활성) | `2450` |
| `--orderbook` | 호가창 필터 (매수>매도 시만 진입) | False | 플래그만 추가 |
| `--momentum` | 모멘텀 모드 (전일 고가 돌파 시 매수) | False | 플래그만 추가 |
| `--live` | 실전 매매 모드 활성화 | False (모의) | 플래그만 추가 |

#### 사용 예시
```bash
# 기본 사용 (종목코드 사용, 모의매매)
uv run python monitor_scalp_universal.py --ticker 014940 --budget 1000000

# 종목명으로 검색 (국내주식)
uv run python monitor_scalp_universal.py --ticker "삼성중공업" --budget 500000

# 목표 수익률 1%로 설정
uv run python monitor_scalp_universal.py --ticker 014940 --budget 100000 --target 0.01

# 특정 가격(2,400원)까지 하락 시 매수 진입
uv run python monitor_scalp_universal.py --ticker 014940 --budget 300000 --buy_price 2400

# 호가창 필터 활성화 (매수잔량 > 매도잔량 시만 진입)
uv run python monitor_scalp_universal.py --ticker 014940 --budget 200000 --orderbook --live

# 모멘텀 모드 (전일 고가 돌파 시 매수, 달리는 말에 올라타기)
uv run python monitor_scalp_universal.py --ticker 014940 --budget 200000 --momentum --live

# 모멘텀 + 호가창 필터 조합 (상승세 + 수급 우위 확인)
uv run python monitor_scalp_universal.py --ticker 014940 --budget 200000 --momentum --orderbook --live
# 해외주식 (테슬라) - 5,000달러 예산
uv run python monitor_scalp_universal.py --ticker TSLA --budget 5000 --target 0.005

# 실전 매매 모드
uv run python monitor_scalp_universal.py --ticker "삼성중공업" --budget 100000 --target 0.01 --live
```

#### 상태 관리
봇은 `scalp_data/` 폴더에 거래 상태를 JSON 파일로 저장하여, 봇 재시작 시에도 이전 포지션을 유지합니다.
- **상태 파일 경로**: `scalp_data/state_{종목코드}.json`
- **저장 정보**: 현재 상태(SEARCHING/HOLDING), 평균 매수가, 총 보유 수량, 물타기 단계, 매수 이력

```bash
# 상태 파일 확인
cat scalp_data/state_014940.json

# 상태 초기화 (수동으로 정리 시)
rm scalp_data/state_014940.json
```

#### 로그 출력 예시
```
2025-01-05 09:15:30 [INFO] Starting Universal Scalper | Ticker: 014940 (Domestic) | Budget: 1,000,000 | Target: 0.50%
2025-01-05 09:15:31 [INFO] Price: 2,480.00 | Bounce: 0.12% | RSI: 35.2 | BB: [2,420.50, 2,580.30] | Supply: F:+125.3k, I:-45.8k | 주문가능: 5,000,000 | 총자산: 12,500,000 | 보유없음 | Target: 0.50% | Next Buy: B1 @ BB:2420.50 / RSI30:2415.20 | Step: 0 | State: SEARCHING
```

#### 알림 기능
- **macOS**: 매매 체결 시 시스템 사운드 (Ping.aiff) 재생
- **Windows/Linux**: 사운드 미지원 (afplay 명령어가 macOS 전용)

### 6.2. `monitor_scalp_llm.py` (AI 지능형 스캘퍼)
Universal 봇의 기술적 지표에 **OpenAI GPT-5.2**의 판단력을 결합한 최신형 봇입니다.
- **AI 감정 분석**: 실시간 관련 뉴스를 수집하여 GPT-5.2가 -5 ~ +5 점수로 매매 적합성 판별.
- **거시 지표 반영 (Macro Context)**: 국내 지수(KOSPI/KOSDAQ) 및 해외 지수(SPY/QQQ)와 실시간 수급(외인/기관 순매수)을 GPT가 종합 분석.
- **비상 탈출**: 기술적 지표가 좋아도 뉴스가 심각하게 부정적(점수 -3 이하)일 경우 즉시 전량 매도.
- **알림 기능**: 매매 체결 시 'Submarine' 사운드 알림.

### 6.3. 실행 방법 (권장)
`uv`를 사용하는 경우, **`uv run`** 명령어를 통해 모든 의존성 패키지가 포함된 격리된 환경에서 안전하게 실행할 수 있습니다. 또한, 티커 코드 대신 **"삼성중공업"**과 같은 종목명을 직접 입력할 수 있습니다.

```bash
# 범용 봇 실행 (종목명 "삼성중공업" 사용, 10만원 예산, 목표 수익 1% 설정, 실전매매)
uv run python monitor_scalp_universal.py --ticker "삼성중공업" --budget 100000 --target 0.01 --live

# AI 봇 실행 (테슬라, 5000달러 예산, 목표 수익 0.5% 설정, 실전매매)
uv run python monitor_scalp_llm.py --ticker TSLA --budget 5000 --target 0.005 --live
```

## 7. 데이터 분석 및 시각화 (Analysis & Visualization)

트레이딩 의사결정을 돕기 위한 강력한 데이터 시각화 및 분석 도구를 제공합니다.

### 7.1. `visualize_investor_trends.py` (심층 차트 제너레이터)
단순한 가격 차트를 넘어, 투자에 필요한 모든 핵심 데이터를 하나의 이미지로 결합합니다.
- **포함 데이터**: 주가, 이동평균선, 외국인/기관/개인 수급, 신용융자 잔고, 대차잔고(공매도 추이), 밸류에이션(PBR/PER), 주요 뉴스/공시(수주 등), 애널리스트 목표가, 배당 정보.
- **자동 종목 검색**: 종목코드 대신 종목명(예: "삼성전자")만 입력해도 자동으로 코드를 찾아 분석합니다.
- **한글 지원**: macOS, Windows, Linux 환경에 맞는 한글 폰트를 자동으로 설정합니다.

### 7.2. `analyze_chart_data.py` (데이터 해석기)
시각화된 데이터를 수치적으로 분석하여 리포트 형태로 출력합니다.
- **밸류에이션 진단**: 현재 PBR/PER 수치와 과거 최고점 대비 위치를 분석하여 저평가 여부를 판별합니다.
- **상관관계 분석**: 주가와 수급, 주가와 밸류에이션 간의 상관계수를 계산하여 주가 상승의 동인을 파악합니다.
- **피크 분석**: 주가 고점과 신용/대차 잔고 고점 사이의 시차(Lag)를 분석하여 변곡점을 추적합니다.

### 7.3. `custom_scripts/leading_stock_finder.py` (주도주 검색기)
당일 시장을 주도하고 있는 상위 20개 종목을 실시간으로 발굴합니다.
- **데이터 통합**: 가격 급등락, 거래대금 상위, 체결강도(VolPower) 데이터를 종합 분석.
- **Leader Score**: 거래대금 가중치와 상승률, 체결강도를 결합한 독자적인 점수 체계 적용.
- **실시간 순위**: 현재 시간 기준 가장 강력한 수급이 쏠리는 종목을 표 형태로 출력.

### 7.4. 실행 방법
```bash
# 삼성전자 종합 분석 차트 생성 (자동으로 폰트 및 코드 검색)
python visualize_investor_trends.py "삼성전자"

# 오리엔탈정공(014940) 데이터 심층 분석 리포트 출력
python analyze_chart_data.py 014940

# 주도주 검색기 실행
uv run python custom_scripts/leading_stock_finder.py
```

---

---

## 5. 문제 해결 가이드

### 토큰 오류 시

```python
import kis_auth as ka

# 토큰 재발급 - 1분당 1회 발급됩니다.
ka.auth(svr="prod")  # 또는 "vps"
```

### 설정 파일 오류 시

- `kis_devlp.yaml` 파일의 앱키, 앱시크릿이 올바른지 확인
- 계좌번호 형식이 맞는지 확인 (앞 8자리 + 뒤 2자리)
- 실시간 시세(WebSocket) 이용 중 ‘No close frame received’ 오류가 발생하는 경우, `kis_devlp.yaml`에 입력하신 HTS ID가 정확한지 확인

### 의존성 오류 시

```bash
# 의존성 재설치
uv sync --reinstall
```

---

# 📧 문의사항

- [💬 한국투자증권 Open API 챗봇](https://chatgpt.com/g/g-68b920ee7afc8191858d3dc05d429571-hangugtujajeunggweon-open-api-seobiseu-gpts)에 언제든 궁금한 점을 물어보세요.
