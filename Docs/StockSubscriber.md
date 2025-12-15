# StockSubscriber 기술 명세서

## 1. 개요

`StockSubscriber`는 실시간 주식 시세를 모니터링하고 가격 변동을 추적하는 핵심 모듈입니다. 한국투자증권 API를 활용하여 국내외 주식의 가격 정보를 주기적으로 조회하고, 이벤트 버스를 통해 다른 모듈에 가격 업데이트를 전파합니다.

### 1.1 주요 기능
- 📈 실시간 주식 시세 모니터링 (폴링 방식)
- 🌍 국내(KR) 및 해외(US) 주식 지원
- 📊 종목별 가격 로깅 및 히스토리 관리
- 🕐 시장 시간 인식 및 장외 시간 자동 처리
- 🔄 이벤트 버스를 통한 실시간 데이터 전파
- 🔍 종목코드/회사명 자동 검색 및 변환

## 2. 현재 구현 방식: 폴링(Polling)

### 2.1 폴링 방식 개요
현재 `StockSubscriber`는 **폴링(Polling) 방식**을 사용하여 가격 정보를 조회합니다.

```python
def _price_monitoring_loop(self):
    """가격 모니터링 루프"""
    logger.info(f"💡 가격 모니터링 루프 시작 (간격: {self.monitoring_interval}초)")
    
    while self.is_running and not self._stop_event.is_set():
        # 구독된 심볼들의 가격 조회
        for symbol, info in list(self.subscribed_symbols.items()):
            self._update_symbol_price(symbol, info, current_time)
        
        # 설정된 간격만큼 대기 (기본: 60초)
        if not self._stop_event.wait(self.monitoring_interval):
            continue
```

### 2.2 API 호출 방식
- **해외 주식**: `self.client.get_oversea_stock_price(symbol)`
- **국내 주식**: `self.client.get_domestic_stock_price(symbol)`
- **기본 간격**: 60초 (설정 가능)
- **장시간 처리**: 자동으로 API 호출 스킵

### 2.3 폴링 방식의 장단점

#### 장점 ✅
- **구현 단순성**: REST API 호출만으로 간단히 구현
- **안정성**: 연결 끊김 등의 문제가 적음
- **디버깅 용이**: 로그 추적이 명확
- **리소스 관리**: 메모리 사용량 예측 가능

#### 단점 ❌
- **실시간성 부족**: 최대 60초 지연 발생
- **API 호출량 증가**: 정기적인 REST API 호출
- **서버 부하**: 불필요한 조회 요청 발생
- **데이터 누락**: 간격 사이의 변화 감지 불가

## 3. 한국투자증권 WebSocket API (실시간 Subscribe 방식)

### 3.1 WebSocket 방식 개요
한국투자증권은 실시간 데이터 수신을 위한 **WebSocket API**를 제공합니다.

```python
# WebSocket 연결 예시 (한국투자증권 공식 샘플)
async def connect():
    url = 'ws://ops.koreainvestment.com:21000'  # 실전투자계좌
    # url = 'ws://ops.koreainvestment.com:31000'  # 모의투자계좌
    
    async with websockets.connect(url, ping_interval=None) as websocket:
        # 실시간 체결 구독
        subscribe(ws, KIS_WSReq.CONTRACT, app_key, stock_code)
        # 실시간 호가 구독  
        subscribe(ws, KIS_WSReq.BID_USA, app_key, stock_code)
```

### 3.2 WebSocket 구독 타입
- **실시간 체결**: 거래 체결 시마다 즉시 데이터 수신
- **실시간 호가**: 호가 변동 시마다 즉시 데이터 수신
- **계좌 체결통보**: 본인 계좌 체결 발생 시 즉시 알림
- **동시 구독 제한**: 최대 40개 종목까지 가능

### 3.3 WebSocket 방식의 장단점

#### 장점 ✅
- **실시간성**: 밀리초 단위 즉시 응답
- **효율성**: 변화가 있을 때만 데이터 수신
- **완전성**: 모든 가격 변화 감지 가능
- **서버 부하 감소**: 지속적인 연결로 요청 횟수 최소화

