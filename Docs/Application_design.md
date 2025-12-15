Application 설계명세 


1. 프로젝트 구조 
```
/
├── Docs/                      # 문서 디렉토리
│   ├── Application_design.md  # 애플리케이션 설계 문서
│   ├── UI_design.md          # UI 설계 문서
│   ├── TradingStrategy.md    # 거래 전략 문서
│   └── Consulting.md         # 컨설팅 문서
│
├── src/                      # 소스 코드 디렉토리
│   ├── api/                  # API 관련 모듈
│   │   ├── __init__.py
│   │   └── kis_client.py    # 한국투자증권 API 클라이언트 [개선됨]
│   │
│   ├── strategy/            # 거래 전략 모듈
│   │   ├── __init__.py
│   │   └── infinite_buying.py # 무한매수 전략 구현 [개선됨]
│   │
│   ├── ui/                  # UI 관련 모듈
│   │   ├── __init__.py
│   │   └── app.py          # Streamlit UI 구현
│   │
│   ├── utils/              # 유틸리티 모듈
│   │   ├── __init__.py
│   │   ├── logger.py      # 로깅 유틸리티
│   │   └── telegram.py    # 텔레그램 알림 기능
│   │
│   ├── __init__.py
│   ├── config.py          # 설정 관리 모듈
│   ├── event_bus.py       # 이벤트 버스 (RxPy) [구현완료]
│   └── trading_engine.py  # 트레이딩 엔진 [구현완료]
│
├── config/                 # 설정 파일 디렉토리
│   └── config.yaml        # 애플리케이션 설정 파일 [개선됨]
│
├── states/                # 상태 파일 디렉토리 [신규 추가]
│   ├── strategy_state_SOXL.json       # 전략 상태 메인 파일
│   └── strategy_state_SOXL.backup.json # 전략 상태 백업 파일
│
├── logs/                  # 로그 파일 디렉토리
│
├── main.py               # 메인 실행 파일 [개선됨]
├── setup.py             # 패키지 설정 파일
├── requirements.txt     # 의존성 목록
├── Dockerfile          # 도커 설정 파일
├── .gitignore         # Git 제외 파일 목록 [업데이트됨]
└── README.md          # 프로젝트 설명 문서
```

2. 기본 기능 명세
   1. Account Manager
      1. 계좌 로그인 [구현완료 - kis_client.py]
      2. 계좌 상태 조회 및 표시 [구현완료 - get_oversea_balance()]
      3. 계좌 이력 조회 및 그래프 표시
   2. Strategy Manager
      1. 전략 실행 및 중단 [구현완료 - trading_engine.py]
      2. 전략 상황 조회 및 표시 [구현완료 - get_status()]
      3. 전략 파라메터 세팅 [구현완료 - infinite_buying.py]
      4. 전략 실행 로그 조회 및 표시 [부분구현 - logger.py]
      5. 기존 전략 Cycle 로그 조회 및 그래프 표시
      6. 전략 목록 조회 및 추가, 삭제 [구현완료 - trading_engine.py]
      7. 전략 파라메터 세팅 및 저장 [구현완료 - save_state(), load_state()]
   3. Market_Subscriber
      1. 활성화된 전략이 요구하는 종목들과 그 종목들에 대한 요구 주기에 따라 시세를 구독하고 전략에 제공 [부분구현 - get_oversea_stock_price()]
   

3. 제약사항
   1. 계좌는 세팅된 하나만 로그인 가능
   2. 전략은 Ticker당 하나만 실행 가능   
   3. 이 App은 한국에서 실행. 미국 및 한국 시장에서 거래.
      미국시장 거래시 타임존 변환에 주의할 것.
      ✅ 동적 타임존 처리 구현 완료 (서머타임/윈터타임 자동 대응)

