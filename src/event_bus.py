import logging
from typing import Any, Callable, Dict
from rx import create
from rx.subject import Subject

logger = logging.getLogger(__name__)

class EventBus:
    """이벤트 버스 - 컴포넌트 간 통신을 위한 중앙 이벤트 시스템"""
    
    def __init__(self):
        self._subjects: Dict[str, Subject] = {}
        self._subscriptions = {}
        
    def get_subject(self, event_type: str) -> Subject:
        """특정 이벤트 타입의 Subject 반환
        
        Args:
            event_type: 이벤트 타입
            
        Returns:
            Subject: RxPy Subject
        """
        if event_type not in self._subjects:
            self._subjects[event_type] = Subject()
            logger.debug(f"새 이벤트 타입 생성: {event_type}")
            
        return self._subjects[event_type]
        
    def publish(self, event_type: str, data: Any):
        """이벤트 발행
        
        Args:
            event_type: 이벤트 타입
            data: 이벤트 데이터
        """
        subject = self.get_subject(event_type)
        
        logger.debug(f"이벤트 발행: {event_type}")
        subject.on_next({
            "type": event_type,
            "data": data
        })
        
    def subscribe(self, event_type: str, handler: Callable, 
                 subscription_id: str = None) -> str:
        """이벤트 구독
        
        Args:
            event_type: 이벤트 타입
            handler: 이벤트 핸들러 함수
            subscription_id: 구독 ID (옵션)
            
        Returns:
            str: 구독 ID
        """
        subject = self.get_subject(event_type)
        
        # 구독 ID 생성
        if subscription_id is None:
            subscription_id = f"{event_type}_{len(self._subscriptions)}"
            
        # 구독 처리
        subscription = subject.subscribe(
            on_next=lambda event: self._handle_event(handler, event),
            on_error=lambda error: logger.error(f"이벤트 오류 {event_type}: {error}"),
            on_completed=lambda: logger.debug(f"이벤트 완료 {event_type}")
        )
        
        self._subscriptions[subscription_id] = subscription
        logger.debug(f"이벤트 구독: {event_type} (ID: {subscription_id})")
        
        return subscription_id
        
    def unsubscribe(self, subscription_id: str):
        """구독 해제
        
        Args:
            subscription_id: 구독 ID
        """
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id].dispose()
            del self._subscriptions[subscription_id]
            logger.debug(f"구독 해제: {subscription_id}")
            
    def _handle_event(self, handler: Callable, event: Dict):
        """이벤트 처리
        
        Args:
            handler: 핸들러 함수
            event: 이벤트 데이터
        """
        try:
            handler(event["data"])
        except Exception as e:
            logger.error(f"이벤트 핸들러 오류: {str(e)}")
            
    def clear(self):
        """모든 구독 해제 및 초기화"""
        for subscription_id in list(self._subscriptions.keys()):
            self.unsubscribe(subscription_id)
            
        self._subjects.clear()
        logger.debug("EventBus 초기화 완료")
        
    def get_active_subscriptions(self) -> list:
        """활성 구독 목록 반환
        
        Returns:
            list: 구독 ID 목록
        """
        return list(self._subscriptions.keys())
        
    def get_event_types(self) -> list:
        """등록된 이벤트 타입 목록 반환
        
        Returns:
            list: 이벤트 타입 목록
        """
        return list(self._subjects.keys()) 