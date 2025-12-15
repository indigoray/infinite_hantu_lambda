from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import logging
from rx.subject import Subject
from rx import operators as ops

logger = logging.getLogger(__name__)

class EventType(Enum):
    UI_ACTION = "UI_ACTION"
    TELEGRAM_COMMAND = "TELEGRAM_COMMAND"
    TRADE_UPDATE = "TRADE_UPDATE"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"
    PRICE_UPDATE = "PRICE_UPDATE"
    ERROR = "ERROR"
    ORDER_APPROVAL_REQUEST = "ORDER_APPROVAL_REQUEST"
    ORDER_APPROVAL_RESPONSE = "ORDER_APPROVAL_RESPONSE"
    
@dataclass
class Event:
    """이벤트 데이터 클래스"""
    type: str
    source: str
    action: str
    data: Optional[Dict[str, Any]] = None

class EventBus:
    """RxPY 기반 이벤트 버스"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subject = Subject()
            logger.info("이벤트 버스 초기화됨")
        return cls._instance
    
    def __init__(self):
        # 싱글톤이므로 __new__에서 초기화된 경우 건너뜀
        pass
    
    def dispatch(self, event: Event):
        """이벤트 발행"""
        logger.debug(f"이벤트 발행: {event}")
        self.subject.on_next(event)
    
    def subscribe(self, event_type: str, handler):
        """이벤트 구독
        
        Args:
            event_type (str): 구독할 이벤트 타입
            handler: 이벤트 처리 함수
        """
        logger.debug(f"이벤트 구독: {event_type}")
        return (
            self.subject
            .pipe(
                ops.filter(lambda event: event.type == event_type)
            )
            .subscribe(
                on_next=handler,
                on_error=lambda e: logger.error(f"이벤트 처리 중 에러 발생: {str(e)}")
            )
        )
    
    def clear(self):
        """모든 구독 해제"""
        self.subject = Subject() 