#### 단점 ❌
- **구현 복잡성**: 재연결, 에러 처리 등 복잡
- **연결 관리**: 네트워크 불안정 시 재연결 로직 필요
- **메모리 사용**: 지속적인 연결 유지
- **종목 수 제한**: 최대 40개 종목만 동시 구독 가능

## 4. 두 방식의 상세 비교

| 구분 | 폴링 (현재) | WebSocket |
|------|-------------|-----------|
| **실시간성** | 60초 간격 지연 | 즉시 (< 1초) |
| **API 호출량** | 많음 (종목수 × 1440회/일) | 적음 (연결 시에만) |
| **구현 복잡도** | ★☆☆☆☆ (매우 간단) | ★★★★☆ (복잡) |
| **안정성** | ★★★★★ (매우 안정) | ★★★☆☆ (재연결 필요) |
| **서버 부하** | ★★☆☆☆ (높음) | ★★★★★ (낮음) |
| **데이터 정확성** | ★★★☆☆ (샘플링) | ★★★★★ (완전) |
| **종목 수 제한** | 무제한 | 40개까지 |
| **디버깅** | ★★★★★ (쉬움) | ★★☆☆☆ (어려움) |
| **적합한 전략** | 중장기 전략 | 단타/스칼핑 |

## 5. StockSubscriber 사용 방법

### 5.1 기본 사용법

```python
from src.trading.stock_subscriber import StockSubscriber
from src.utils.event_bus import EventBus

# 이벤트 버스 생성
event_bus = EventBus()

# StockSubscriber 인스턴스 생성
subscriber = StockSubscriber(
    kis_client=kis_client,
    event_bus=event_bus,
    monitoring_interval=60  # 60초 간격
)

# 종목 구독 (다양한 형태로 가능)
subscriber.subscribe("SOXL", "us")           # 해외 주식 티커
subscriber.subscribe("005930", "kr")         # 국내 주식 종목코드
subscriber.subscribe("삼성전자", "kr")        # 국내 주식 회사명
subscriber.subscribe("네이버", "kr")          # 국내 주식 회사명

# 모니터링 시작
subscriber.start()

# 실행 중인 상태에서 추가 구독
subscriber.subscribe("AAPL", "us")

# 특정 종목 구독 해제
subscriber.unsubscribe("AAPL")

# 모니터링 중지
subscriber.stop()
```

### 5.2 이벤트 버스 연동

```python
def on_price_update(event_data):
    """가격 업데이트 이벤트 핸들러"""
    symbol = event_data["symbol"]
    price = event_data["price"]
    change_pct = event_data["change_pct"]
    
    print(f"{symbol}: ${price:.2f} ({change_pct:+.2f}%)")

# 이벤트 구독
event_bus.subscribe("price_update", on_price_update)
```

### 5.3 시장 상태 확인

```python
# 현재 시장 상태 확인
us_status = subscriber.get_market_status_info("us")
kr_status = subscriber.get_market_status_info("kr")

print(f"미국 시장: {'OPEN' if us_status['is_open'] else 'CLOSED'}")
print(f"한국 시장: {'OPEN' if kr_status['is_open'] else 'CLOSED'}")

# 향후 공휴일 확인
holidays = subscriber.get_upcoming_holidays(7, "us")
for holiday in holidays:
    print(f"{holiday['date']}: {holiday['name']}")
```

## 6. 로깅 및 모니터링

### 6.1 가격 로깅 시스템
- **폴더**: `price_logging/` (자동 생성)
- **파일명 형식**: `{종목명}_{시작시간}.log`
- **로그 형식**: `시간 | 가격 | 변화량 | 변화율 | 상태`

```
2024-01-15 09:30:00 | INFO | $150.25 | +2.15 | +1.45% | 상승
2024-01-15 09:31:00 | INFO | $149.80 | -0.45 | -0.30% | 하락
```

### 6.2 종목별 로거
각 구독 종목마다 개별 로그 파일이 생성되어 상세한 가격 히스토리를 기록합니다.

```python
# 안전한 파일명 생성 (특수문자 처리)
safe_name = self._make_safe_filename(display_name)
log_filename = f"{safe_name}_{start_time_str}.log"
```

## 7. 종목 검색 및 마스터 데이터