4. Application Start Flow
    - streamlit run main.py 명령으로 실행
    - main.py 파일에서 Streamlit UI 초기화
    - 세션 상태 초기화 및 페이지 설정
    - 애플리케이션 초기화 (한 번만 실행)
        - config.py 파일에서 설정 파일 로드 [구현완료]
        - logger.py 파일에서 로깅 설정 [구현완료]
        - EventBus 초기화 [구현완료]
        - telegram.py 파일에서 텔레그램 설정 [구현완료]
        - kis_client.py 파일에서 한국투자증권 API 설정 [구현완료]
        - 유저 계좌에 로그인 [구현완료]
        - Trading Engine 초기화 및 시작 [구현완료]
        - 실행중인 전략 체크 및 활성화 [구현완료]
    - UI 렌더링: 계좌 잔고, 예수금, 실행 중인 전략 목록 등 표시 [구현완료]
    - Event Bus를 통한 실시간 업데이트 처리 [구현완료]
  
5. Strategy Manager, Run Strategy 플로우
    - 전략 목록 조회 [구현완료]
    - 전략 Instance 생성 - Instance 이름 부여 [구현완료]
    - 전략 파라메터 세팅 [구현완료]
    - 전략 실행 - 실행시, 자신의 실행 parameter를 저장하고 상태 변경시마다 저장 [구현완료]
    - 전략은 daemon이 재실행될 때, 이전에 저장되었던 전략이 있으면 로딩하여 재실행 [구현완료]
    - 전략은 자신의 실행주기 마다 run 메서드를 호출하여 실행 [구현완료]
    - init, run, exit, save_state, load_state 메서드를 구현한다. [구현완료]
      - init 메서드는 전략 실행시 최초 한번만 호출된다.
      - run 메서드는 지정 주기마다 호출된다.
      - exit 메서드는 전략 종료시 호출된다.
      - save_state 메서드는 전략 상태 변경시 호출된다.
      - load_state 메서드는 전략 실행시 호출된다.
    - 전략은 다음과 같은 공통 param을 갖는다.
      - 이름
      - 설명
      - 실행주기 (1초, 1분, 5분, 10분, 1시간, 장시작 n초 후 1회, 장 끝나기 n초 전 1회, etc.)
      - 대상 Ticker
      - 실행 파라메터
      - 할당 계좌
      - 할당 자금량
    - 모든 전략은 프로그램 오류나, 정전, 기타 상황에 대비해 자신의 상태를 memory에만 가지고 있어서는 안되고 항상 상태 변경시마다 파일로 저장하고, 재실행시에 이전 상태파일을 불러와 원래의 상태를 복원할 수 있어야 한다.

     - **상태 관리 보장 사항:**
       - 원자적 저장 (Atomic Save): 임시 파일을 통한 안전한 저장으로 저장 중 프로그램 종료시에도 파일 손상 방지
       - 백업 시스템: 메인 상태 파일 손상시 자동으로 백업 파일에서 복구
       - 상태 무결성 검증: 로드시 필수 키와 데이터 유효성 확인으로 손상된 파일 감지
       - 재시도 메커니즘: 저장 실패시 최대 3회까지 재시도
       - 긴급 알림: 상태 저장 실패시 텔레그램을 통한 즉시 알림
       - 모든 상태 변경점에서 즉시 저장: 사이클 시작/종료, 주문 준비/실행, 일일 실행 플래그 변경 등
        
  1. 전체 Application Architecture
   ```
   [클라이언트]
   Streamlit UI  ←→  [Streamlit Handler]                     
   Telegram Bot  ←→  [Telegram Handler]
                            ↕
                     [Event Bus/Queue]
                            ↕
                     [Application Core]
                     [Trading Engine][StockSubscriber]
                           ↕
                     [증권사 API Client (KIS API)]
   ```
