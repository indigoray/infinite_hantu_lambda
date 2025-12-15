# 라오어의 무한매수 전략 자동화 

## 프로젝트 소개
이 프로젝트는 라오어의 무한매수 방법론에 따라서, 미국 SOXL(반도체 레버리지 3x ETF) 등의 종목을 대상으로 하는 자동 매매 시스템입니다. 
DCA(Dollar Cost Averaging) 전략을 기반으로 하여 주기적으로 매수하고, 설정된 수익률에 도달하면 매도하는 전략을 자동화합니다.
추가적으로 박성현의 외환 7스플릿 전략, LOU의 VR 전략 (Value Rebalancing) 등을 추가하여 다양한 전략을 지원합니다.

### 무한매수 전략 특징
- 사이클 개념: 전량 매도 시 사이클 종료, 잔량 0일 때 새 사이클 시작
- 진행률 기반 동적 파라메터 조정
- Star가격 매수/매도 전략
- LOC(Limit on Close) 및 After hours 주문 활용

## 작동환경
- Linux (WSL) 데몬
- 개인 노트북 linux환경 또는 AWS EC2 환경
- Docker 환경

## 한국투자증권 API의 장점

- Websocket방식의 Restful API를 지원한다. 
- API로 미국주식 거래를 지원한다. 
- 수수료 0.05%로 저렴한 편 (cf. 키움은 0.07%)
- 자동 달러 RP 매수/매도

## 주요 기능
- Streamlit을 이용한 웹 인터페이스
- daemon으로 실행, 매일 저녁 6시 자동 전략 실행 (매수/매도 예약)
- 실시간 모니터링을 통한 변화전략 실행
- 한국투자증권 API를 통한 실시간 시세 조회 
- 계좌 모니터링 (잔고 및 예수금 상황, RP매수 잔고 등)
- 상황에 따른 실시간 매도 전략 실행
- 텔레그램을 통한 알림 및 설정 기능

### 구현된 주요 기능
1. **무한매수 전략 엔진** (InfiniteBuyingStrategy)
   - 자동 사이클 관리
   - 동적 파라메터 계산
   - 시간별 자동 주문 실행

2. **Trading Engine**
   - 다중 전략 동시 실행
   - 스케줄 기반 전략 실행
   - 이벤트 기반 상태 관리

3. **실시간 모니터링 대시보드**
   - 포지션 정보
   - 전략 진행 상황
   - 주문 현황
   - 시스템 로그

4. **한국투자증권 API 최적화**
   - 모의투자/실전투자 자동 TR ID 변환
   - Rate Limit 자동 처리 및 재시도
   - 안전한 데이터 변환 처리
   - API 에러 복구 메커니즘

## 기술 스택
- Python 3.8+
- 한국투자증권 웹소켓/REST API
- PyYAML (설정 관리)
- python-telegram-bot (알림 기능)
- streamlit (웹 인터페이스)
- RxPy (이벤트 시스템)
- schedule (스케줄링)
- pandas, numpy (데이터 처리)

## 설치 방법
1. 저장소 클론
```bash
git clone [repository-url]
cd infinite-hantu
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

4. 설정 파일 수정
- `config/config.yaml` 파일에서 필요한 설정을 변경하세요
- 한국투자증권 API 키와 시크릿을 설정하세요
- 텔레그램 봇 토큰 설정 (선택사항)

## 설정 파일 구성

### config/config.yaml 예시
```yaml
api:
  app_key: "YOUR_APP_KEY"
  app_secret: "YOUR_APP_SECRET"
  account_number: "YOUR_ACCOUNT_NUMBER"
  base_url: "https://openapi.koreainvestment.com:9443"
  is_virtual: true  # 모의투자: true, 실전투자: false

trading:
  infinite_buying_strategy:
    symbol: "SOXL"  # 거래 종목 (SOXL, TQQQ 등)
    total_investment: 1000000  # 전략 할당 총투자금 (원)
    division_count: 40  # 분할수 (총 투자 건수)
    max_profit_rate: 12  # 목표수익률(최대익절비율) %
    min_profit_rate: 8  # 최소익절비율 %
    star_adjustment_rate: 0  # Star 보정비율 % (default 0)

telegram:
  enabled: true  # 텔레그램 알림 사용 여부
  token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

### 중요한 설정 옵션

#### 모의투자 vs 실전투자
- **모의투자**: `is_virtual: true`
  - 모의투자용 TR ID 자동 사용 (VTTS, VTTT 등)
  - 안전한 테스트 환경
