

### Windows 데몬과 Linux 데몬의 주요 차이점을 비교

1. 프로세스 관리
```
Windows (Service):
- Windows Service Manager가 관리
- GUI 기반 서비스 관리자 제공
- 복잡한 서비스 등록 절차 (레지스트리 등)
- 권한 관리가 상대적으로 복잡

Linux (systemd):
- systemd가 통합 관리
- 명령줄 기반의 간단한 관리
- 단순한 설정 파일로 관리 (.service)
- 명확한 권한 체계
```

2. 로깅 시스템
```
Windows:
- Windows 이벤트 로그에 기록
- 로그 확인이 다소 불편
- 로그 로테이션 수동 설정 필요
- 분산된 로그 저장소

Linux:
- journald로 중앙화된 로깅
- journalctl로 쉬운 로그 확인
- 자동 로그 로테이션
- 구조화된 로그 데이터
```

3. 자동 재시작
```
Windows:
- 제한적인 재시작 정책
- 오류 복구가 상대적으로 불안정
- 수동 설정이 많이 필요

Linux:
- 유연한 재시작 정책 (Restart=always, on-failure 등)
- 자동 백오프 지원 (RestartSec)
- 의존성 기반 재시작
```

4. 의존성 관리
```
Windows:
- 서비스 간 의존성 설정 복잡
- 네트워크 의존성 처리 불안정
- 제한적인 순서 제어

Linux:
- 명확한 의존성 선언 (After, Requires, Wants)
- 네트워크, 파일시스템 등 세밀한 제어
- 병렬 시작 최적화
```

5. 리소스 제어
```
Windows:
- 제한적인 리소스 제어
- 프로세스 우선순위 정도만 조정 가능
- 모니터링 도구 부족

Linux:
- cgroups를 통한 세밀한 리소스 제어
- CPU, 메모리, 디스크 I/O 제한 가능
- 다양한 모니터링 도구
```

결론:
```
Linux 데몬이 더 적합한 경우:
- 24/7 서버 운영
- 안정적인 자동화 필요
- 세밀한 리소스 관리 필요
- 로그 분석이 중요한 경우

Windows 서비스가 더 적합한 경우:
- Windows 전용 기능 필요
- GUI 관리 도구 선호
- Active Directory 통합 필요
- Windows 전용 API 사용
```

트레이딩 봇의 경우, 안정성과 모니터링이 중요하므로 Linux 데몬으로 구현하는 것이 더 적합합니다.


### 분봉 요청 웹소켓 예제
```python
import asyncio
import json
import websockets
from src.utils.logger import setup_logger

logger = setup_logger("websocket_client")

class WebSocketClient:
    def __init__(self, access_token, app_key, app_secret):
        self.access_token = access_token
        self.app_key = app_key
        self.app_secret = app_secret
        self.ws_url = "ws://ops.koreainvestment.com:31000" # 실제 웹소켓 서버 주소
        self.connect_url = "ws://ops.koreainvestment.com:31000/tryitout/H0STCNT0"  # 실시간 체결 구독
        
    async def connect_and_subscribe(self, symbol):
        try:
            async with websockets.connect(self.connect_url) as websocket:
                # 실시간 시세 구독 요청
                subscribe_data = {
                    "header": {
                        "approval_key": self.access_token,
                        "custtype": "P",  # 개인
                        "tr_type": "1",   # 1: 시세, 2: 체결
                        "content-type": "utf-8"
                    },
                    "body": {
                        "input": {
                            "tr_id": "H0STCNT0",  # 실시간 시세 요청 TR ID
                            "tr_key": symbol      # 종목코드
                        }
                    }
                }
                
                await websocket.send(json.dumps(subscribe_data))
                logger.info(f"구독 요청 전송 완료: {symbol}")
                
                while True:
                    data = await websocket.recv()
                    message = json.loads(data)
                    
                    if "error" in message:
                        logger.error(f"에러 발생: {message['error']}")
                        continue
                        
                    # 실시간 데이터 처리
                    self._handle_realtime_data(message)
                    
        except Exception as e:
            logger.error(f"웹소켓 연결 에러: {str(e)}")
            await asyncio.sleep(5)  # 재연결 전 대기
            
    def _handle_realtime_data(self, data):
        """수신된 실시간 데이터 처리"""
        try:
            # 실제 데이터 처리 로직 구현
            logger.info(f"실시간 데이터 수신: {data}")
            return data
        except Exception as e:
            logger.error(f"데이터 처리 중 에러 발생: {str(e)}")
```

