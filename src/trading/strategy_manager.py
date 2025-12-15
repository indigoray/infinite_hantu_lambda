import logging
from typing import Dict, Optional
from src.strategy.infinite_buying import InfiniteBuyingStrategy
from src.utils.event_bus import EventBus, Event, EventType
from src.config import Config
from src.api.kis_client import KISClient
from rx import operators as ops

logger = logging.getLogger(__name__)

class StrategyManager:
    """전략 관리자
    
    여러 전략 인스턴스들을 관리하고 이벤트를 처리
    전략의 생명주기(초기화, 시작, 중지, 상태저장) 관리
    """
    
    def __init__(self, kis_client: KISClient, config: Config, event_bus: EventBus):
        self.kis_client = kis_client
        self.config = config
        self.event_bus = event_bus
        self.strategies: Dict[str, InfiniteBuyingStrategy] = {}
        self._setup_event_handlers()
        self._initialize_default_strategy()
        
    def _setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        # UI 액션 이벤트 구독
        self.event_bus.subscribe(
            EventType.UI_ACTION,
            lambda event: self._handle_ui_action(event)
        )
        
        # 가격 업데이트 이벤트 구독
        self.event_bus.subscribe(
            EventType.PRICE_UPDATE,
            lambda event: self._handle_price_update(event)
        )
        
    def _initialize_default_strategy(self):
        """기본 전략 초기화"""
        strategy = self._create_strategy("default")
        if strategy:
            self.add_strategy("default", strategy)
            
    def _create_strategy(self, strategy_id: str) -> Optional[InfiniteBuyingStrategy]:
        """전략 인스턴스 생성"""
        try:
            strategy = InfiniteBuyingStrategy(self.kis_client, self.config, self.event_bus)
            strategy.load_state()  # 이전 상태 로드
            logger.info(f"전략 생성 성공: {strategy_id}")
            return strategy
        except Exception as e:
            logger.error(f"전략 생성 실패: {strategy_id}, 에러: {str(e)}")
            return None
            
    def add_strategy(self, strategy_id: str, strategy: InfiniteBuyingStrategy):
        """전략 추가"""
        if strategy_id not in self.strategies:
            self.strategies[strategy_id] = strategy
            logger.info(f"전략 추가됨: {strategy_id}")
            
    def remove_strategy(self, strategy_id: str):
        """전략 제거"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.save_state()  # 상태 저장
            del self.strategies[strategy_id]
            logger.info(f"전략 제거됨: {strategy_id}")
            
    def start_strategy(self, strategy_id: str):
        """전략 시작"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.is_active = True
            strategy.save_state()  # 상태 저장
            logger.info(f"전략 시작: {strategy_id}")
            
            # 전략 시작 이벤트 발행
            self.event_bus.dispatch(Event(
                type=EventType.TRADE_UPDATE,
                source="strategy_manager",
                action="strategy_started",
                data={"strategy_id": strategy_id}
            ))
            
    def stop_strategy(self, strategy_id: str):
        """전략 중지"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.is_active = False
            strategy.save_state()  # 상태 저장
            logger.info(f"전략 중지: {strategy_id}")
            
            # 전략 중지 이벤트 발행
            self.event_bus.dispatch(Event(
                type=EventType.TRADE_UPDATE,
                source="strategy_manager",
                action="strategy_stopped",
                data={"strategy_id": strategy_id}
            ))
            
    def get_strategy(self, strategy_id: str) -> Optional[InfiniteBuyingStrategy]:
        """전략 인스턴스 반환"""
        return self.strategies.get(strategy_id)
            
    def _handle_ui_action(self, event: Event):
        """UI 액션 이벤트 처리"""
        if event.action == "start_strategy":
            self.start_strategy("default")
        elif event.action == "stop_strategy":
            self.stop_strategy("default")
            
    def _handle_price_update(self, event: Event):
        """가격 업데이트 이벤트 처리"""
        symbol = event.data["symbol"]
        price = event.data["price"]
        
        # 모든 활성 전략에 가격 업데이트 전달
        for strategy in self.strategies.values():
            if strategy.symbol == symbol and strategy.is_active:
                strategy.on_price_update(price) 