### 7.1 종목 마스터 데이터
- **KOSPI/KOSDAQ 마스터**: 자동 다운로드 및 캐싱
- **캐시 위치**: `stock_master_cache/` 폴더
- **업데이트**: 캐시 폴더 삭제 후 재실행

### 7.2 종목 검색 기능

```python
# 다양한 방식으로 종목 검색 가능
code, name = subscriber.search_stock("005930")      # 종목코드
code, name = subscriber.search_stock("삼성전자")     # 회사명
code, name = subscriber.search_stock("samsung")     # 영문명 (일부)

print(f"종목코드: {code}, 회사명: {name}")
# 결과: 종목코드: 005930, 회사명: 삼성전자
```

## 8. 무한매수 전략에서의 권장사항

### 8.1 전략 특성에 따른 선택

#### 폴링 방식 권장 상황 ✅
- **중장기 DCA 전략**: 분 단위 모니터링으로 충분
- **안정성 우선**: 시스템 안정성이 중요한 경우
- **다수 종목 모니터링**: 40개 이상 종목 추적 필요
- **개발 리소스 한정**: 빠른 개발 및 유지보수

#### WebSocket 방식 권장 상황 ✅
- **실시간 반응**: 초 단위 빠른 대응 필요
- **정확한 타이밍**: 정확한 진입/청산점 포착
- **소수 종목 집중**: 40개 이하 핵심 종목만 추적
- **고도화된 전략**: 복잡한 실시간 로직 구현

### 8.2 SOXL 무한매수 전략 적용

현재 SOXL 중심의 무한매수 전략에서는:

```python
# 현재 구현 (폴링) - 권장
subscriber = StockSubscriber(monitoring_interval=60)  # 1분 간격
subscriber.subscribe("SOXL", "us")

# 장점:
# - 1분 간격으로 충분한 실시간성
# - 안정적인 시스템 운영
# - 단순하고 명확한 로직
```

## 9. 성능 및 리소스 사용량

### 9.1 폴링 방식 리소스 사용
- **CPU**: 낮음 (주기적 REST 호출)
- **메모리**: 낮음 (상태 정보만 저장)
- **네트워크**: 중간 (정기적 API 호출)
- **API 할당량**: 높음 사용 (1종목 = 1440회/일)

### 9.2 WebSocket 방식 리소스 사용 (예상)
- **CPU**: 중간 (실시간 데이터 처리)
- **메모리**: 중간 (연결 및 버퍼 유지)
- **네트워크**: 낮음 (지속적 연결)
- **API 할당량**: 낮음 사용 (연결 시에만)

## 10. 향후 개선 방향

### 10.1 하이브리드 방식 구현
```python
class HybridStockSubscriber(StockSubscriber):
    """폴링과 WebSocket을 함께 사용하는 하이브리드 방식"""
    
    def __init__(self, primary_symbols=None, **kwargs):
        super().__init__(**kwargs)
        self.primary_symbols = primary_symbols or []  # WebSocket 대상
        self.secondary_symbols = []  # 폴링 대상
    
    def subscribe(self, symbol, market, priority="normal"):
        if priority == "high" and len(self.primary_symbols) < 40:
            # 핵심 종목은 WebSocket으로 처리
            self._subscribe_websocket(symbol, market)
        else:
            # 일반 종목은 폴링으로 처리
            super().subscribe(symbol, market)
```

### 10.2 성능 최적화
- **배치 처리**: 여러 종목 동시 조회
- **캐싱 강화**: 중복 조회 방지
- **비동기 처리**: async/await 패턴 도입
- **동적 간격 조정**: 변동성에 따른 조회 간격 자동 조정

## 11. 결론

현재의 **폴링 방식**은 SOXL 무한매수 전략에 매우 적합한 구현입니다:

- ✅ **중장기 전략**에 최적화
- ✅ **안정적이고 예측 가능**한 동작
- ✅ **유지보수가 간단**
- ✅ **충분한 실시간성** (1분 간격)

향후 더 정교한 실시간 전략이 필요하다면 WebSocket 방식으로 전환을 고려할 수 있으나, 현재 단계에서는 폴링 방식으로 충분히 효과적인 자동매매 시스템을 구축할 수 있습니다. 