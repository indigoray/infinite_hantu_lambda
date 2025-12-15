import logging
import asyncio
from src.utils.event_bus import EventBus, Event, EventType
from src.trading.stock_subscriber import StockSubscriber
from src.trading.strategy_manager import StrategyManager
from src.strategy.infinite_buying import InfiniteBuyingStrategy
from src.config import Config

logger = logging.getLogger(__name__)

class TradingEngine:
    """트레이딩 엔진
    
    전략 관리자와 시세 구독자를 조율하여 전체 트레이딩 시스템을 운영
    """
    
    def __init__(self, kis_client, config: Config, event_bus: EventBus):
        self.kis_client = kis_client
        self.config = config
        self.event_bus = event_bus
        self.stock_subscriber = StockSubscriber(kis_client, event_bus)
        self.strategy_manager = StrategyManager(kis_client, config, event_bus)
        
    def initialize(self):
        """트레이딩 엔진 초기화"""
        # 기본 전략의 심볼 구독 설정
        default_strategy = self.strategy_manager.get_strategy("default")
        if default_strategy:
            self.stock_subscriber.subscribe(default_strategy.symbol)
            logger.info("트레이딩 엔진 초기화 완료")
            return True
        else:
            logger.error("기본 전략 초기화 실패")
            return False
            
    def start(self):
        """트레이딩 엔진 시작"""
        # 실시간 시세 구독 시작
        self.stock_subscriber.start()
        logger.info("트레이딩 엔진 시작")
        
        # 시작 이벤트 발행
        self.event_bus.dispatch(Event(
            type=EventType.TRADE_UPDATE,
            source="trading_engine",
            action="engine_start",
            data={"message": "🚀 트레이딩 엔진이 시작되었습니다."}
        ))
        