- 주요 컴포넌트 설명
   - Application Core
      - 모든 비즈니스 로직을 담당      
      - Event Bus를 통해 UI와 Bot으로부터 명령을 수신                
      - 상태 관리 및 설정 관리     
      - Logging관리
      - 전략 관리 및 실행 : Trading Engine, StrategyManager를 통해서 전략 관리 및 실행
   - Event Bus/Queue [RxPy를 사용하여 구현] [구현완료]
      - Streamlit과 Telegram에서 오는 명령을 단일 채널로 통합  
      - Trading Engine에서 발생한 Event를 Event Bus를 통해 Telegram과 Streamlit UI에 전달
      - 비동기 이벤트 처리      
      - 명령 우선순위 관리      
   - Trading Engine [구현완료]
      - 실제 거래 로직 실행      
      - 시장 데이터 모니터링 
      - 포지션 관리
      - 다수의 전략 동시 실행       
      - StockSubscriber에서 제공하는 시세를 활용하여 전략 실행
      - Event Bus를 통해 다른 컴포넌트와 실시간 통신
   - StrategyManager
      - 전략 관리
      - 전략 실행 제어
      - 전략 상태 관리      
      
   - StockSubscriber
      - 증권사 API를 통해 실시간 시세 업데이트
   - Streamlit Handler [구현완료 - main.py]
      - Main Thread에서 동작, Streamlit Application의 구조를 따름.
      - Streamlit Server를 통해 Web UI 제공           
      - 실시간 전략 수행 상태 조회
      - Streamlit UI를 통해 들어온 명령을 Event Bus에 전달      
      - Trading Engine에서 발생한 Event를 Event Bus에서 받아서 Streamlit UI에 업데이트
   - Telegram Handler [구현완료]
      - 별도 스레드로 동작하며 Polling 방식으로 동작
      - 텔레그램 명령을 Event Bus에 전달
      - Trading Engine에서 발생한 Event를 Event Bus에서 받아서 알림/응답 발송      
      
- 기본 구조
   - Streamlit Application이 메인 진입점 (streamlit run main.py로 실행)
   - 하나의 메인 프로세스에서 모든 것을 관리
   - main.py가 Streamlit UI와 모든 서비스 컴포넌트를 통합 관리
   - Telegram Handler는 Event Bus를 통해 이벤트 수신/발송
   - Streamlit UI와 Telegram을 통해 들어온 Event를 Event Bus에 전달
   - EventBus는 양방향으로 작동=> Trading Engine에서 발생한 Event를 Event Bus를 통해 Telegram과 Streamlit UI에 전달

7. 구현된 주요 컴포넌트 상세

7.1 InfiniteBuyingStrategy (무한매수 전략)
   - 위치: src/strategy/infinite_buying.py
   - 구현된 기능:
      - 사이클 관리 (_start_new_cycle, _end_cycle)
      - 파라메터 계산 (_calculate_parameters)
      - 매수/매도 주문 생성 (_create_buy_orders, _create_sell_orders)
      - 시간 체크 (_is_pre_market_time, _is_after_market_end_time)
      - 주문 실행 (_execute_orders)
      - 상태 저장/로드 (save_state, load_state)
      - **강화된 상태 관리 시스템 [신규 개선]:**
         * save_state(): 원자적 저장 + 백업 시스템 + 재시도 메커니즘
         * load_state(): 백업 파일 자동 복구 + 무결성 검증
         * _validate_state_data(): 상태 데이터 무결성 검증
         * 모든 상태 변경점에서 즉시 save_state() 호출
         * 저장 실패시 텔레그램 긴급 알림
      - **상태 파일 시스템:**
         * 메인 파일: strategy_state_{symbol}.json
         * 백업 파일: strategy_state_{symbol}.backup.json
         * 임시 파일: strategy_state_{symbol}.tmp.json (원자적 저장용)

7.1.1 장애 복구 시나리오 [견고성 보장]

   **시나리오 1: 정전/프로그램 강제 종료**
   ```
   [프로그램 재시작]
        ↓
   [load_state() 자동 호출]
        ↓
   [메인 파일에서 상태 복원] ─→ 성공시 정상 재개
        ↓ (실패시)
   [백업 파일에서 자동 복구] ─→ 성공시 재개 + 메인 파일 재생성
        ↓ (실패시)
   [기본 상태로 안전 시작] ─→ 포지션 API 재동기화
   ```

   **시나리오 2: 상태 파일 손상**
   ```
   [무결성 검증 실패 감지]
        ↓
   [백업 파일에서 자동 복구]
        ↓
   [메인 파일 재생성]
        ↓
   [정상 동작 재개]
   ```

   **시나리오 3: 모든 파일 손실**
   ```
   [파일 존재 확인 실패]
        ↓
   [기본 상태로 안전 시작]
        ↓
   [새로운 상태 파일 생성]
        ↓
   [포지션 정보 API에서 재동기화]
        ↓
   [정상 전략 실행]
   ```

   **복구 보장 사항:**
   - 최대 복구 시간: 30초 이내
   - 데이터 손실: 최대 5분간의 실행 기록만 손실 가능
   - 포지션 정보: 100% 정확 복구 (API 조회 기반)
   - 사이클 상태: 완전 복구 또는 안전한 재시작
   - 실행 플래그: 당일 중복 실행 방지 보장

