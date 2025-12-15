# 애플리케이션 로딩 후 실행 전략

## 1. 애플리케이션 초기화 완료 후 자동 실행 전략

### 1.1 시스템 상태 점검 및 복구
```python
def post_initialization_strategy():
    """애플리케이션 초기화 완료 후 자동 실행되는 전략"""
    
    # 1. 기존 실행 중인 전략 상태 복구
    strategy_manager.load_saved_strategies()
    
    # 2. 계좌 상태 및 포지션 확인
    account_status = kis_client.get_account_balance()
    current_positions = kis_client.get_positions()
    
    # 3. 시장 상태 확인 (장 시간, 휴장일 등)
    market_status = check_market_status()
    
    # 4. 네트워크 연결 상태 확인
    connection_status = verify_api_connections()
    
    return {
        'strategies': strategy_manager.get_active_strategies(),
        'account': account_status,
        'positions': current_positions,
        'market': market_status,
        'connection': connection_status
    }
```

### 1.2 무한매수 전략 자동 활성화 조건
- **기존 사이클이 진행 중인 경우**: 자동으로 전략 재개
- **새로운 사이클 시작 조건**: 
  - 기존 포지션이 없음
  - 사이클 시작일에 도달
  - 충분한 투자 자금 확보

## 2. 실시간 모니터링 및 실행 전략

### 2.1 시장 시간별 실행 전략

#### 프리마켓 시간 (한국시간 저녁 8:00-10:30)
```python
def premarket_strategy():
    """프리마켓 시간 전략"""
    
    # 1. 전일 결과 분석 및 리포트 생성
    daily_report = generate_daily_report()
    telegram_handler.send_daily_report(daily_report)
    
    # 2. 당일 매수/매도 계획 수립
    today_plan = calculate_today_trading_plan()
    
    # 3. 예약 주문 설정 (기본 모드)
    if strategy.mode == "basic":
        place_scheduled_orders(today_plan)
    
    # 4. 시장 뉴스 및 변동성 체크
    market_volatility = check_market_volatility()
    if market_volatility > threshold:
        adjust_strategy_parameters()
```

#### 정규 장시간 (한국시간 밤 10:30-새벽 5:00)
```python
def regular_market_strategy():
    """정규 장시간 실시간 전략"""
    
    if strategy.mode == "advanced":
        # Advanced 모드: 1분 주기 실시간 매매
        schedule_realtime_trading()
    else:
        # Basic 모드: 예약 주문 모니터링
        monitor_scheduled_orders()
    
    # 실시간 포지션 모니터링
    monitor_positions_realtime()
    
    # 익절/손절 조건 체크
    check_profit_loss_conditions()
```

#### 애프터마켓 시간 (한국시간 새벽 5:00-6:00)
```python
def aftermarket_strategy():
    """애프터마켓 시간 전략"""
    
    # 1. 당일 거래 결과 정리
    daily_summary = summarize_daily_trades()
    
    # 2. 포지션 상태 업데이트
    update_position_status()
    
    # 3. 사이클 완료 여부 체크
    if check_cycle_completion():
        complete_current_cycle()
        prepare_next_cycle()
    
    # 4. 텔레그램 일일 리포트 발송
    telegram_handler.send_end_of_day_report(daily_summary)
```

### 2.2 무한매수 전략 핵심 로직

#### DCA (Dollar Cost Averaging) 매수 전략
```python
def execute_dca_strategy():
    """DCA 매수 전략 실행"""
    
    # 현재 사이클 정보 조회
    current_cycle = strategy_manager.get_current_cycle()
    
    if not current_cycle:
        # 새로운 사이클 시작
        start_new_cycle()
        return
    
    # 매일 정해진 시간에 DCA 매수 실행
    if is_dca_time():
        dca_amount = current_cycle.daily_investment_amount  # 3,000원
        current_price = kis_client.get_current_price(current_cycle.symbol)
        
        # 매수 수량 계산
        buy_quantity = calculate_buy_quantity(dca_amount, current_price)
        
        # 매수 주문 실행
        order_result = kis_client.place_buy_order(
            symbol=current_cycle.symbol,
            quantity=buy_quantity,
            price=current_price
        )
        
        # 결과 기록 및 알림
        record_trade_result(order_result)
        telegram_handler.send_trade_notification(order_result)
```

