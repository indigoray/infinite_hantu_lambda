import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import schedule

# StockSubscriber 임포트 추가
from src.trading.stock_subscriber import StockSubscriber

logger = logging.getLogger(__name__)

class TradingEngine:
    """거래 엔진 - 전략 실행 및 관리"""
    
    def __init__(self, event_bus=None, kis_client=None):
        self.event_bus = event_bus
        self.kis_client = kis_client
        self.strategies = {}
        self.running = False
        self._thread = None
        self._lock = threading.Lock()
        
        # StockSubscriber 초기화
        if kis_client:
            self.stock_subscriber = StockSubscriber(kis_client, event_bus)
            logger.info("📊 StockSubscriber 초기화 완료")
        else:
            self.stock_subscriber = None
            logger.warning("⚠️ KIS Client가 없어 StockSubscriber를 초기화할 수 없습니다")
        
    def add_strategy(self, name: str, strategy):
        """전략 추가
        
        Args:
            name: 전략 이름
            strategy: 전략 인스턴스
        """
        with self._lock:
            if name in self.strategies:
                logger.warning(f"전략 {name}이 이미 존재합니다. 덮어씁니다.")
                
            self.strategies[name] = {
                "instance": strategy,
                "active": False,
                "schedule": "1m",  # 기본 1분 주기
                "last_run": None
            }
            
            logger.info(f"전략 추가: {name}")
            
            # 무한매수 전략이 추가되면 자동으로 StockSubscriber에 심볼 등록
            if "infinite_buying" in name.lower() and self.stock_subscriber:
                self._register_strategy_symbols(strategy)
                
    def _register_strategy_symbols(self, strategy):
        """전략의 심볼들을 StockSubscriber에 등록"""
        try:
            # SOXL (무한매수 전략의 기본 심볼)
            strategy_symbol = getattr(strategy, 'symbol', 'SOXL')
            self.stock_subscriber.subscribe(strategy_symbol, market="us")
            
            # 추가 관심 종목들 등록
            additional_symbols = [
                ("SOXL", "us"),     # 반도체 3x ETF (이미 등록되어 있어도 중복 체크함)
                ("005930", "kr"),   # 삼성전자
            ]
            
            for symbol, market in additional_symbols:
                if not self.stock_subscriber.is_symbol_subscribed(symbol):
                    self.stock_subscriber.subscribe(symbol, market=market)
                    
            logger.info(f"📈 전략 심볼 등록 완료: {strategy_symbol}, 삼성전자(005930)")
            
        except Exception as e:
            logger.error(f"전략 심볼 등록 실패: {str(e)}")
            
    def start_strategy(self, name: str):
        """전략 시작
        
        Args:
            name: 전략 이름
        """
        with self._lock:
            if name not in self.strategies:
                logger.error(f"전략 {name}을 찾을 수 없습니다.")
                return False
                
            strategy_info = self.strategies[name]
            strategy_info["active"] = True
            
            # 전략 초기화
            try:
                strategy_info["instance"].init()
                logger.info(f"전략 시작: {name}")
                
                # StockSubscriber도 함께 시작 (처음 전략이 시작될 때만)
                if self.stock_subscriber and not self.stock_subscriber.is_running:
                    self.stock_subscriber.start()
                    logger.info("📊 StockSubscriber 가격 모니터링 시작")
                
                # 이벤트 발행
                if self.event_bus:
                    self.event_bus.publish("strategy_started", {
                        "name": name,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                return True
                
            except Exception as e:
                logger.error(f"전략 시작 실패 {name}: {str(e)}")
                logger.debug(f"전략 시작 실패 상세: {repr(e)}", exc_info=True)
                strategy_info["active"] = False
                return False
                
    def stop_strategy(self, name: str):
        """전략 중지
        
        Args:
            name: 전략 이름
        """
        with self._lock:
            if name not in self.strategies:
                logger.error(f"전략 {name}을 찾을 수 없습니다.")
                return
                
            strategy_info = self.strategies[name]
            if strategy_info["active"]:
                strategy_info["active"] = False
                
                # 전략 종료 처리
                try:
                    strategy_info["instance"].exit()
                    logger.info(f"전략 중지: {name}")
                    
                    # 모든 전략이 중지되면 StockSubscriber도 중지
                    active_strategies = [info for info in self.strategies.values() if info["active"]]
                    if not active_strategies and self.stock_subscriber and self.stock_subscriber.is_running:
                        self.stock_subscriber.stop()
                        logger.info("📊 모든 전략 중지로 StockSubscriber 중지")
                    
                    # 이벤트 발행
                    if self.event_bus:
                        self.event_bus.publish("strategy_stopped", {
                            "name": name,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.error(f"전략 중지 실패 {name}: {str(e)}")
                    
    def start(self):
        """Trading Engine 시작"""
        if self.running:
            logger.warning("Trading Engine이 이미 실행 중입니다.")
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("Trading Engine 시작됨")
        
    def stop(self):
        """Trading Engine 중지"""
        self.running = False
        
        # StockSubscriber 중지
        if self.stock_subscriber:
            self.stock_subscriber.stop()
        
        # 모든 전략 중지
        with self._lock:
            active_strategies = [name for name, info in self.strategies.items() 
                               if info["active"]]
                               
        for name in active_strategies:
            self.stop_strategy(name)
            
        if self._thread:
            self._thread.join(timeout=5)
            
        logger.info("Trading Engine 중지됨")
        
    def _run_loop(self):
        """메인 실행 루프"""
        while self.running:
            try:
                # 활성화된 전략 실행
                with self._lock:
                    active_strategies = [(name, info) for name, info in self.strategies.items() 
                                       if info["active"]]
                    
                for name, strategy_info in active_strategies:
                    self._execute_strategy(name, strategy_info)
                    
                # 스케줄된 작업 실행
                schedule.run_pending()
                
                time.sleep(1)  # 1초 대기
                
            except Exception as e:
                logger.error(f"Trading Engine 루프 오류: {str(e)}")
                
    def _execute_strategy(self, name: str, strategy_info: Dict):
        """전략 실행
        
        Args:
            name: 전략 이름
            strategy_info: 전략 정보
        """
        try:
            # 실행 주기 체크
            if not self._should_run_strategy(strategy_info):
                return
                
            # 전략 실행
            logger.debug(f"전략 실행: {name}")
            strategy_info["instance"].run()
            strategy_info["last_run"] = datetime.now()
            
            # 상태 업데이트 이벤트
            if self.event_bus:
                status = strategy_info["instance"].get_status()
                self.event_bus.publish("strategy_update", {
                    "name": name,
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"전략 실행 오류 {name}: {str(e)}")
            
            # 오류 이벤트 발행
            if self.event_bus:
                self.event_bus.publish("strategy_error", {
                    "name": name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
    def _should_run_strategy(self, strategy_info: Dict) -> bool:
        """전략 실행 여부 확인
        
        Args:
            strategy_info: 전략 정보
            
        Returns:
            bool: 실행 여부
        """
        last_run = strategy_info["last_run"]
        schedule = strategy_info["schedule"]
        
        if last_run is None:
            return True
            
        # 스케줄에 따른 실행 시간 계산
        if schedule == "1m":
            next_run = last_run + timedelta(minutes=1)
        elif schedule == "5m":
            next_run = last_run + timedelta(minutes=5)
        elif schedule == "10m":
            next_run = last_run + timedelta(minutes=10)
        elif schedule == "1h":
            next_run = last_run + timedelta(hours=1)
        else:
            # 기본 1분
            next_run = last_run + timedelta(minutes=1)
            
        return datetime.now() >= next_run
        
    def get_strategy_status(self, name: str) -> Optional[Dict]:
        """전략 상태 조회
        
        Args:
            name: 전략 이름
            
        Returns:
            dict: 전략 상태 정보
        """
        with self._lock:
            if name not in self.strategies:
                return None
                
            strategy_info = self.strategies[name]
            status = strategy_info["instance"].get_status()
            
            return {
                "name": name,
                "active": strategy_info["active"],
                "schedule": strategy_info["schedule"],
                "last_run": strategy_info["last_run"].isoformat() if strategy_info["last_run"] else None,
                "status": status
            }
            
    def get_all_strategies(self) -> List[Dict]:
        """모든 전략 목록 조회
        
        Returns:
            list: 전략 목록
        """
        with self._lock:
            strategies = []
            for name in self.strategies:
                status = self.get_strategy_status(name)
                if status:
                    strategies.append(status)
                    
            return strategies
    
    def get_subscribed_symbols(self) -> Dict:
        """구독 중인 심볼 목록 조회"""
        if self.stock_subscriber:
            return self.stock_subscriber.get_subscribed_symbols()
        return {}
    
    def subscribe_symbol(self, symbol: str, market: str = "us"):
        """심볼 구독 추가"""
        if self.stock_subscriber:
            self.stock_subscriber.subscribe(symbol, market)
            return True
        return False
    
    def unsubscribe_symbol(self, symbol: str):
        """심볼 구독 해제"""
        if self.stock_subscriber:
            self.stock_subscriber.unsubscribe(symbol)
            return True
        return False 