7.2 KIS API Client
   - 위치: src/api/kis_client.py
   - 구현된 API 메서드:
      - login(): 토큰 발급
      - get_oversea_stock_price(): 해외주식 현재가
      - get_oversea_balance(): 해외주식 잔고
      - create_oversea_order(): 해외주식 주문
      - get_oversea_open_orders(): 미체결 주문
      - cancel_oversea_order(): 주문 취소
      - get_oversea_orders(): 주문내역 조회 [신규 추가]
      - get_pending_orders(): 미체결 주문 조회 [신규 추가]
      - cancel_order(): 주문 취소 (통합) [신규 추가]
   
   - 공통 기능:
      - _wait_for_rate_limit(): API 호출 속도 제한 (50ms) [신규 추가]
      - _get_tr_id(): 모의/실전 TR ID 자동 매핑 [개선]
      - _safe_float(): 안전한 숫자 변환 [신규 추가]
      - 자동 토큰 갱신
      - 에러 처리 및 로깅

7.3 무한매수전략 파라메터
   - 기본 파라메터:
      - division_count: 40 (분할수)
      - total_investment: 총투자금
      - profit_ratio_max: 12% (최대익절비율)
      - profit_ratio_min: 8% (최소익절비율)
   - 계산된 파라메터:
      - current_round: 현재회차(T)
      - progress_ratio: 진행비율
      - star_price: Star가격
      - profit_price: 익절가격

7.4 주문 실행 타이밍
   - 프리마켓 5분전 (22:25): 주문 준비
   - 프리마켓 1분후 (22:31): 주문 실행
   - 애프터마켓 종료 (09:00): 사이클 체크

7.5 주문 체결 확인 시스템 [신규 구현]

7.5.1 REST API 기반 체결 확인
   - 위치: src/api/kis_client.py
   - 구현된 메서드:
      - get_oversea_orders(order_date): 해외주식 주문내역 조회 (당일/특정일)
      - get_pending_orders(): 미체결 주문 조회
      - cancel_order(order_id): 주문 취소
      - _safe_float(): 안전한 float 변환 (빈 문자열 처리)
      - _wait_for_rate_limit(): API 호출 속도 제한 관리 (50ms 간격)
   
   - 사용 TR ID:
      - TTTS3035R/VTTS3035R: 해외주식 주문체결내역 조회
      - TTTS3031R/VTTS3031R: 해외주식 미체결 주문 조회
      - TTTS0308U/VTTS0308U: 해외주식 주문 취소

7.5.2 WebSocket 실시간 체결 통보 [신규 구현]
   - 위치: src/api/kis_websocket.py
   - 주요 기능:
      - 실시간 체결통보 수신 (AES256 복호화)
      - 자동 재연결 관리
      - 비동기 콜백 처리
      - Approval Key 관리

   - 구현된 클래스: KISWebSocketClient
      - connect(): WebSocket 연결
      - subscribe_execution(callback): 체결통보 구독
      - disconnect(): 연결 해제
      - _decrypt_data(): AES256 데이터 복호화
      - _handle_message(): 메시지 처리 및 콜백 호출

