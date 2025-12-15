import logging
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd  # 추가
import pytz  # 타임존 처리를 위해 추가
from src.api.kis_client import KISClient
from src.config import Config
from ..utils.telegram import TelegramHandler
from src.utils.event_bus import EventBus, Event, EventType
from src.trading.market_calendar import market_calendar  # 동적 타임존 처리를 위해 추가
from .trade_history import TradeHistory  # 거래 내역 관리 클래스

logger = logging.getLogger(__name__)

class InfiniteBuyingStrategy:
    """무한매수 전략 구현
    
    미국 SOXL, TQQQ 등 레버리지 3x 상품을 DCA로 매수하다가
    일정 수익이 나면 매도하는 중단기 매매 전략
    """
    
    def __init__(self, kis_client: KISClient, config: Config, event_bus: EventBus = None):
        """무한매수 전략 초기화
        
        Args:
            kis_client: 한국투자증권 API 클라이언트
            config: 설정 객체
            event_bus: 이벤트 버스 (옵션)
        """
        self.client = kis_client
        self.config = config
        self.event_bus = event_bus
        
        # 타임존 설정 추가
        self.korea_tz = pytz.timezone('Asia/Seoul')
        self.eastern_tz = pytz.timezone('US/Eastern')
        self.market_calendar = market_calendar
        
        # 텔레그램 핸들러 초기화 (기존 호환성)
        telegram_config = config.telegram if hasattr(config, 'telegram') else config.get('telegram', {})
        self.telegram = TelegramHandler(telegram_config)
        
        # 주문 승인 응답 대기 저장소
        self.pending_approvals = {}
        
        # EventBus 이벤트 핸들러 설정
        if self.event_bus:
            self._setup_event_handlers()
        
        # 무한매수 전략 설정 가져오기
        strategy_config = config.trading.get("infinite_buying_strategy", {})
        
        # 전략 기본 설정
        self.symbol = strategy_config.get("symbol", "SOXL")
        
        # 상태 파일 경로 설정 (states 폴더에 저장)
        import os
        states_dir = "states"
        os.makedirs(states_dir, exist_ok=True)  # states 폴더가 없으면 생성
        
        self.state_file = os.path.join(states_dir, f"strategy_state_{self.symbol}.json")
        self.backup_state_file = os.path.join(states_dir, f"strategy_state_{self.symbol}.backup.json")
        self.temp_state_file = os.path.join(states_dir, f"strategy_state_{self.symbol}.tmp.json")
        
        # 전략 상태 초기화
        self.state = {
            "active": False,
            "cycle_active": False,
            "cycle_start_date": None,
            "cycle_end_date": None,
            "last_execution_time": None,
            "daily_executions": {
                "date": None,  # 실행 추적 날짜
                "pre_market_prepare": False,  # 프리마켓 준비 실행 여부
                "orders_executed": False,     # 주문 실행 여부
                "cycle_end_checked": False    # 사이클 종료 체크 여부
            },
            "orders": {
                "buy": [],
                "sell": []
            }
        }
        
        # 전략 파라메터 (config에서 읽어오기)
        self.params = {
            # 사이클 관련
            "division_count": strategy_config.get("division_count", 40),  # 분할수
            "total_investment": strategy_config.get("total_investment", 1000000),  # 총투자금 (원)
            
            # 익절 전략 관련
            "max_profit_rate": strategy_config.get("max_profit_rate", 12),  # 최대익절비율(%)
            "min_profit_rate": strategy_config.get("min_profit_rate", 8),   # 최소익절비율(%)
            "star_adjustment_rate": strategy_config.get("star_adjustment_rate", 0),  # Star보정비율(%)
        }
        
        logger.info(f"무한매수 전략 파라메터 로드 완료:")
        logger.info(f"  - 종목: {self.symbol}")
        logger.info(f"  - 총투자금: {self.params['total_investment']:,}원")
        logger.info(f"  - 분할수: {self.params['division_count']}회")
        logger.info(f"  - 최대익절비율: {self.params['max_profit_rate']}%")
        logger.info(f"  - 최소익절비율: {self.params['min_profit_rate']}%")
        logger.info(f"  - Star보정비율: {self.params['star_adjustment_rate']}%")
        
        # 계산된 파라메터
        self.calculated_params = {}
        
        # 포지션 정보
        self.position = {
            "quantity": 0,
            "avg_price": 0,
            "total_cost": 0,
            "current_price": 0
        }
        
        # 상태 로드
        self.load_state()
        
        # 파라메터 계산
        self._calculate_parameters()
        
        # 거래 내역 관리 클래스 초기화 (테스트 모드 설정 가능)
        trade_history_test_mode = strategy_config.get("trade_history_test_mode", False)
        logger.info(f"🔧 거래내역 테스트 모드 설정: {trade_history_test_mode}")
        self.trade_history = TradeHistory(self.client, self.symbol, self.params, test_mode=trade_history_test_mode)
        
        logger.info(f"{self.symbol} 무한매수 전략 초기화 완료")
        logger.info(f"전략 파라메터: {self.params}")
    
    def _setup_event_handlers(self):
        """EventBus 이벤트 핸들러 설정"""
        # 주문 승인 응답 이벤트 구독
        self.event_bus.subscribe(
            EventType.ORDER_APPROVAL_RESPONSE,
            self._handle_approval_response
        )
    
    def _handle_approval_response(self, event: Event):
        """주문 승인 응답 이벤트 처리"""
        try:
            callback_id = event.data.get("callback_id")
            approved = event.data.get("approved", False)
            orders = event.data.get("orders", [])
            order_id = event.data.get("order_id")
            
            if callback_id in self.pending_approvals:
                logger.info(f"주문 승인 응답 처리: {order_id} -> {'승인' if approved else '거부'}")
                
                # 승인된 경우 주문 실행
                if approved:
                    self._execute_approved_orders_eventbus(orders)
                else:
                    logger.info("❌ 주문이 거부되었습니다.")
                    if self.telegram:
                        self.telegram.send_message("❌ 주문이 거부되어 실행이 취소되었습니다.")
                
                # 대기 중인 승인 정보 제거
                del self.pending_approvals[callback_id]
            else:
                logger.warning(f"알 수 없는 승인 응답: {callback_id}")
                
        except Exception as e:
            logger.error(f"주문 승인 응답 처리 오류: {e}")
        
    def init(self):
        """전략 초기화 (Trading Engine에서 호출)"""
        logger.info(f"🎯 {self.symbol} 무한매수 전략 초기화")
        
        self.state["active"] = True
        self.load_state()
        self._update_position()
        
        # 포지션 확인 후 처리
        if self.position["quantity"] == 0:
            # 잔량이 없으면 새 사이클 시작
            if not self.state["cycle_active"]:
                self._start_new_cycle()
        else:
            # 기존 포지션이 있으면 사이클 계속
            if not self.state["cycle_active"]:
                self.state["cycle_active"] = True
                self._notify_strategy_restart()
        
        self.save_state()
        
    def run(self):
        """전략 실행 (Trading Engine에서 주기적 호출)"""
        if not self.state["active"]:
            return
            
        current_time = datetime.now()
        today = current_time.date().isoformat()
        
        # 포지션 업데이트
        self._update_position()
        
        # 포지션이 0이고 사이클이 비활성화 상태면 새 사이클 시작
        if self.position["quantity"] == 0 and not self.state["cycle_active"]:
            logger.info("💡 포지션 없음 감지 - 새 사이클 시작 조건 확인")
            self._start_new_cycle()
            return  # 새 사이클 시작 후 이번 실행은 종료
        
        # 사이클이 활성화되지 않았으면 대기
        if not self.state["cycle_active"]:
            logger.debug("🔄 사이클 비활성화 상태 - 대기 중")
            return
        
        # 날짜가 바뀌었으면 일일 실행 플래그 리셋
        if self.state["daily_executions"]["date"] != today:
            logger.info(f"🗓️ 새로운 날짜 감지: {today} - 일일 실행 플래그 리셋")
            self.state["daily_executions"] = {
                "date": today,
                "pre_market_prepare": False,
                "orders_executed": False,
                "cycle_end_checked": False
            }
            # 중요한 상태 변경이므로 즉시 저장
            self.save_state()
        
        # 1. 프리마켓 시작 5분전 체크 (동적 타임존 처리)
        if (self._is_pre_market_prepare_time(current_time) and 
            not self.state["daily_executions"]["pre_market_prepare"]):
            self._log_and_notify("⏰ 프리마켓 준비 시간 도달 - 주문 준비 실행", log_level="info")
            self._prepare_pre_market_orders()
            self.state["daily_executions"]["pre_market_prepare"] = True
            # 상태 변경 후 저장
            self.save_state()
            
        # 2. 프리마켓 시작 1분 후 주문 실행 (동적 타임존 처리)
        elif (self._is_pre_market_execution_time(current_time) and 
              not self.state["daily_executions"]["orders_executed"]):
            self._log_and_notify("⏰ 주문 실행 시간 도달 - 주문 실행", log_level="info")
            self._execute_orders()
            self.state["daily_executions"]["orders_executed"] = True
            # 상태 변경 후 저장
            self.save_state()
            
        # 3. 애프터마켓 종료 체크 (동적 타임존 처리)
        elif (self._is_after_market_end_time(current_time) and 
              not self.state["daily_executions"]["cycle_end_checked"]):
            self._log_and_notify("⏰ 사이클 종료 체크 시간 도달 - 종료 체크 실행", log_level="info")
            self._check_cycle_end()
            self.state["daily_executions"]["cycle_end_checked"] = True
            # 상태 변경 후 저장
            self.save_state()
            
        # 4. 주문 체결 확인 (매 실행시마다 체크)
        self._check_order_execution()
        
        # 5. 스마트 주문 체결 확인 (5분마다, 주문 타입별 최적화)
        if not hasattr(self.state, "last_order_check_time"):
            self.state["last_order_check_time"] = current_time.isoformat()
            
        last_check_time = datetime.fromisoformat(self.state["last_order_check_time"])
        if (current_time - last_check_time).total_seconds() >= 300:  # 5분 = 300초
            logger.debug("🔍 5분 주기 스마트 주문 체결 확인")
            self._smart_order_execution_check(current_time)
            self.state["last_order_check_time"] = current_time.isoformat()

        self.state["last_execution_time"] = current_time.isoformat()
        self.save_state()
        
    def _smart_order_execution_check(self, current_time: datetime):
        """스마트 주문 체결 확인 (주문 타입별 최적화)"""
        try:
            # 미체결 주문 조회
            pending_orders = self.client.get_pending_orders(self.symbol)
            
            if not pending_orders:
                logger.debug(f"📋 {self.symbol} 미체결 주문 없음")
                return
                
            logger.info(f"📋 현재 {self.symbol} 미체결 주문: {len(pending_orders)}건 - 스마트 체크")
            
            # 주문 타입별 분류
            order_types_count = {}
            should_check_detailed = False
            
            for order in pending_orders:
                # 주문 타입 추정 (ord_dvsn 기준)
                ord_dvsn = order.get("ord_dvsn", "00")
                order_type = "LOC" if ord_dvsn == "34" else "AFTER" if ord_dvsn == "32" else "LIMIT"
                
                order_types_count[order_type] = order_types_count.get(order_type, 0) + 1
                
                # 주문 정보 구성
                order_info = {
                    "order_no": order.get("odno"),
                    "symbol": order.get("pdno"),
                    "side": "BUY" if order.get("sll_buy_dvsn_cd") == "02" else "SELL",
                    "quantity": int(order.get("ord_qty", "0")),
                    "price": float(order.get("ord_unpr", "0")),
                    "order_time": order.get("ord_tmd"),
                    "order_type": order_type
                }
                
                # 현재 시점에 체결 확인이 필요한지 판단
                if self._should_check_order_now(order_info, current_time):
                    should_check_detailed = True
                    logger.info(f"🔍 {order_type} 주문 상세 확인 필요: {order['odno']}")
                    
            # 주문 타입별 요약 로깅
            for order_type, count in order_types_count.items():
                schedule = self._get_order_execution_schedule(order_type)
                logger.info(f"📊 {order_type} 미체결: {count}건 ({schedule['description']})")
                
            # 상세 확인이 필요한 경우에만 API 호출
            if should_check_detailed:
                logger.info("🔍 상세 체결 확인 실행")
                self._check_order_execution()
            else:
                logger.debug("⏰ 현재 시점 체결 확인 불필요 - 대기 중")
                
        except Exception as e:
            logger.error(f"스마트 주문 체결 확인 중 오류: {str(e)}")
            
    def exit(self):
        """전략 종료"""
        self.state["active"] = False
        self._cancel_all_orders()
        self.save_state()
        
        # 알림 전송
        self._notify_strategy_stop()
        
    def save_state(self):
        """전략 상태 저장 (원자적 저장 + 백업)"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                state_data = {
                    "state": self.state,
                    "params": self.params,
                    "calculated_params": self.calculated_params,
                    "position": self.position,
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0"  # 호환성을 위한 버전 정보
                }
                
                # 1. 임시 파일에 먼저 저장 (원자적 저장)
                with open(self.temp_state_file, 'w', encoding='utf-8') as f:
                    json.dump(state_data, f, ensure_ascii=False, indent=2)
                
                # 2. 기존 상태 파일이 있으면 백업으로 복사
                if os.path.exists(self.state_file):
                    shutil.copy2(self.state_file, self.backup_state_file)
                
                # 3. 임시 파일을 실제 상태 파일로 이동 (원자적 연산)
                shutil.move(self.temp_state_file, self.state_file)
                
                logger.debug(f"전략 상태 저장 완료 (시도 {attempt + 1})")
                return
                
            except Exception as e:
                logger.warning(f"전략 상태 저장 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                
                # 임시 파일 정리
                if os.path.exists(self.temp_state_file):
                    try:
                        os.remove(self.temp_state_file)
                    except:
                        pass
                        
                if attempt == max_retries - 1:
                    logger.error(f"전략 상태 저장 최종 실패: {str(e)}")
                    # 텔레그램 긴급 알림
                    self.telegram.send_message(f"🚨 <b>긴급:</b> {self.symbol} 전략 상태 저장 실패!\n\n상세: {str(e)}")
                    
    def load_state(self):
        """전략 상태 로드 (백업 파일 자동 복구)"""
        state_files = [self.state_file, self.backup_state_file]
        
        for state_file in state_files:
            try:
                if not os.path.exists(state_file):
                    continue
                    
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                # 상태 무결성 검증
                if not self._validate_state_data(state_data):
                    logger.warning(f"상태 파일 무결성 검증 실패: {state_file}")
                    continue
                
                # 상태 복원
                self.state = state_data.get("state", self.state)
                self.params.update(state_data.get("params", {}))
                self.calculated_params = state_data.get("calculated_params", {})
                self.position = state_data.get("position", self.position)
                
                logger.info(f"전략 상태 로드 완료 (파일: {state_file})")
                
                # 메인 파일이 아닌 백업에서 복원했다면 메인 파일로 저장
                if state_file != self.state_file:
                    logger.info("백업 파일에서 복원됨 - 메인 상태 파일 재생성")
                    self.save_state()
                    
                return
                
            except Exception as e:
                logger.warning(f"전략 상태 로드 실패 ({state_file}): {str(e)}")
                
        # 모든 상태 파일 로드 실패시
        logger.warning("모든 상태 파일 로드 실패 - 기본 상태로 시작")
        self.save_state()  # 기본 상태 저장
        
    def _validate_state_data(self, state_data: dict) -> bool:
        """상태 데이터 무결성 검증"""
        try:
            # 필수 키 확인
            required_keys = ["state", "params", "timestamp"]
            for key in required_keys:
                if key not in state_data:
                    logger.warning(f"필수 키 누락: {key}")
                    return False
            
            # 상태 구조 확인
            state = state_data.get("state", {})
            required_state_keys = ["active", "cycle_active", "daily_executions", "orders"]
            for key in required_state_keys:
                if key not in state:
                    logger.warning(f"상태 필수 키 누락: {key}")
                    return False
            
            # 타임스탬프 확인 (너무 오래된 파일은 의심)
            timestamp_str = state_data.get("timestamp", "")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
                age_days = (datetime.now() - timestamp).days
                if age_days > 30:  # 30일 이상 오래된 파일
                    logger.warning(f"상태 파일이 너무 오래됨: {age_days}일")
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"상태 검증 중 오류: {str(e)}")
            return False
        
    def _start_new_cycle(self):
        """새 사이클 시작"""
        cycle_start_time = datetime.now()
        
        self.state["cycle_active"] = True
        self.state["cycle_start_date"] = cycle_start_time.date().isoformat()
        self.state["cycle_end_date"] = None
        
        # 파라메터 초기화
        self._calculate_parameters()
        
        # 현재 포지션 업데이트
        self._update_position()
        
        # 상태 저장 (중요한 상태 변경)
        self.save_state()
        
        # 알림 전송
        self._notify_cycle_start()
        
    def _end_cycle(self):
        """사이클 종료"""
        cycle_end_time = datetime.now()
        
        self.state["cycle_active"] = False
        self.state["cycle_end_date"] = cycle_end_time.date().isoformat()
        
        # 상태 저장 (중요한 상태 변경)
        self.save_state()
        
        # 알림 전송
        self._notify_cycle_end()
        
        # 사이클 결과 기록
        # TODO: 사이클 결과를 별도 파일이나 DB에 저장
        
    def _update_position(self):
        """현재 포지션 정보 업데이트"""
        try:
            # 보유 잔고 조회
            balance = self.client.get_oversea_balance()
            
            # 기본값으로 초기화
            self.position["quantity"] = 0
            self.position["avg_price"] = 0
            self.position["total_cost"] = 0
            
            for item in balance:
                if item["symbol"] == self.symbol:
                    self.position["quantity"] = int(float(item["qty"]))
                    self.position["avg_price"] = float(item["avg_price"])
                    self.position["total_cost"] = self.position["quantity"] * self.position["avg_price"]
                    break
                    
            # 현재가 조회
            price_info = self.client.get_oversea_stock_price(self.symbol)
            self.position["current_price"] = float(price_info.get("current_price", 100.0))
            
            logger.debug(f"포지션 업데이트: {self.position}")
            
        except Exception as e:
            logger.error(f"포지션 업데이트 실패: {str(e)}")
            # 에러 발생 시 안전한 기본값으로 설정
            if self.position.get("current_price", 0) == 0:
                self.position["current_price"] = 100.0  # 기본 현재가 설정
        
    def _calculate_parameters(self):
        """전략 파라메터 계산"""
        # 포지션 정보 업데이트
        self._update_position()
        
        # 1일 매수금
        daily_amount = self.params["total_investment"] / self.params["division_count"]
        
        # 현재회차(T) 계산
        current_round = 0
        if self.position["total_cost"] > 0 and daily_amount > 0:
            current_round = int(self.position["total_cost"] / daily_amount)
            
        # 진행비율
        progress_ratio = (current_round / self.params["division_count"]) * 100
        
        # 실투자비율
        actual_investment_ratio = (self.position["total_cost"] / self.params["total_investment"]) * 100
        
        # Star가격비율 계산
        max_star_ratio = self.params["max_profit_rate"] - 2.5
        star_price_ratio = max_star_ratio - (progress_ratio/100) * max_star_ratio * 2 + self.params["star_adjustment_rate"]
        
        # Star가격
        star_price = self.position["avg_price"] * (1 + star_price_ratio/100)
        
        # Star수량
        star_quantity = int((daily_amount / 2) / star_price) if star_price > 0 else 0
        
        # 평단매수수량 (T <= 20일 때만)
        avg_buy_quantity = 0
        if current_round <= 20 and self.position["avg_price"] > 0:
            daily_quantity = int(daily_amount / self.position["current_price"]) if self.position["current_price"] > 0 else 0
            avg_buy_quantity = daily_quantity - star_quantity
            
        # 익절비율 계산
        profit_ratio = (self.params["max_profit_rate"] * (1 - progress_ratio/100) + 
                       self.params["min_profit_rate"] * progress_ratio/100)
        
        # 익절가격
        profit_price = self.position["avg_price"] * (1 + profit_ratio/100)
        
        # 계산된 파라메터 저장
        self.calculated_params = {
            "daily_amount": daily_amount,
            "current_round": current_round,
            "progress_ratio": progress_ratio,
            "actual_investment_ratio": actual_investment_ratio,
            "star_price_ratio": star_price_ratio,
            "star_price": star_price,
            "star_quantity": star_quantity,
            "avg_buy_quantity": avg_buy_quantity,
            "profit_ratio": profit_ratio,
            "profit_price": profit_price
        }
        
        logger.info(f"파라메터 계산 완료: T={current_round}, 진행비율={progress_ratio:.1f}%")
        
    def _prepare_pre_market_orders(self):
        """프리마켓 주문 준비"""
        logger.info("프리마켓 주문 준비 시작")
        
        # 기존 주문 취소
        self._cancel_all_orders()
        
        # 파라메터 재계산
        self._calculate_parameters()
        
        # 매수/매도 주문 생성
        self._create_buy_orders()
        self._create_sell_orders()
        
        # 상태 저장 (주문 정보 변경)
        self.save_state()
        
    def _create_buy_orders(self):
        """매수 주문 생성"""
        orders = []
        current_round = self.calculated_params["current_round"]
        
        if current_round <= 20:
            # Star가격 매수
            if self.calculated_params["star_quantity"] > 0:
                orders.append({
                    "type": "star_buy",
                    "price": round(self.calculated_params["star_price"], 2),
                    "quantity": self.calculated_params["star_quantity"],
                    "order_type": "LOC"  # Limit on Close
                })
                
            # 평단 매수
            if self.calculated_params["avg_buy_quantity"] > 0:
                orders.append({
                    "type": "avg_buy",
                    "price": round(self.position["avg_price"], 2),
                    "quantity": self.calculated_params["avg_buy_quantity"],
                    "order_type": "LOC"
                })
                
        else:  # T > 20
            # Star가격에 1일매수금 전체로 매수
            star_price = self.calculated_params["star_price"]
            if star_price > 0:
                quantity = int(self.calculated_params["daily_amount"] / star_price)
                if quantity > 0:
                    orders.append({
                        "type": "star_buy_full",
                        "price": round(star_price, 2),
                        "quantity": quantity,
                        "order_type": "LOC"
                    })
                    
        # 추가 매수 주문 (현재가에서 30% 하락까지)
        self._create_additional_buy_orders(orders)
        
        self.state["orders"]["buy"] = orders
        logger.info(f"매수 주문 생성 완료: {len(orders)}건")
        
    def _create_additional_buy_orders(self, orders: List[Dict]):
        """추가 매수 주문 생성 (30% 하락까지)"""
        current_price = self.position["current_price"]
        if current_price <= 0:
            return
            
        daily_amount = self.calculated_params["daily_amount"]
        star_qty = self.calculated_params["star_quantity"]
        avg_qty = self.calculated_params["avg_buy_quantity"]
        
        # 추가 매수 시작 가격 계산
        base_quantity = star_qty + avg_qty + 1
        
        for i in range(10):  # 최대 10개 주문
            price = daily_amount / (base_quantity + i)
            
            # 현재가 대비 30% 이상 하락하면 중단
            if price < current_price * 0.7:
                break
                
            orders.append({
                "type": f"additional_buy_{i+1}",
                "price": round(price, 2),
                "quantity": 1,
                "order_type": "LOC"
            })
            
    def _create_sell_orders(self):
        """매도 주문 생성"""
        orders = []
        
        if self.position["quantity"] <= 0:
            self.state["orders"]["sell"] = orders
            return
            
        # Star 매도 (보유수량의 1/4)
        star_sell_qty = int(self.position["quantity"] / 4)
        if star_sell_qty > 0:
            star_sell_price = self.calculated_params["star_price"] + 0.01
            orders.append({
                "type": "star_sell",
                "price": round(star_sell_price, 2),
                "quantity": star_sell_qty,
                "order_type": "LOC"
            })
            
        # 익절 매도 (나머지 전량)
        profit_sell_qty = self.position["quantity"] - star_sell_qty
        if profit_sell_qty > 0:
            orders.append({
                "type": "profit_sell",
                "price": round(self.calculated_params["profit_price"], 2),
                "quantity": profit_sell_qty,
                "order_type": "AFTER"  # After hours 지정가
            })
            
        self.state["orders"]["sell"] = orders
        logger.info(f"매도 주문 생성 완료: {len(orders)}건")
        
    def _execute_orders(self):
        """주문 실행 (텔레그램 승인 시스템 포함)"""
        logger.info("📋 주문 실행 시작")
        
        # 모든 주문을 하나의 리스트로 합치기
        all_orders = []
        
        # 매수 주문 추가
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
            
        # 매도 주문 추가
        for order in self.state["orders"]["sell"]:
            order_info = {
                "action": "SELL",
                "symbol": self.symbol,
                "quantity": order["quantity"],
                "price": order["price"],
                "order_type": order["order_type"],
                "original_order": order
            }
            all_orders.append(order_info)
        
        if not all_orders:
            logger.info("실행할 주문이 없습니다.")
            return
            
        # EventBus를 통한 주문 승인 요청
        if self.event_bus:
            logger.info(f"🔐 {len(all_orders)}건의 주문에 대한 승인 요청 (EventBus)")
            callback_id = str(uuid.uuid4())
            self.pending_approvals[callback_id] = all_orders
            
            self.event_bus.dispatch(Event(
                type=EventType.ORDER_APPROVAL_REQUEST.value,
                source="infinite_buying_strategy",
                action="request_approval",
                data={
                    "orders": all_orders,
                    "callback_id": callback_id,
                    "timeout": 300
                }
            ))
        else:
            # 기존 방식 (호환성)
            logger.info(f"🔐 {len(all_orders)}건의 주문에 대한 승인 요청 (기존 방식)")
            self.telegram.request_order_approval(all_orders, self._execute_approved_orders)
        
    def _execute_approved_orders(self, approved: bool, orders: list):
        """승인된 주문 실행"""
        if not approved:
            logger.info("❌ 주문이 거부되었습니다.")
            self.telegram.send_message("❌ 주문이 거부되어 실행이 취소되었습니다.")
            return
            
        logger.info("✅ 주문이 승인되었습니다. 실행을 시작합니다.")
        self.telegram.send_message("✅ 주문이 승인되었습니다. 실행을 시작합니다.")
        
        executed_orders = {"buy": [], "sell": []}
        order_types_executed = set()
        
        # 승인된 주문들 실행
        for order_info in orders:
            original_order = order_info["original_order"]
            action = order_info["action"]
            
            try:
                result = self.client.create_oversea_order(
                    symbol=self.symbol,
                    order_type="buy" if action == "BUY" else "sell",
                    price=original_order["price"],
                    quantity=original_order["quantity"],
                    execution_type=original_order["order_type"]
                )
                
                if result.get("rt_cd") == "0":
                    if action == "BUY":
                        executed_orders["buy"].append(original_order)
                    else:
                        executed_orders["sell"].append(original_order)
                    order_types_executed.add(original_order["order_type"])
                    self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=True)
                else:
                    self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=False)
                    logger.error(f"{action} 주문 실패: {result.get('msg1')}")
                
            except Exception as e:
                self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=False)
                logger.error(f"{action} 주문 실패 상세: {str(e)}")
                
        # 실행 완료 요약 알림
        self._notify_orders_executed(executed_orders)
        
        # 주문 타입별 체결 확인 전략 적용
        if executed_orders["buy"] or executed_orders["sell"]:
            self._schedule_execution_checks(order_types_executed)
    
    def _execute_approved_orders_eventbus(self, orders: list):
        """EventBus 방식 승인된 주문 실행"""
        logger.info("✅ 주문이 승인되었습니다. 실행을 시작합니다.")
        if self.telegram:
            self.telegram.send_message("✅ 주문이 승인되었습니다. 실행을 시작합니다.")
        
        executed_orders = {"buy": [], "sell": []}
        order_types_executed = set()
        
        # 승인된 주문들 실행
        for order_info in orders:
            original_order = order_info["original_order"]
            action = order_info["action"]
            
            try:
                result = self.client.create_oversea_order(
                    symbol=self.symbol,
                    order_type="buy" if action == "BUY" else "sell",
                    price=original_order["price"],
                    quantity=original_order["quantity"],
                    execution_type=original_order["order_type"]
                )
                
                if result.get("rt_cd") == "0":
                    if action == "BUY":
                        executed_orders["buy"].append(original_order)
                    else:
                        executed_orders["sell"].append(original_order)
                    order_types_executed.add(original_order["order_type"])
                    self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=True)
                else:
                    self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=False)
                    logger.error(f"{action} 주문 실패: {result.get('msg1')}")
                
            except Exception as e:
                self._notify_trade_alert("매수" if action == "BUY" else "매도", original_order, success=False)
                logger.error(f"{action} 주문 실패 상세: {str(e)}")
                
        # 실행 완료 요약 알림
        self._notify_orders_executed(executed_orders)
        
        # 주문 타입별 체결 확인 전략 적용
        if executed_orders["buy"] or executed_orders["sell"]:
            self._schedule_execution_checks(order_types_executed)
            
    def _schedule_execution_checks(self, order_types: set):
        """주문 타입별 체결 확인 스케줄링"""
        logger.info(f"📅 주문 타입별 체결 확인 스케줄 설정: {', '.join(order_types)}")
        
        immediate_check_needed = False
        delayed_check_needed = False
        
        for order_type in order_types:
            schedule = self._get_order_execution_schedule(order_type)
            
            if schedule["immediate_check"]:
                immediate_check_needed = True
                logger.info(f"⚡ {order_type} 주문 - 즉시 체결 확인 예정")
                
            elif schedule.get("check_after_seconds"):
                delayed_check_needed = True
                check_after = schedule["check_after_seconds"]
                logger.info(f"⏳ {order_type} 주문 - {check_after}초 후 체결 확인 예정")
                
            elif schedule.get("check_at_times"):
                check_times = ", ".join(schedule["check_at_times"])
                logger.info(f"🕐 {order_type} 주문 - 지정 시간({check_times}) 체결 확인 예정")
        
        # 즉시 확인이 필요한 주문이 있으면 10초 후 체결 확인
        if immediate_check_needed:
            logger.info("⏳ 즉시 체결 확인이 필요한 주문을 위해 10초 대기...")
            import time
            time.sleep(10)
            logger.info("🔍 즉시 체결 확인 주문 상태 체크")
            self._check_order_execution()
            
        # 지연 확인이 필요한 주문이 있으면 최소 대기 시간 적용
        elif delayed_check_needed:
            min_wait_time = min(
                self._get_order_execution_schedule(ot).get("check_after_seconds", 60)
                for ot in order_types
                if self._get_order_execution_schedule(ot).get("check_after_seconds")
            )
            logger.info(f"⏳ 지연 체결 확인을 위해 {min_wait_time}초 대기...")
            import time
            time.sleep(min_wait_time)
            logger.info("🔍 지연 체결 확인 주문 상태 체크")
            self._check_order_execution()
            
        else:
            # LOC 주문 등 특정 시간에만 체결되는 주문들
            logger.info("📅 지정 시간 체결 주문 - 다음 정기 체크에서 확인")
            
        # 항상 상태 저장
        self.save_state()
        
    def _cancel_all_orders(self):
        """모든 미체결 주문 취소"""
        try:
            # 미체결 주문 조회
            open_orders = self.client.get_oversea_open_orders()
            
            for order in open_orders:
                if order["symbol"] == self.symbol:
                    self.client.cancel_oversea_order(order["order_id"])
                    logger.info(f"주문 취소: {order['order_id']}")
                    
        except Exception as e:
            logger.error(f"주문 취소 실패: {str(e)}")
            
    def _check_cycle_end(self):
        """사이클 종료 체크"""
        # 포지션 업데이트
        self._update_position()
        
        # 잔량이 0이면 사이클 종료
        if self.position["quantity"] == 0:
            logger.info("💰 전량 매도 완료 감지 - 사이클 종료 처리")
            self._end_cycle()
        else:
            logger.debug(f"📊 현재 포지션: {self.position['quantity']}주 - 사이클 계속")
            
    def _is_pre_market_prepare_time(self, current_time: datetime) -> bool:
        """프리마켓 준비 시간 체크 (프리마켓 시작 5분전)
        
        Args:
            current_time: 현재 시간 (한국시간)
            
        Returns:
            bool: 프리마켓 준비 시간인지 여부
        """
        # 미국 동부시간으로 변환
        korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
        us_time = korea_time.astimezone(self.eastern_tz)
        
        # 프리마켓 시작은 04:00 EST, 5분전은 03:55 EST
        target_time = us_time.replace(hour=3, minute=55, second=0, microsecond=0)
        return us_time >= target_time and us_time < target_time + timedelta(minutes=1)
        
    def _is_pre_market_execution_time(self, current_time: datetime) -> bool:
        """프리마켓 주문 실행 시간 체크 (프리마켓 시작 1분후)
        
        Args:
            current_time: 현재 시간 (한국시간)
            
        Returns:
            bool: 주문 실행 시간인지 여부
        """
        # 미국 동부시간으로 변환
        korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
        us_time = korea_time.astimezone(self.eastern_tz)
        
        # 프리마켓 시작 1분후는 04:01 EST
        target_time = us_time.replace(hour=4, minute=1, second=0, microsecond=0)
        return us_time >= target_time and us_time < target_time + timedelta(minutes=1)
                
    def _is_after_market_end_time(self, current_time: datetime) -> bool:
        """애프터마켓 종료 시간 체크
        
        Args:
            current_time: 현재 시간 (한국시간)
            
        Returns:
            bool: 애프터마켓 종료 시간인지 여부
        """
        # 미국 동부시간으로 변환
        korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
        us_time = korea_time.astimezone(self.eastern_tz)
        
        # 애프터마켓 종료는 20:00 EST
        target_time = us_time.replace(hour=20, minute=0, second=0, microsecond=0)
        return us_time >= target_time and us_time < target_time + timedelta(minutes=1)
        
    def get_status(self) -> Dict:
        """전략 상태 조회"""
        self._update_position()
        
        # 현재 수익률 계산
        profit_ratio = 0
        if self.position["avg_price"] > 0:
            profit_ratio = ((self.position["current_price"] - self.position["avg_price"]) / 
                           self.position["avg_price"]) * 100
                           
        return {
            "active": self.state["active"],
            "cycle_active": self.state["cycle_active"],
            "symbol": self.symbol,
            "position": self.position,
            "params": self.params,
            "calculated_params": self.calculated_params,
            "profit_ratio": profit_ratio,
            "orders": self.state["orders"]
        } 
    def _is_time_passed(self, current_time: datetime, target_hour: int, target_minute: int) -> bool:
        """지정된 시간이 지났는지 확인
        
        Args:
            current_time: 현재 시간
            target_hour: 목표 시간 (시)
            target_minute: 목표 시간 (분)
            
        Returns:
            bool: 해당 시간이 지났는지 여부
        """
        target_time = current_time.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        return current_time >= target_time
        
    # ==============================================
    # 알림 및 로깅 헬퍼 메서드들
    # ==============================================
    
    def _log_and_notify(self, log_message: str, telegram_message: str = None, log_level: str = "info"):
        """로그와 텔레그램 알림을 함께 처리
        
        Args:
            log_message: 로그 메시지
            telegram_message: 텔레그램 메시지 (None이면 텔레그램 전송 안함)
            log_level: 로그 레벨 (info, warning, error)
        """
        # 로그 출력
        if log_level == "info":
            logger.info(log_message)
        elif log_level == "warning":
            logger.warning(log_message)
        elif log_level == "error":
            logger.error(log_message)
            
        # 텔레그램 알림 (에러가 아니고 메시지가 제공된 경우에만)
        if log_level != "error" and telegram_message is not None:
            self.telegram.send_message(telegram_message)
            
    def _notify_cycle_start(self):
        """새 사이클 시작 알림"""
        cycle_start_time = datetime.now()
        
        # 로그 메시지
        log_msg = f"🎯 {self.symbol} 새로운 사이클 시작!"
        logger.info(log_msg)
        logger.info(f"사이클 시작 시간: {cycle_start_time}")
        logger.info(f"전략 파라메터:")
        logger.info(f"  - 총투자금: {self.params['total_investment']:,}원")
        logger.info(f"  - 분할수: {self.params['division_count']}회")
        logger.info(f"  - 최대익절비율: {self.params['max_profit_rate']}%")
        logger.info(f"  - 최소익절비율: {self.params['min_profit_rate']}%")
        logger.info(f"  - Star보정비율: {self.params['star_adjustment_rate']}%")
        
        # 텔레그램 메시지
        mode_indicator = " 🧪(모의투자)" if self.client.is_virtual else ""
        message = f"🎯 <b>{self.symbol} 새 사이클 시작!{mode_indicator}</b>\n\n"
        message += f"📅 시작일: {cycle_start_time.strftime('%Y-%m-%d %H:%M')}\n"
        message += f"💰 총투자금: {self.params['total_investment']:,}원\n"
        message += f"📊 분할수: {self.params['division_count']}회\n"
        message += f"📈 최대익절: {self.params['max_profit_rate']}%\n"
        message += f"📉 최소익절: {self.params['min_profit_rate']}%\n"
        message += f"⭐ Star보정: {self.params['star_adjustment_rate']}%\n\n"
        
        if self.position['quantity'] > 0:
            message += f"🔹 현재 포지션: {self.position['quantity']}주\n"
            message += f"🔹 평단가: ${self.position['avg_price']:.2f}\n"
            message += f"🔹 현재가: ${self.position['current_price']:.2f}\n"
        else:
            message += "🔹 포지션 없음 (신규 시작)\n"
            
        self.telegram.send_message(message)
        
    def _notify_cycle_end(self):
        """사이클 종료 알림"""
        cycle_end_time = datetime.now()
        
        # 수익률 계산
        profit_ratio = 0.0
        if self.position['avg_price'] > 0 and self.position['current_price'] > 0:
            profit_ratio = ((self.position['current_price'] - self.position['avg_price']) / self.position['avg_price']) * 100
            
        # 로그 메시지
        log_msg = f"🏁 {self.symbol} 사이클 종료!"
        logger.info(log_msg)
        logger.info(f"사이클 종료 시간: {cycle_end_time}")
        logger.info(f"최종 수익률: {profit_ratio:.2f}%")
        
        # 텔레그램 메시지
        message = f"🏁 <b>{self.symbol} 사이클 종료!</b>\n\n"
        message += f"📅 종료일: {cycle_end_time.strftime('%Y-%m-%d %H:%M')}\n"
        
        if self.state.get("cycle_start_date"):
            start_date = datetime.fromisoformat(self.state["cycle_start_date"])
            duration = (cycle_end_time.date() - start_date).days
            message += f"⏱️ 진행일수: {duration}일\n"
            
        message += f"📊 최종 수익률: {profit_ratio:.2f}%\n"
        message += f"💰 매도 완료 - 다음 사이클 대기\n"
        
        self.telegram.send_message(message)
        
    def _notify_strategy_restart(self):
        """전략 재시작 알림"""
        log_msg = f"기존 포지션 발견 - 사이클 재개: {self.position['quantity']}주"
        logger.info(log_msg)
        
        message = f"🔄 <b>{self.symbol} 전략 재시작</b>\n\n"
        message += f"📊 기존 포지션: {self.position['quantity']}주\n"
        message += f"💰 평단가: ${self.position['avg_price']:.2f}\n"
        message += f"📈 현재가: ${self.position['current_price']:.2f}\n"
        
        if self.position['avg_price'] > 0 and self.position['current_price'] > 0:
            profit_ratio = ((self.position['current_price'] - self.position['avg_price']) / self.position['avg_price']) * 100
            message += f"📊 현재 수익률: {profit_ratio:.2f}%\n"
            
        self.telegram.send_message(message)
        
    def _notify_strategy_stop(self):
        """전략 종료 알림"""
        log_msg = f"🛑 {self.symbol} 무한매수 전략 종료"
        logger.info(log_msg)
        
        message = f"🛑 <b>{self.symbol} 전략 종료</b>\n\n"
        message += f"📅 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        if self.position['quantity'] > 0:
            message += f"📊 보유 포지션: {self.position['quantity']}주\n"
            message += f"💰 평단가: ${self.position['avg_price']:.2f}\n"
            message += f"📈 현재가: ${self.position['current_price']:.2f}\n"
        else:
            message += "📊 포지션 없음\n"
            
        message += "⚠️ 전략이 중지되었습니다."
        
        self.telegram.send_message(message)
        
    def _notify_orders_executed(self, executed_orders: dict):
        """주문 실행 완료 알림"""
        if not (executed_orders["buy"] or executed_orders["sell"]):
            return
            
        logger.info("📋 주문 실행 완료 요약 전송")
        
        message = f"📋 <b>{self.symbol} 주문 실행 완료</b>\n\n"
        
        if executed_orders["buy"]:
            message += f"🟢 매수 주문: {len(executed_orders['buy'])}건\n"
            total_buy_amount = sum(order["price"] * order["quantity"] for order in executed_orders["buy"])
            message += f"💰 총 매수금액: ${total_buy_amount:,.2f}\n"
            
        if executed_orders["sell"]:
            message += f"🔴 매도 주문: {len(executed_orders['sell'])}건\n"
            total_sell_amount = sum(order["price"] * order["quantity"] for order in executed_orders["sell"])
            message += f"💰 총 매도금액: ${total_sell_amount:,.2f}\n"
            
        self.telegram.send_message(message)
        
    def _notify_trade_alert(self, action: str, order: dict, success: bool = True):
        """개별 거래 알림"""
        if success:
            log_msg = f"✅ {order['type']} {action} 주문 성공"
            logger.info(log_msg)
            
            # 텔레그램 개별 거래 알림
            self.telegram.send_trade_alert(
                action=action.upper(),
                symbol=self.symbol,
                quantity=order["quantity"],
                price=order["price"]
            )
        else:
            log_msg = f"❌ {order['type']} {action} 주문 실패"
            logger.error(log_msg)
            
    # ==============================================
    # 주문 체결 확인 메서드들  
    # ==============================================
    
    def _get_order_execution_schedule(self, order_type: str) -> dict:
        """주문 타입별 체결 확인 스케줄 반환
        
        Args:
            order_type: 주문 타입 (LOC, AFTER, LIMIT, MARKET)
            
        Returns:
            dict: 체결 확인 전략 정보
        """
        schedules = {
            "LOC": {
                "immediate_check": False,  # 즉시 확인 불필요
                "check_after_seconds": None,  # 특정 시간 후 확인 불필요
                "check_at_us_times": ["16:05", "16:10"],  # 미국 장 마감 후 확인 (동부시간)
                "max_wait_hours": 1,  # 최대 1시간 대기
                "description": "장 마감 시 체결"
            },
            "AFTER": {
                "immediate_check": False,
                "check_after_seconds": 60,  # 1분 후 확인
                "check_at_times": [],  # 특정 시간 없음
                "max_wait_hours": 4,  # 애프터마켓 시간 고려
                "description": "애프터마켓 지정가"
            },
            "LIMIT": {
                "immediate_check": True,  # 즉시 확인
                "check_after_seconds": 30,  # 30초 후 확인
                "check_at_times": [],
                "max_wait_hours": 24,  # 하루 종일 대기 가능
                "description": "지정가 주문"
            },
            "MARKET": {
                "immediate_check": True,
                "check_after_seconds": 10,  # 10초 후 확인
                "check_at_times": [],
                "max_wait_hours": 0.1,  # 6분만 대기
                "description": "시장가 주문 (즉시 체결)"
            }
        }
        
        return schedules.get(order_type, schedules["LIMIT"])  # 기본값: LIMIT
    
    def _should_check_order_now(self, order: dict, current_time: datetime) -> bool:
        """현재 시점에 주문 체결을 확인해야 하는지 판단
        
        Args:
            order: 주문 정보
            current_time: 현재 시간
            
        Returns:
            bool: 체결 확인 필요 여부
        """
        order_type = order.get("order_type", "LIMIT")
        schedule = self._get_order_execution_schedule(order_type)
        
        # 주문 시간 파싱
        order_time_str = order.get("order_time", "")
        if not order_time_str:
            return True  # 주문 시간 불명시 즉시 확인
            
        try:
            # HHMMSS 형식으로 주문 시간 파싱
            if len(order_time_str) == 6:
                order_hour = int(order_time_str[:2])
                order_minute = int(order_time_str[2:4])
                order_second = int(order_time_str[4:6])
                
                order_time = current_time.replace(
                    hour=order_hour, 
                    minute=order_minute, 
                    second=order_second, 
                    microsecond=0
                )
            else:
                order_time = current_time  # 파싱 실패시 현재 시간 사용
                
        except Exception:
            order_time = current_time
        
        time_elapsed = current_time - order_time
        
        # LOC 주문 특별 처리
        if order_type == "LOC":
            # 미국 동부시간으로 변환
            korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
            us_time = korea_time.astimezone(self.eastern_tz)
            us_hour_minute = us_time.strftime("%H:%M")
            
            # 장 마감 후 확인 시간 (동부시간 16:05 이후)
            for check_time in schedule.get("check_at_us_times", []):
                if us_hour_minute >= check_time:
                    return True
                    
            # 아직 체결 시간이 안됨
            return False
            
        # AFTER 주문 처리 (애프터마켓)
        elif order_type == "AFTER":
            # 미국 동부시간으로 변환
            korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
            us_time = korea_time.astimezone(self.eastern_tz)
            
            # 애프터마켓 시간 (동부시간 16:00-20:00) 동안만 체크
            us_hour = us_time.hour
            if 16 <= us_hour <= 20:
                return time_elapsed.total_seconds() >= schedule.get("check_after_seconds", 60)
            return False
            
        # MARKET, LIMIT 주문 처리
        else:
            # 즉시 확인 필요한 경우
            if schedule["immediate_check"] and time_elapsed.total_seconds() >= 5:
                return True
                
            # 지정된 시간 후 확인
            if schedule.get("check_after_seconds"):
                return time_elapsed.total_seconds() >= schedule["check_after_seconds"]
                
        return False
        
    def _is_order_expired(self, order: dict, current_time: datetime) -> bool:
        """주문이 만료되었는지 확인
        
        Args:
            order: 주문 정보
            current_time: 현재 시간
            
        Returns:
            bool: 만료 여부
        """
        order_type = order.get("order_type", "LIMIT")
        schedule = self._get_order_execution_schedule(order_type)
        
        # 주문 시간 파싱
        order_time_str = order.get("order_time", "")
        if not order_time_str:
            return False
            
        try:
            if len(order_time_str) == 6:
                order_hour = int(order_time_str[:2])
                order_minute = int(order_time_str[2:4])
                order_second = int(order_time_str[4:6])
                
                order_time = current_time.replace(
                    hour=order_hour, 
                    minute=order_minute, 
                    second=order_second, 
                    microsecond=0
                )
            else:
                return False
                
        except Exception:
            return False
        
        time_elapsed = current_time - order_time
        max_wait_seconds = schedule["max_wait_hours"] * 3600
        
        return time_elapsed.total_seconds() > max_wait_seconds
    
    def _check_order_execution(self):
        """주문 체결 확인 (주문 타입별 최적화)"""
        try:
            # 당일 주문내역 조회
            orders_result = self.client.get_oversea_orders()
            
            if orders_result.get("rt_cd") != "0":
                logger.error("주문내역 조회 실패")
                return
                
            orders = orders_result.get("output1", [])
            
            # 오늘 날짜의 해당 종목 주문만 필터링
            today = datetime.now().strftime("%Y%m%d")
            symbol_orders = [
                order for order in orders 
                if order.get("pdno") == self.symbol and order.get("ord_dt") == today
            ]
            
            if not symbol_orders:
                logger.debug(f"📋 오늘 {self.symbol} 주문내역 없음")
                return
                
            current_time = datetime.now()
            
            # 체결/미체결 상태별로 처리
            executed_orders = []
            pending_orders = []
            orders_to_check = []  # 현재 확인이 필요한 주문들
            
            for order in symbol_orders:
                ccld_yn = order.get("ccld_yn", "N")  # 체결여부 Y/N
                ccld_qty = int(order.get("ccld_qty", "0"))  # 체결수량
                ord_qty = int(order.get("ord_qty", "0"))  # 주문수량
                
                # 주문 타입 추정 (API 응답에서 확인)
                ord_dvsn = order.get("ord_dvsn", "00")
                order_type = "LOC" if ord_dvsn == "34" else "AFTER" if ord_dvsn == "32" else "LIMIT"
                
                # 주문 정보 구성
                order_info = {
                    "order_no": order.get("odno"),
                    "symbol": order.get("pdno"),
                    "side": "BUY" if order.get("sll_buy_dvsn_cd") == "02" else "SELL",
                    "quantity": ord_qty,
                    "executed_qty": ccld_qty,
                    "price": float(order.get("ord_unpr", "0")),
                    "executed_price": float(order.get("ccld_unpr", "0")) if ccld_qty > 0 else 0,
                    "order_time": order.get("ord_tmd"),
                    "order_type": order_type
                }
                
                if ccld_yn == "Y" and ccld_qty > 0:
                    # 체결된 주문
                    executed_orders.append(order_info)
                elif ccld_qty < ord_qty:
                    # 미체결 또는 부분체결
                    order_info["quantity"] = ord_qty - ccld_qty  # 미체결 수량만
                    pending_orders.append(order_info)
                    
                    # 현재 시점에 체결 확인이 필요한지 판단
                    if self._should_check_order_now(order_info, current_time):
                        orders_to_check.append(order_info)
                        
            # 체결된 주문 알림 (새로 체결된 것만)
            for executed_order in executed_orders:
                self._notify_order_executed(executed_order)
                
            # 확인이 필요한 미체결 주문 처리
            if orders_to_check:
                logger.info(f"🔍 체결 확인 대상: {len(orders_to_check)}건")
                for order in orders_to_check:
                    self._log_order_check_status(order, current_time)
                    
            # 만료된 미체결 주문 관리
            self._manage_pending_orders_by_type(pending_orders, current_time)
                
            logger.info(f"📊 주문 체결 확인 완료 - 체결: {len(executed_orders)}건, 미체결: {len(pending_orders)}건, 확인대상: {len(orders_to_check)}건")
            
        except Exception as e:
            logger.error(f"주문 체결 확인 중 오류: {str(e)}")
            
    def _log_order_check_status(self, order: dict, current_time: datetime):
        """주문 체결 확인 상태 로깅"""
        order_type = order.get("order_type", "UNKNOWN")
        schedule = self._get_order_execution_schedule(order_type)
        
        logger.info(f"🔍 {order_type} 주문 체결 확인")
        logger.info(f"  - 종목: {order['symbol']}")
        logger.info(f"  - 구분: {order['side']}")
        logger.info(f"  - 미체결수량: {order['quantity']}주")
        logger.info(f"  - 가격: ${order['price']:.2f}")
        logger.info(f"  - 체결전략: {schedule['description']}")
        
        # LOC 주문 특별 안내
        if order_type == "LOC":
            logger.info(f"  ⏰ LOC 주문은 미국 장 마감(동부시간 16:00) 시 체결됩니다")
        elif order_type == "AFTER":
            logger.info(f"  ⏰ AFTER 주문은 애프터마켓(동부시간 16:00-20:00) 동안 체결 가능합니다")
        
    def _notify_order_executed(self, order: dict):
        """체결된 주문 알림"""
        side_emoji = "🟢" if order["side"] == "BUY" else "🔴"
        side_text = "매수" if order["side"] == "BUY" else "매도"
        
        # 로그 메시지
        log_msg = f"✅ {side_text} 체결 완료"
        logger.info(log_msg)
        logger.info(f"  - 종목: {order['symbol']}")
        logger.info(f"  - 수량: {order['quantity']}주")
        logger.info(f"  - 가격: ${order['price']:.2f}")
        logger.info(f"  - 체결시간: {order['executed_time']}")
        
        # 텔레그램 메시지
        message = f"{side_emoji} <b>{self.symbol} {side_text} 체결!</b>\n\n"
        message += f"📊 체결수량: {order['quantity']}주\n"
        message += f"💰 체결가격: ${order['price']:.2f}\n"
        message += f"💵 체결금액: ${order['quantity'] * order['price']:,.2f}\n"
        message += f"⏰ 체결시간: {order['executed_time']}\n"
        message += f"📝 주문번호: {order['order_no']}"
        
        self.telegram.send_message(message)
        
        # 포지션 업데이트 (체결 후 포지션 변경 반영)
        self._update_position()
        
    def _manage_pending_orders_by_type(self, pending_orders: list, current_time: datetime):
        """타입별 미체결 주문 관리"""
        if not pending_orders:
            return
            
        logger.info(f"📋 미체결 주문 {len(pending_orders)}건 확인 - 타입별 관리")
        
        for order in pending_orders:
            try:
                order_type = order.get("order_type", "LIMIT")
                
                # 주문 만료 확인
                if self._is_order_expired(order, current_time):
                    logger.warning(f"⏰ {order_type} 주문 만료됨 - 취소 처리")
                    self._cancel_expired_order(order, "만료")
                    continue
                
                # 주문 타입별 특별 처리
                if order_type == "LOC":
                    self._manage_loc_order(order, current_time)
                elif order_type == "AFTER":
                    self._manage_after_order(order, current_time)
                elif order_type == "MARKET":
                    # 시장가 주문이 미체결이면 문제 상황
                    logger.warning(f"🚨 시장가 주문 미체결 감지 - 즉시 확인 필요")
                    self._notify_market_order_issue(order)
                else:  # LIMIT
                    self._manage_limit_order(order, current_time)
                    
            except Exception as e:
                logger.warning(f"미체결 주문 관리 중 오류: {str(e)}")
                
    def _manage_loc_order(self, order: dict, current_time: datetime):
        """LOC 주문 관리"""
        # 미국 동부시간으로 변환
        korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
        us_time = korea_time.astimezone(self.eastern_tz)
        us_hour = us_time.hour
        
        # 미국 장 마감 시간 전이면 대기
        if us_hour < 16:  # 동부시간 16:00 이전
            logger.debug(f"📅 LOC 주문 대기 중 - 장 마감 후 체결 예정 (주문번호: {order['order_no']})")
        elif 16 <= us_hour <= 17:  # 체결 시간대
            logger.info(f"⏰ LOC 주문 체결 시간대 - 체결 상태 모니터링 중")
        else:  # 17:00 이후에도 미체결이면 문제
            logger.warning(f"🚨 LOC 주문 장시간 미체결 - 수동 확인 필요")
            self._notify_loc_order_issue(order)
            
    def _manage_after_order(self, order: dict, current_time: datetime):
        """AFTER(애프터마켓) 주문 관리"""
        # 미국 동부시간으로 변환
        korea_time = self.korea_tz.localize(current_time) if current_time.tzinfo is None else current_time
        us_time = korea_time.astimezone(self.eastern_tz)
        us_hour = us_time.hour
        
        # 애프터마켓 시간 확인
        if 16 <= us_hour <= 20:  # 애프터마켓 시간 (동부시간)
            logger.debug(f"🌙 AFTER 주문 애프터마켓 시간 중 - 체결 대기")
        else:
            # 애프터마켓 시간 외에는 체결 불가
            logger.info(f"⏰ AFTER 주문 애프터마켓 시간 외 - 다음 세션 대기")
            
    def _manage_limit_order(self, order: dict, current_time: datetime):
        """지정가 주문 관리"""
        # 지정가는 조건 충족시 언제든 체결 가능
        logger.debug(f"📊 LIMIT 주문 조건 대기 중 - 가격: ${order['price']:.2f}")
        
    def _cancel_expired_order(self, order: dict, reason: str):
        """만료된 주문 취소"""
        try:
            result = self.client.cancel_order(
                order_number=order["order_no"],
                symbol=order["symbol"]
            )
            
            if result.get("rt_cd") == "0":
                logger.info(f"🚫 만료된 {order['order_type']} 주문 취소: {order['order_no']}")
                
                # 텔레그램 알림
                order_type_name = self._get_order_execution_schedule(order['order_type'])['description']
                message = f"🚫 <b>주문 자동 취소</b>\n\n"
                message += f"📊 종목: {order['symbol']}\n"
                message += f"📊 구분: {order['side']}\n"
                message += f"📊 타입: {order_type_name}\n"
                message += f"📊 수량: {order['quantity']}주\n"
                message += f"💰 가격: ${order['price']:.2f}\n"
                message += f"📝 주문번호: {order['order_no']}\n"
                message += f"⚠️ 사유: {reason}"
                
                self.telegram.send_message(message)
            else:
                logger.warning(f"주문 취소 실패: {result.get('msg1')}")
                
        except Exception as e:
            logger.error(f"주문 취소 중 오류: {str(e)}")
            
    def _notify_loc_order_issue(self, order: dict):
        """LOC 주문 문제 알림"""
        message = f"🚨 <b>LOC 주문 확인 필요</b>\n\n"
        message += f"📊 종목: {order['symbol']}\n"
        message += f"📊 수량: {order['quantity']}주\n"
        message += f"💰 가격: ${order['price']:.2f}\n"
        message += f"📝 주문번호: {order['order_no']}\n"
        message += f"⚠️ 장 마감 후에도 미체결 상태입니다."
        
        self.telegram.send_message(message)
        
    def _notify_market_order_issue(self, order: dict):
        """시장가 주문 문제 알림"""
        message = f"🚨 <b>시장가 주문 미체결</b>\n\n"
        message += f"📊 종목: {order['symbol']}\n"
        message += f"📊 수량: {order['quantity']}주\n"
        message += f"📝 주문번호: {order['order_no']}\n"
        message += f"⚠️ 시장가 주문이 체결되지 않았습니다. 즉시 확인하세요!"
        
        self.telegram.send_message(message) 

    def get_trading_history_table(self, days: int = 30) -> pd.DataFrame:
        """거래 내역을 날짜별로 집계한 테이블 반환
        
        Args:
            days: 조회할 일수 (기본 30일)
            
        Returns:
            pd.DataFrame: 날짜별 거래 내역 테이블
        """
        # 테스트 모드에서는 cycle_start_date를 무시하고 days 기준으로 조회
        if self.trade_history.test_mode:
            cycle_start_date = None
            logger.info(f"🧪 테스트 모드: cycle_start_date 무시, days={days} 기준으로 조회")
        else:
            cycle_start_date = self.state.get("cycle_start_date")
            logger.info(f"🔴 실제 모드: cycle_start_date={cycle_start_date} 사용")
        
        return self.trade_history.get_trading_history_table(days, cycle_start_date)
    
 
