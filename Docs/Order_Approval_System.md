# 주문 승인 시스템 (Order Approval System)

## 개요

실전투자에서 안전성을 위해 구현된 주문 승인 시스템입니다. 실제 주문을 실행하기 전에 텔레그램을 통해 승인을 받아야 주문이 실행됩니다.

## 주요 기능

### 🔐 **주문 승인 요청**
- 주문 실행 전 텔레그램으로 승인 요청
- 상세한 주문 정보 표시 (종목, 수량, 가격, 주문 유형)
- 총 주문 금액 계산 및 표시

### ✅ **승인/거부 처리**
- 인라인 키보드로 Yes/No 선택
- 승인 시 주문 실행
- 거부 시 주문 취소

### ⏰ **타임아웃 처리**
- 기본 5분(300초) 타임아웃
- 타임아웃 시 자동 취소
- 설정 가능한 타임아웃 시간

## 시스템 구조

### 1. 텔레그램 핸들러 확장
```python
class TelegramHandler:
    def request_order_approval(self, orders: list, callback: Callable, timeout: int = 300) -> str:
        """주문 승인 요청"""
        
    def start_webhook_listener(self, port: int = 8443):
        """웹훅 리스너 시작"""
        
    def _handle_callback_query(self, data: dict):
        """콜백 쿼리 처리"""
```

### 2. 주문 승인 정보 클래스
```python
class OrderApproval:
    def __init__(self, order_id: str, orders: list, callback: Callable, timeout: int = 300):
        self.order_id = order_id
        self.orders = orders
        self.callback = callback
        self.created_at = datetime.now()
        self.timeout = timeout
        self.approved = None  # None: 대기중, True: 승인, False: 거부
```

## 사용 방법

### 1. 기본 설정

#### config.yaml 설정
```yaml
telegram:
  enabled: true
  token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

#### 의존성 설치
```bash
pip install flask>=2.3.0
```

### 2. 주문 승인 요청

#### 전략에서 사용
```python
def _execute_orders(self):
    """주문 실행 (텔레그램 승인 시스템 포함)"""
    # 모든 주문을 하나의 리스트로 합치기
    all_orders = []
    
    # 매수/매도 주문 정보 추가
    for order in self.state["orders"]["buy"]:
        order_info = {
            "action": "BUY",
            "symbol": self.symbol,
            "quantity": order["quantity"],
            "price": order["price"],
            "order_type": order["order_type"],
            "original_order": order
        }
        all_orders.append(order_info)
    
    # 텔레그램 승인 요청
    self.telegram.request_order_approval(all_orders, self._execute_approved_orders)

def _execute_approved_orders(self, approved: bool, orders: list):
    """승인된 주문 실행"""
    if not approved:
        logger.info("❌ 주문이 거부되었습니다.")
        return
        
    # 승인된 주문들 실행
    for order_info in orders:
        # 실제 주문 실행 로직
        pass
```

### 3. 테스트

#### 테스트 스크립트 실행
```bash
python test_order_approval.py
```

## 텔레그램 메시지 예시

### 승인 요청 메시지
```
🔐 주문 승인 요청

주문 ID: order_1703123456
요청 시간: 2023-12-21 14:30:56

1. 🟢 BUY SOXL
   수량: 100주
   가격: $25.50
   유형: MARKET
   금액: $2,550.00

2. 🟢 BUY SOXL
   수량: 50주
   가격: $24.80
   유형: LIMIT
   금액: $1,240.00

💰 총 주문 금액: $3,790.00

위 주문을 실행하시겠습니까?

[✅ 승인] [❌ 거부]
```

### 승인/거부 응답
```
✅ 주문 order_1703123456: 승인됨
```

또는

```
❌ 주문 order_1703123456: 거부됨
```

## 웹훅 vs 폴링 모드

### 웹훅 모드 (권장)
- **장점**: 실시간 응답, 서버 리소스 절약
- **단점**: 공개 도메인 필요, HTTPS 설정 필요
- **사용법**: Flask 웹서버로 웹훅 처리

### 폴링 모드 (대안)
- **장점**: 설정 간단, 로컬에서도 동작
- **단점**: 지연 가능성, API 호출 증가
- **사용법**: 주기적으로 업데이트 확인

## 보안 고려사항

### 1. 텔레그램 봇 보안
- 봇 토큰 보안 유지
- 채팅 ID 제한 (특정 사용자만 접근)
- 봇 권한 최소화

### 2. 웹훅 보안
- HTTPS 필수
- 웹훅 URL 검증
- 요청 서명 확인

### 3. 주문 승인 보안
- 타임아웃 설정으로 무한 대기 방지
- 승인 정보 암호화 저장
- 승인 로그 기록

## 설정 옵션

### 타임아웃 설정
```python
# 기본 5분
telegram.request_order_approval(orders, callback, timeout=300)

# 1분으로 설정
telegram.request_order_approval(orders, callback, timeout=60)
```

### 웹훅 포트 설정
```python
# 기본 8443 포트
telegram.start_webhook_listener()

# 다른 포트 사용
telegram.start_webhook_listener(port=8080)
```

## 오류 처리

### 일반적인 오류들

#### 1. 텔레그램 연결 실패
```
❌ 텔레그램 설정이 올바르지 않습니다.
```
**해결방법**: config.yaml에서 토큰과 채팅 ID 확인

#### 2. 웹훅 설정 실패
```
⚠️ Flask가 설치되지 않아 웹훅 기능을 사용할 수 없습니다.
```
**해결방법**: `pip install flask` 실행

#### 3. 타임아웃
```
⏰ 주문 order_xxx: 승인 시간 초과로 자동 취소됨
```
**해결방법**: 타임아웃 시간 조정 또는 빠른 응답

## 모니터링 및 로깅

### 로그 메시지
```
INFO - 🔐 2건의 주문에 대한 승인 요청
INFO - 주문 승인 요청 전송됨: order_1703123456
INFO - ✅ 주문이 승인되었습니다. 실행을 시작합니다.
INFO - ❌ 주문이 거부되었습니다.
```

### 상태 모니터링
- 대기 중인 승인 요청 수
- 승인/거부 비율
- 평균 응답 시간
- 타임아웃 발생 횟수

## 향후 개선 계획

### 1. 단기 개선
- [ ] 승인 히스토리 저장
- [ ] 승인 패턴 분석
- [ ] 자동 승인 규칙 설정

### 2. 중기 개선
- [ ] 다중 사용자 승인
- [ ] 승인 권한 레벨
- [ ] 승인 알림 설정

### 3. 장기 개선
- [ ] AI 기반 승인 추천
- [ ] 승인 패턴 학습
- [ ] 실시간 승인 대시보드

## 결론

주문 승인 시스템은 실전투자에서 안전성을 크게 향상시킵니다. 텔레그램을 통한 간편한 승인 프로세스와 타임아웃 처리로 안전하면서도 효율적인 주문 실행이 가능합니다.

특히 무한매수 전략과 같은 자동화된 전략에서 실수로 인한 손실을 방지하는 데 매우 유용합니다. 