7.5.3 전략에서의 체결 확인 로직 [신규 구현 + 주문 타입별 최적화]
   - 위치: src/strategy/infinite_buying.py
   - 구현된 메서드:
      - _get_order_execution_schedule(): 주문 타입별 체결 전략 정의
         * LOC: 장 마감(06:05) 후 확인, 최대 1시간 대기
         * AFTER: 애프터마켓 시간 1분 후 확인, 최대 4시간 대기
         * LIMIT: 즉시 + 30초 후 확인, 24시간 대기 가능
         * MARKET: 즉시 + 10초 후 확인, 6분만 대기
      
      - _should_check_order_now(): 현재 시점 체결 확인 필요성 판단
         * 주문 타입별 스케줄 기반 최적화
         * LOC: 미국 장 마감 시점 고려
         * AFTER: 애프터마켓 시간(05:00-09:00) 확인
         * MARKET/LIMIT: 즉시성 체결 확인
      
      - _schedule_execution_checks(): 주문 실행 후 타입별 체결 전략 적용
         * 즉시 확인 필요: 10초 대기 후 확인
         * 지연 확인 필요: 최소 대기시간 적용
         * 특정 시간 확인: 정기 체크 위임
      
      - _smart_order_execution_check(): 5분 주기 스마트 체결 확인
         * 불필요한 API 호출 방지
         * 주문 타입별 확인 필요성 사전 판단
         * 효율적인 리소스 사용
      
      - _manage_pending_orders_by_type(): 타입별 미체결 주문 관리
         * LOC: 장 마감 전/후 상태별 처리
         * AFTER: 애프터마켓 시간 확인
         * MARKET: 미체결시 즉시 알림
         * LIMIT: 조건부 대기 처리
      
      - _is_order_expired(): 주문 타입별 만료 시간 확인
         * 타입별 최대 대기시간 적용
         * 스마트 취소 정책

   - 실행 타이밍:
      - 매 5분마다: 스마트 체결 상태 확인 (필요시에만)
      - 주문 실행 후: 타입별 최적화된 체결 확인
         * MARKET: 10초 후 즉시 확인
         * LIMIT: 30초 후 확인
         * AFTER: 1분 후 확인 (애프터마켓 시간만)
         * LOC: 장 마감 후 확인 (06:05~06:10)
      - 만료된 주문: 타입별 최대 대기시간 후 자동 취소

7.5.4 통합 알림 시스템 [신규 구현]
   - 체결 즉시 알림: 개별 주문 체결 시 텔레그램 알림
   - 주문 실행 완료 알림: 일괄 주문 실행 후 요약 알림
   - 미체결 주문 알림: 자동 취소 시 상세 정보 제공
   - 체결 내역 로깅: 모든 체결 과정 상세 기록

7.5.5 알림 및 로깅 헬퍼 시스템 [신규 구현]
   - 위치: src/strategy/infinite_buying.py
   - 구현된 헬퍼 메서드:
      - _log_and_notify(): 로그와 텔레그램 통합 처리
      - _notify_cycle_start(): 사이클 시작 알림
      - _notify_cycle_end(): 사이클 종료 알림
      - _notify_strategy_restart(): 전략 재시작 알림
      - _notify_strategy_stop(): 전략 종료 알림
      - _notify_orders_executed(): 주문 실행 완료 알림
      - _notify_trade_alert(): 개별 거래 알림

   - 개선 효과:
      - 코드 중복 제거 (40줄 → 9줄 등)
      - 유지보수성 향상
      - 일관된 메시지 포맷
      - 가독성 대폭 개선

7.5.6 주문 체결 확인 플로우 (주문 타입별 최적화)
   ```
   [주문 실행] 
        ↓
   [주문 타입 분석] ─→ LOC/AFTER/LIMIT/MARKET
        ↓
   [타입별 체결 전략 적용]
   ├─ MARKET: 10초 후 즉시 확인
   ├─ LIMIT: 30초 후 확인 + 지속 모니터링  
   ├─ AFTER: 1분 후 확인 (애프터마켓 시간만)
   └─ LOC: 장 마감 후 확인 (한국시간 06:05)
        ↓
   [스마트 체결 확인] ─→ 필요시에만 API 호출
        ↓
   [타입별 미체결 관리] ─→ 만료시간별 자동 취소
        ↓
   [포지션 동기화] ─→ [텔레그램 알림]
   ```

