# 마켓 캘린더 사용법

## 개요

마켓 캘린더 모듈은 미국 증시의 개장시간, 공휴일, 조기 마감일 등을 동적으로 확인할 수 있는 기능을 제공합니다. 야후 파이낸스와 같은 외부 API 없이도 Python의 `holidays` 라이브러리를 활용하여 정확한 시장 정보를 확인할 수 있습니다.

## 주요 기능

### 1. 실시간 시장 상태 확인
- 현재 시장이 열려있는지 확인
- 공휴일 및 조기 마감일 감지
- 서머타임/윈터타임 자동 처리

### 2. 동적 거래시간 관리
- **미국**: NYSE/NASDAQ 정규장, 프리마켓, 애프터마켓 시간
- **미국**: 조기 마감일 자동 적용 (1:00 PM EST)
- **한국**: KRX 정규장, 동시호가, 시간외거래 시간

### 3. 공휴일 정보
- **미국**: NYSE 공식 공휴일 자동 업데이트 + 조기 마감일
- **한국**: Python holidays 라이브러리 활용 (설날, 추석 등 음력 공휴일 포함)
- 향후 공휴일 조회 (미국/한국 구분)

## 설치 및 설정

### 필수 패키지 설치

```bash
pip install holidays pytz requests
```

또는 requirements.txt 사용:

```bash
pip install -r requirements.txt
```

### 의존성

- `holidays>=0.39`: NYSE 공휴일 정보
- `pytz>=2023.3`: 시간대 처리
- `requests>=2.31.0`: 외부 API 호출 (선택사항)

## 사용 방법

### 기본 사용법

```python
from src.trading.market_calendar import market_calendar

# 🇺🇸 미국 시장 상태 확인
us_is_open = market_calendar.is_market_open("us")
print(f"미국 시장 상태: {'열림' if us_is_open else '닫힘'}")

# 🇰🇷 한국 시장 상태 확인
kr_is_open = market_calendar.is_market_open("kr")
print(f"한국 시장 상태: {'열림' if kr_is_open else '닫힘'}")

# 상세한 시장 정보 조회
us_status = market_calendar.get_market_status("us")
kr_status = market_calendar.get_market_status("kr")

print(f"🇺🇸 미국: 현재시간 {us_status['current_time']}, 공휴일 {us_status['is_holiday']}")
print(f"🇰🇷 한국: 현재시간 {kr_status['current_time']}, 공휴일 {kr_status['is_holiday']}")
```

### 공휴일 확인

```python
from datetime import date

# 특정 날짜가 공휴일인지 확인
is_holiday = market_calendar.is_market_holiday(date(2025, 1, 1))
print(f"2025-01-01 공휴일 여부: {is_holiday}")

# 향후 30일 내 공휴일 조회
upcoming = market_calendar.get_upcoming_holidays(30)
for holiday in upcoming:
    print(f"{holiday['date']}: {holiday['name']}")
```

### 거래시간 정보

```python
# 미국 시장 거래시간 조회
us_hours = market_calendar.get_market_hours("us")
print("미국 시장 거래시간 (EST):")
for session, times in us_hours.items():
    print(f"  {session}: {times['start']} - {times['end']}")

# 조기 마감일의 경우 자동으로 13:00 종료시간 적용
early_close_date = date(2025, 7, 3)  # 독립기념일 전날
hours = market_calendar.get_market_hours("us", early_close_date)
print(f"조기 마감일 종료시간: {hours['regular']['end']}")
```

### StockSubscriber와 연동

```python
from src.trading.stock_subscriber import StockSubscriber

# StockSubscriber는 자동으로 마켓 캘린더 사용
subscriber = StockSubscriber(kis_client)

# 시작 시 자동으로 시장 상태 정보 출력
subscriber.start()

# 수동으로 시장 상태 정보 확인
subscriber.log_market_status()

# 개별 시장 상태 조회
us_status = subscriber.get_market_status_info("us")
kr_status = subscriber.get_market_status_info("kr")
```

## 2025년 주요 공휴일

### NYSE/NASDAQ 공휴일

| 날짜 | 공휴일명 | 비고 |
|------|----------|------|
| 2025-01-01 | New Year's Day | 신정 |
| 2025-01-20 | Martin Luther King Jr. Day | 마틴 루터 킹 데이 |
| 2025-02-17 | Presidents' Day | 대통령의 날 |
| 2025-04-18 | Good Friday | 성금요일 |
| 2025-05-26 | Memorial Day | 현충일 |
| 2025-06-19 | Juneteenth | 준틴스 |
| 2025-07-04 | Independence Day | 독립기념일 |
| 2025-09-01 | Labor Day | 노동절 |
| 2025-11-27 | Thanksgiving Day | 추수감사절 |
| 2025-12-25 | Christmas Day | 크리스마스 |

### 조기 마감일 (1:00 PM EST)

| 날짜 | 사유 |
|------|------|
| 2025-07-03 | 독립기념일 전날 |
| 2025-11-28 | 추수감사절 다음날 |
| 2025-12-24 | 크리스마스 이브 |

## 외부 API 연동 (선택사항)

### Trading Calendar API

무료로 제공되는 Trading Calendar API를 통해 실시간 시장 정보를 확인할 수 있습니다:

```python
# Trading Calendar API 호출 (선택사항)
api_data = market_calendar.get_trading_calendar_api("XNYS")
if api_data:
    print("API 연결 성공:", api_data)
else:
    print("API 응답 없음 - 로컬 데이터 사용")
```

### Docker를 통한 로컬 API 서버

```bash
# Trading Calendar API 로컬 실행
docker pull apptasticsoftware/trading-calendar:latest
docker run -d --name trading-calendar -p 8000:80 apptasticsoftware/trading-calendar

# API 테스트
curl "http://127.0.0.1:8000/api/v1/markets?mic=XNYS"
```

## 테스트 방법

### 기본 테스트 실행

```bash
# 마켓 캘린더 기능 테스트
python test_market_calendar.py
```

## 장점

### 1. 자동화된 시장 관리
- 하드코딩된 시간 대신 동적 시장 정보 사용
- 공휴일과 조기 마감일 자동 처리
- 서머타임 변경 자동 적용

### 2. 정확성
- NYSE 공식 공휴일 데이터 사용
- Python `holidays` 라이브러리의 정확한 날짜 계산
- 실시간 시간대 처리

### 3. 확장성
- 다양한 거래소 지원 가능
- 외부 API 연동 지원
- 커스터마이징 가능한 거래시간

### 4. 로깅 개선
- 상세한 시장 상태 정보 제공
- 공휴일/조기 마감일 구분 표시
- 디버깅 정보 향상

## 주의사항

1. **인터넷 연결**: 외부 API 사용 시 인터넷 연결 필요
2. **시간대 설정**: 시스템 시간대 설정이 정확해야 함
3. **업데이트**: 연도별 조기 마감일 정보는 수동 업데이트 필요
4. **데이터 정확성**: 중요한 거래 결정 시 공식 소스 재확인 권장

## 문제 해결

### 자주 발생하는 문제

1. **ImportError**: `holidays` 또는 `pytz` 설치 확인
2. **시간대 오류**: 시스템 시간대 설정 확인
3. **API 연결 실패**: 인터넷 연결 및 방화벽 설정 확인

### 로그 확인

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 디버그 정보와 함께 실행
market_calendar.get_market_status("us")
```

## 관련 문서

- [한국투자증권 API 가이드](../README.md)
- [무한매수 전략 문서](./TradingStrategy.md)
- [Streamlit UI 가이드](./UI_design.md) 