### Event Bus 기반 Application Architecture 예제
```python
# src/core/event_bus.py
class EventBus:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.handlers = {}
        
    async def dispatch(self, event: Event):
        """모든 이벤트는 이 메서드를 통해 전달됨"""
        await self.queue.put(event)
        
    async def process_events(self):
        """이벤트 처리 루프"""
        while True:
            event = await self.queue.get()
            if event.type in self.handlers:
                for handler in self.handlers[event.type]:
                    await handler(event)
            self.queue.task_done()

# src/ui/streamlit_handler.py
class StreamlitHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def handle_ui_action(self, action: str, data: dict):
        """UI 액션을 이벤트로 변환하여 Event Bus로 전달"""
        event = Event(
            type="UI_ACTION",
            source="streamlit",
            action=action,
            data=data
        )
        await self.event_bus.dispatch(event)

# src/telegram/telegram_handler.py
class TelegramHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def handle_command(self, command: str, data: dict):
        """텔레그램 명령을 이벤트로 변환하여 Event Bus로 전달"""
        event = Event(
            type="TELEGRAM_COMMAND",
            source="telegram",
            command=command,
            data=data
        )
        await self.event_bus.dispatch(event)
```

### StreamlitHandler 예제
```python
import streamlit as st
from src.core.event_bus import EventBus, Event
from src.utils.logger import setup_logger

logger = setup_logger("streamlit_ui")

class StreamlitHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.setup_page()
        
    def setup_page(self):
        st.set_page_config(
            page_title="라오어의 무한매수 전략",
            page_icon="📈",
            layout="wide"
        )
        
    async def handle_start_strategy(self):
        event = Event(
            type="COMMAND",
            source="streamlit",
            action="start_strategy",
            data={}
        )
        await self.event_bus.dispatch(event)
        
    async def handle_stop_strategy(self):
        event = Event(
            type="COMMAND",
            source="streamlit",
            action="stop_strategy",
            data={}
        )
        await self.event_bus.dispatch(event)
        
    def render(self):
        st.title("라오어의 무한매수 전략 🚀")
        
        if st.button("전략 시작"):
            asyncio.run(self.handle_start_strategy())
            
        if st.button("전략 중지"):
            asyncio.run(self.handle_stop_strategy())

from dataclasses import dataclass
from typing import Any

@dataclass
class Event:
    type: str
    source: str
    action: str
    data: dict[str, Any]

class EventBus:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.handlers = {}
        
    async def dispatch(self, event: Event):
        await self.queue.put(event)
        
    async def subscribe(self, event_type: str, handler):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
```