7.5.7 에러 처리 및 복구
   - API 호출 실패: 재시도 로직 및 에러 로깅
   - WebSocket 연결 끊김: 자동 재연결
   - 체결 확인 실패: 수동 확인 안내 메시지
   - 데이터 불일치: 포지션 재동기화

7.5.8 성능 최적화
   - Rate Limit 관리: 500ms 간격으로 API 호출 제한 (개선됨)
   - 캐싱: 중복 조회 방지
   - 비동기 처리: WebSocket 논블로킹 처리
   - 메모리 관리: 불필요한 데이터 정리

8. 최신 구조 개선 사항 (2025.07.25)

8.1 상태 파일 관리 시스템 개선
   - **states/ 디렉토리 도입**: 모든 상태 파일을 전용 폴더에 정리
      - 메인 파일: states/strategy_state_{symbol}.json
      - 백업 파일: states/strategy_state_{symbol}.backup.json
      - 임시 파일: states/strategy_state_{symbol}.tmp.json
   - **버전 관리 최적화**: .gitignore에 states/ 폴더 추가로 개인 상태 파일 제외
   - **코드 개선**: os.path.join() 사용으로 운영체제 무관 경로 처리
   - **자동 폴더 생성**: os.makedirs(exist_ok=True)로 states 폴더 자동 생성

8.2 API URL 관리 시스템 개선
   - **이중 URL 시스템 도입**: config.yaml에서 모의투자/실전투자 URL 분리
      ```yaml
      api:
        base_url_real: "https://openapi.koreainvestment.com:9443"      # 실전투자용
        base_url_virtual: "https://openapivts.koreainvestment.com:29443"  # 모의투자용
        is_virtual: true  # 모의투자: true, 실전투자: false
      ```
   - **자동 URL 선택**: kis_client.py에서 is_virtual 설정에 따라 적절한 URL 자동 선택
   - **하위 호환성**: 기존 base_url 설정도 계속 지원
   - **명확한 모드 표시**: 로그에 "모의투자 모드" 또는 "실전투자 모드" 표시

8.3 더미 모드 제거 및 실제 API 사용
   - **더미 모드 완전 제거**: 개발용 더미 데이터 반환 로직 삭제
   - **실제 모의투자 API 사용**: 한국투자증권 공식 모의투자 서버 연동
   - **is_dummy_mode 플래그 제거**: 불필요한 플래그 정리
   - **DUMMY_TOKEN 체크 제거**: 모든 더미 토큰 관련 로직 삭제

8.4 API Rate Limit 최적화
   - **요청 간격 조정**: 50ms → 500ms로 변경 (초당 2회 제한)
   - **안전성 향상**: 모의투자 API 안정성을 위한 보수적 접근
   - **로깅 개선**: Rate Limit 대기 시간을 debug 레벨로 상세 기록
   - **재시도 로직**: Rate Limit 감지 시 자동 재시도 메커니즘

8.5 설정 키 이름 통일
   - **config.yaml과 코드 간 일치**: 
      - profit_ratio_max → max_profit_rate
      - profit_ratio_min → min_profit_rate  
      - star_correction_ratio → star_adjustment_rate
   - **전체 코드베이스 동기화**: infinite_buying.py, main.py 모두 수정
   - **하위 호환성 고려**: 기존 설정 파일도 정상 동작 보장

8.6 UI 시스템 개선
   - **투자 모드 표시**: 사이드바 상단에 현재 모드 명확 표시
      - 🧪 모의투자 모드 (초록색)
      - ⚠️ 실전투자 모드 (빨간색)
   - **API URL 표시**: 현재 사용 중인 API 서버 URL 표시
   - **재초기화 기능**: "🔄 앱 재초기화" 버튼으로 설정 변경 후 즉시 적용
   - **세션 상태 관리**: 강제 초기화 시 깔끔한 상태 정리