#### Star 매수 전략 (급락 시 추가 매수)
```python
def execute_star_buying_strategy():
    """Star 매수 전략 (급락 시 추가 매수)"""
    
    current_cycle = strategy_manager.get_current_cycle()
    current_price = kis_client.get_current_price(current_cycle.symbol)
    
    # Star 가격 계산 (평단가 대비 6.34% 하락)
    star_price = current_cycle.average_price * (1 - current_cycle.star_price_ratio)
    
    if current_price <= star_price:
        # Star 매수 조건 충족
        star_quantity = current_cycle.star_buy_quantity  # 49주
        
        order_result = kis_client.place_buy_order(
            symbol=current_cycle.symbol,
            quantity=star_quantity,
            price=current_price
        )
        
        # Star 매수 기록
        record_star_trade(order_result)
        telegram_handler.send_star_buy_notification(order_result)
```

#### 익절 매도 전략
```python
def execute_profit_taking_strategy():
    """익절 매도 전략"""
    
    current_cycle = strategy_manager.get_current_cycle()
    current_price = kis_client.get_current_price(current_cycle.symbol)
    
    # 익절 가격 계산 (평단가 대비 11.23% 상승)
    profit_price = current_cycle.average_price * (1 + current_cycle.profit_ratio)
    
    if current_price >= profit_price:
        # 익절 조건 충족
        total_quantity = current_cycle.total_quantity
        
        # 전량 매도 또는 부분 매도 결정
        sell_quantity = determine_sell_quantity(current_cycle, current_price)
        
        order_result = kis_client.place_sell_order(
            symbol=current_cycle.symbol,
            quantity=sell_quantity,
            price=current_price
        )
        
        # 매도 결과 처리
        process_sell_result(order_result, current_cycle)
        
        # 전량 매도 완료 시 사이클 종료
        if is_cycle_complete(current_cycle):
            complete_cycle(current_cycle)
```

## 3. 이벤트 기반 자동 대응 전략

### 3.1 시장 변동성 대응
```python
def handle_market_volatility():
    """시장 변동성 대응 전략"""
    
    volatility_level = calculate_market_volatility()
    
    if volatility_level > HIGH_VOLATILITY_THRESHOLD:
        # 고변동성: 매수 간격 조정, 리스크 관리 강화
        adjust_dca_frequency(reduce=True)
        increase_monitoring_frequency()
        
    elif volatility_level < LOW_VOLATILITY_THRESHOLD:
        # 저변동성: 정상 운영
        restore_normal_operations()
```

### 3.2 API 연결 장애 대응
```python
def handle_api_failure():
    """API 연결 장애 대응 전략"""
    
    # 1. 자동 재연결 시도
    retry_connection()
    
    # 2. 백업 API 사용 (있는 경우)
    switch_to_backup_api()
    
    # 3. 긴급 알림 발송
    telegram_handler.send_emergency_alert("API 연결 장애 발생")
    
    # 4. 안전 모드 전환
    switch_to_safe_mode()
```

### 3.3 예상치 못한 손실 대응
```python
def handle_unexpected_loss():
    """예상치 못한 손실 대응 전략"""
    
    current_loss = calculate_current_loss()
    
    if current_loss > MAX_ACCEPTABLE_LOSS:
        # 긴급 손절 실행
        execute_emergency_stop_loss()
        
        # 전략 일시 중단
        pause_all_strategies()
        
        # 긴급 알림
        telegram_handler.send_emergency_alert(f"긴급 손절 실행: {current_loss}")
```

## 4. 자동화된 리포팅 및 모니터링

### 4.1 실시간 모니터링 대시보드
- Streamlit UI를 통한 실시간 포지션 모니터링
- 수익률, 평단가, 현재가 실시간 업데이트
- 차트를 통한 시각적 모니터링

### 4.2 텔레그램 자동 알림
```python
def automated_telegram_notifications():
    """자동화된 텔레그램 알림 시스템"""
    
    # 매수/매도 시 즉시 알림
    # 일일 수익률 리포트 (장 마감 후)
    # 주간/월간 성과 리포트
    # 긴급 상황 알림 (급락, API 장애 등)
    # 사이클 완료 알림
```

## 5. 전략 실행 우선순위

1. **최우선**: 안전성 확보 (손실 제한, API 연결 상태)
2. **높음**: 기존 포지션 관리 (익절/손절 조건 모니터링)
3. **보통**: 신규 매수 기회 포착 (DCA, Star 매수)
4. **낮음**: 최적화 및 개선 (파라미터 조정, 성과 분석)

## 6. 장애 상황별 대응 매뉴얼

### 6.1 시스템 재시작 시
- 기존 전략 상태 자동 복구
- 미완료 주문 상태 확인
- 포지션 동기화

### 6.2 네트워크 장애 시
- 오프라인 모드 전환
- 중요 데이터 로컬 백업
- 복구 후 자동 동기화

### 6.3 거래소 API 장애 시
- 대체 데이터 소스 활용
- 수동 개입 알림
- 안전 모드 운영

이 전략은 애플리케이션이 로딩된 후 자동으로 실행되어 24시간 무인 운영이 가능하도록 설계되었습니다.