### Event Bus 예제 RxPy 사용
```python
from rx.subject import Subject
from dataclasses import dataclass
from typing import Any
from enum import Enum
from rx import operators as ops

class EventType(Enum):
    UI_ACTION = "UI_ACTION"
    TELEGRAM_COMMAND = "TELEGRAM_COMMAND"
    TRADE_UPDATE = "TRADE_UPDATE"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"
    PRICE_UPDATE = "PRICE_UPDATE"
    ERROR = "ERROR"

@dataclass
class Event:
    type: EventType
    source: str
    action: str
    data: dict[str, Any]
    priority: int = 0

class EventBus:
    def __init__(self):
        self.subject = Subject()
        
    def subscribe(self, event_type: EventType, handler, priority: int = 0):
        """이벤트 구독
        Args:
            event_type: 구독할 이벤트 타입
            handler: 이벤트 처리 핸들러 함수
            priority: 이벤트 처리 우선순위 (높을수록 먼저 처리)
        """
        return (
            self.subject.pipe(
                ops.filter(lambda e: e.type == event_type),
                ops.filter(lambda e: e.priority >= priority)
            )
            .subscribe(
                on_next=lambda e: handler(e),
                on_error=lambda e: print(f"Error handling event: {e}")
            )
        )
    
    def subscribe_multiple(self, event_types: list[EventType], handler, priority: int = 0):
        """여러 이벤트 타입 동시 구독"""
        return (
            self.subject.pipe(
                ops.filter(lambda e: e.type in event_types),
                ops.filter(lambda e: e.priority >= priority)
            )
            .subscribe(
                on_next=lambda e: handler(e),
                on_error=lambda e: print(f"Error handling event: {e}")
            )
        )
        
    def publish(self, event: Event):
        """이벤트 발행"""
        self.subject.on_next(event)
```

### application main 예시
```python
import streamlit as st
import asyncio
import threading
from src.core.event_bus import EventBus
from src.ui.streamlit_handler import StreamlitHandler
from src.telegram.telegram_handler import TelegramHandler
from src.core.trading_engine import TradingEngine
from src.utils.logger import setup_logger

logger = setup_logger("main")

def run_telegram_bot(event_bus):
    """텔레그램 봇을 별도 스레드에서 실행"""
    telegram_handler = TelegramHandler(event_bus)
    asyncio.run(telegram_handler.start())

def main():
    # Event Bus 초기화
    event_bus = EventBus()
    
    # Trading Engine 초기화
    trading_engine = TradingEngine(event_bus)
    
    # Telegram 봇 스레드 시작
    telegram_thread = threading.Thread(
        target=run_telegram_bot,
        args=(event_bus,),
        daemon=True  # 메인 프로세스 종료시 함께 종료
    )
    telegram_thread.start()
    
    # Streamlit UI 초기화 및 실행
    streamlit_handler = StreamlitHandler(event_bus)
    streamlit_handler.render()

if __name__ == "__main__":
    main()
```

### StreamlitHandler 예제
```python
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.utils.logger import setup_logger

logger = setup_logger("streamlit_ui")

class StreamlitHandler:
    def __init__(self, event_bus: EventBus, trading_engine: TradingEngine):
        self.event_bus = event_bus
        self.event_bus.subscribe(EventType.TRADE_UPDATE, self.handle_trade_update)
        self.event_bus.subscribe(EventType.PORTFOLIO_UPDATE, self.handle_portfolio_update)
        self.trading_engine = trading_engine
        self.setup_page()
        
    def setup_page(self):
        st.set_page_config(
            page_title="라오어의 무한매수 전략",
            page_icon="📈",
            layout="wide"
        )
        st.title("라오어의 무한매수 전략 🚀")

    async def handle_trade_update(self, event: Event):
        # Streamlit의 상태 업데이트
        st.session_state.trades = event.data
        st.experimental_rerun()
    
    async def handle_ui_action(self, action: str, data: dict):
        """UI 액션을 이벤트로 변환하여 Event Bus로 전달"""
        event = Event(
            type="UI_ACTION",
            source="streamlit",
            action=action,
            data=data
        )
        await self.event_bus.dispatch(event)
    
    def render(self):
        """대시보드 렌더링"""
        # 사이드바 설정
        with st.sidebar:
            st.header("설정")
            if st.button("전략 시작"):
                asyncio.create_task(self.handle_ui_action("start_strategy", {}))
            if st.button("전략 중지"):
                asyncio.create_task(self.handle_ui_action("stop_strategy", {}))
            
        # 메인 대시보드 렌더링 (기존 render_dashboard 코드와 동일)
        ...
```
### TradingEngine 예제
```python
class TradingEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def execute_trade(self, order):
        # 거래 실행 후
        await self.event_bus.publish(Event(
            type=EventType.TRADE_UPDATE,
            source="trading_engine",
            data={"trade": order}
        ))        
```