8.7 로깅 및 에러 처리 개선
   - **반복 에러 필터링**: "해당 서비스를 찾을수 없습니다" 등을 debug 레벨로 처리
   - **에러 분류**: 서비스 에러와 실제 문제 구분하여 로깅
   - **포지션 업데이트 안전성**: 기본값 설정으로 에러 상황에서도 안정적 동작
   - **상세 에러 추적**: 전략 시작 실패 시 상세 정보 기록

8.8 텔레그램 알림 개선
   - **모드 표시**: 알림 메시지에 "🧪(모의투자)" 표시 추가
   - **명확한 구분**: 실전투자와 모의투자 알림 구분
   - **투자 모드 안전성**: 실수로 실전투자 실행 방지

8.9 파일 구조 최적화
   - **states/ 폴더**: 모든 상태 파일을 전용 디렉토리에 집중
   - **.gitignore 업데이트**: states/ 폴더를 버전 관리에서 제외
   - **기존 파일 이전**: 루트 디렉토리의 상태 파일들을 states/로 자동 이전
   - **권한 및 보안**: 상태 파일들의 적절한 접근 권한 관리

8.10 개선 효과 및 장점
   - **안정성**: 실제 모의투자 API 사용으로 신뢰성 향상
   - **명확성**: 투자 모드가 UI에서 명확히 구분됨
   - **유지보수성**: 상태 파일 정리로 관리 편의성 증대
   - **확장성**: 모의투자/실전투자 간 쉬운 전환
   - **안전성**: 실수로 실전투자 실행할 위험 감소
   - **개발 효율성**: 설정 변경 후 즉시 적용 가능

8.11 향후 개선 계획
   - **다중 계좌 지원**: 계좌별 URL 설정
   - **환경별 설정**: 개발/테스트/운영 환경 분리
   - **설정 검증**: 시작 시 설정 파일 유효성 자동 검증
   - **백업 복구**: states 폴더 자동 백업/복구 시스템

9. StockSubscriber 시스템 구현 (2025.07.25)

9.1 StockSubscriber 아키텍처
   - **목적**: 실시간 주식 가격 모니터링 및 로깅 시스템
   - **구현 위치**: `src/trading/stock_subscriber.py`
   - **실행 방식**: 백그라운드 스레드 기반 1분 주기 실행
   - **지원 시장**: 미국 주식(US), 한국 주식(KR)
   - **이벤트 연동**: EventBus를 통한 가격 업데이트 이벤트 발행

   ```python
   class StockSubscriber:
       def __init__(self, kis_client, event_bus):
           # 초기화: KIS API 클라이언트, 이벤트 버스 연결
       
       def subscribe(self, symbol: str, market: str):
           # 심볼 구독 등록
       
       def start(self):
           # 백그라운드 모니터링 시작
       
       def _price_monitoring_loop(self):
           # 1분마다 실행되는 가격 조회 루프
   ```

9.2 핵심 기능
   - **자동 가격 조회**: 1분마다 REST API로 실시간 가격 확인
   - **장시간 체크**: 각 시장별 거래 시간 자동 감지
      - 미국: 한국시간 23:30-06:00 (서머타임 22:30-05:00)
      - 한국: 09:00-15:30
   - **스마트 로깅**: 가격 변동 시 상세 로그, 변동 없으면 디버그 레벨
   - **에러 처리**: 연속 실패 시 경고, 자동 재시도 메커니즘
   - **스레드 안전**: threading.Event를 이용한 안전한 종료

9.3 TradingEngine 통합
   ```python
   # src/trading_engine.py 주요 변경사항
   def __init__(self, event_bus=None, kis_client=None):
       # StockSubscriber 자동 초기화
       if kis_client:
           self.stock_subscriber = StockSubscriber(kis_client, event_bus)
   
   def _register_strategy_symbols(self, strategy):
       # 무한매수 전략 시작 시 자동 심볼 등록
       # SOXL (미국), 005930 (삼성전자) 자동 등록
   ```