- **실전투자**: `is_virtual: false`  
  - 실전투자용 TR ID 사용 (TTTS, TTTT 등)
  - 실제 자금 거래

## 사용 방법
1. 설정 파일 확인
   - `config/config.yaml` 파일에서 API 키, 계좌 정보, 전략 설정 등을 확인하세요

2. Streamlit UI 실행
```bash
streamlit run main.py
```

3. 웹 브라우저에서 `http://localhost:8501` 접속

4. UI에서 전략 시작/중지 및 모니터링
   - 사이드바에서 전략 제어
   - 메인 화면에서 실시간 상태 확인

## 무한매수 전략 상세

### 전략 파라메터
- **분할수**: 40회 (기본값)
- **최대익절률**: 12%
- **최소익절률**: 8%
- **Star보정비율**: 0% (조정 가능)

### 주문 실행 시간
- **프리마켓 5분전** (한국시간 22:25): 주문 준비
- **프리마켓 1분후** (한국시간 22:31): 주문 실행
- **애프터마켓 종료** (한국시간 09:00): 사이클 체크

### 주문 로직
1. **T ≤ 20일 때**
   - Star가격 매수 (1일매수금의 절반)
   - 평단가 매수
   - 추가 매수 (현재가 30% 하락까지)

2. **T > 20일 때**
   - Star가격에 1일매수금 전액 매수
   - 추가 매수 (현재가 30% 하락까지)

3. **매도 전략**
   - Star매도: 보유수량의 1/4 (LOC)
   - 익절매도: 나머지 전량 (After hours)

## 🔔 주문 체결 확인 시스템

### **실시간 체결 모니터링**
- **REST API 조회**: 주문내역, 미체결 주문 실시간 확인
- **체결 즉시 알림**: 텔레그램으로 체결 완료 즉시 통보
- **자동 미체결 관리**: 30분 초과 미체결 주문 자동 취소
- **WebSocket 지원**: 실시간 체결통보 수신 (선택사항)

### **주요 체결 확인 기능**
- `get_oversea_orders()`: 당일 주문내역 조회
- `get_pending_orders()`: 미체결 주문 확인
- `cancel_order()`: 주문 취소
- `_check_order_execution()`: 상세 체결 상태 분석

## 프로젝트 구조
```
src/
├── api/
│   └── kis_client.py         # 한국투자증권 API 클라이언트
├── strategy/
│   └── infinite_buying.py    # 무한매수 전략 구현
├── utils/
│   ├── logger.py            # 로깅 유틸리티
│   └── telegram.py          # 텔레그램 알림
├── config.py                # 설정 관리
├── event_bus.py             # RxPy 이벤트 시스템
└── trading_engine.py        # 거래 엔진
```

## 주의사항
- 이 프로그램은 투자 위험이 있는 자동매매 시스템입니다
- 레버리지 ETF의 위험성을 충분히 이해하고 사용하시기 바랍니다
- **반드시 모의투자로 충분한 테스트를 진행하시기 바랍니다**
- API 키를 GitHub에 업로드하지 마세요
- 실전투자 전환 시 `is_virtual: false`로 변경 후 신중하게 테스트

## 문제 해결

### API 로그인 실패
- API 키와 시크릿 확인
- 계좌번호 형식 확인 (8자리+2자리)
- 한국투자증권 개발자센터에서 서비스 신청 상태 확인

### 주문 실패
- 미국 장 시간 확인
- 주문 가능 금액 확인
- API 호출 제한 확인
- 모의투자/실전투자 설정 확인

## 개발 현황
- [x] 무한매수 전략 구현
- [x] KIS API 연동
- [x] Streamlit UI
- [x] Trading Engine
- [x] Event Bus 시스템
- [x] 텔레그램 알림
- [x] 상태 저장/복원
- [x] API 에러 자동 처리
- [x] 모의투자/실전투자 자동 구분
- [x] Rate Limit 자동 관리
- [ ] 백테스팅 기능
- [ ] 다중 종목 동시 지원
- [ ] 웹소켓 실시간 시세
- [ ] 성과 분석 대시보드

## 작성자
- Sangsu Lee

## 참고 자료
- [한국투자증권 Open Trading API](https://github.com/koreainvestment/open-trading-api)
- [SOXL ETF 정보](https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs)
- [무한매수 전략 소개](https://blog.naver.com/louisiana1919)
- [Streamlit Documentation](https://docs.streamlit.io)
- [RxPy Documentation](https://rxpy.readthedocs.io)