9.4 API 확장
   ```python
   # src/api/kis_client.py 추가 메서드
   def get_domestic_stock_price(self, symbol: str):
       """국내주식 현재가 조회
       
       Args:
           symbol: 주식 종목 코드 (예: "005930")
           
       Returns:
           dict: 현재가 정보
       """
       # TR ID: FHKST01010100 (국내주식 현재가 시세)
       # 삼성전자 등 한국 주식 가격 조회 지원
   ```

9.5 UI 시스템 통합
   ```python
   # main.py 사이드바 추가 기능
   📊 가격 모니터링
   🟢 실행 중 / 🟡 중지됨
   
   구독 중인 심볼들:
   🇺🇸 SOXL: $16.67 (마지막 업데이트: 10:59:30)
   🇰🇷 005930: ₩66,100 (마지막 업데이트: 11:00:32)
   ```

9.6 실행 흐름
   1. **초기화**: TradingEngine 시작 시 StockSubscriber 자동 생성
   2. **심볼 등록**: 무한매수 전략 추가 시 SOXL, 삼성전자 자동 구독
   3. **모니터링 시작**: 첫 번째 전략 시작 시 백그라운드 루프 시작
   4. **가격 조회**: 1분마다 각 심볼의 현재가 REST API 호출
   5. **장시간 체크**: 거래 시간 외에는 조회 스킵 (로그 스팸 방지)
   6. **로깅**: 가격 변동 시 📈📉 이모지와 함께 상세 로그
   7. **이벤트 발행**: EventBus로 가격 업데이트 이벤트 전파
   8. **안전 종료**: 모든 전략 중지 시 StockSubscriber도 함께 중지

9.7 실시간 로그 예시
   ```
   [2025-07-25 10:57:14] INFO - 📊 StockSubscriber 초기화 완료
   [2025-07-25 10:57:14] INFO - 📈 심볼 구독 시작: SOXL (US 시장)
   [2025-07-25 10:57:14] INFO - 📈 심볼 구독 시작: 005930 (KR 시장)
   [2025-07-25 10:57:21] INFO - 💡 가격 모니터링 루프 시작
   [2025-07-25 10:58:26] INFO - 📈 005930 (KR): $66150.00 (+50.00, +0.08%)
   [2025-07-25 10:59:30] INFO - 📉 005930 (KR): $66050.00 (-100.00, -0.15%)
   [2025-07-25 11:00:32] INFO - 📉 005930 (KR): $66000.00 (-50.00, -0.08%)
   ```

9.8 장시간 감지 시스템
   ```python
   def _is_market_open(self, market: str, current_time: datetime) -> bool:
       korea_time = current_time + timedelta(hours=9)  # UTC+9
       
       if market == "us":
           # 미국 장시간 (한국시간 기준)
           # 서머타임: 22:30-05:00, 일반: 23:30-06:00
       elif market == "kr":
           # 한국 장시간: 09:00-15:30
           # 점심시간: 12:00-13:00 (거래 가능)
   ```

9.9 에러 처리 및 안정성
   - **연속 실패 처리**: 5회 연속 실패 시 경고 후 카운터 리셋
   - **Rate Limit 대응**: API 호출 간격 0.5초로 제한
   - **스레드 안전성**: threading.Event로 깔끔한 종료 처리
   - **메모리 관리**: 불필요한 데이터 정리 및 효율적 저장
   - **예외 복구**: 개별 심볼 실패가 전체 시스템에 영향 없음

9.10 성능 최적화
   - **스마트 로깅**: 변동 없을 시 DEBUG 레벨 (로그 스팸 방지)
   - **장시간 스킵**: 거래 시간 외 API 호출 최소화
   - **비동기 처리**: 백그라운드 스레드로 메인 애플리케이션 블로킹 없음
   - **이벤트 기반**: EventBus를 통한 느슨한 결합 구조

9.11 확장 가능성
   - **다중 심볼**: 무제한 심볼 추가 지원
   - **다중 시장**: 미국, 한국 외 추가 시장 확장 가능
   - **실시간 알림**: 텔레그램 봇 연동 준비
   - **WebSocket 업그레이드**: 향후 실시간 스트리밍 대응 가능
   - **데이터베이스 연동**: 가격 히스토리 저장 확장 가능







