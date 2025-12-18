from datetime import time, datetime, timedelta
import asyncio
import logging
from typing import Optional

from ..domain.models import CycleState, InfiniteConfig, Position
from ..domain.common import Money, Symbol, Quantity
from ..domain.strategies.infinite import InfiniteBuyingLogic
from ..infrastructure.persistence.json_repo import StateRepository
from .bot_service import BotService

logger = logging.getLogger(__name__)

class TradingEngine:
    """
    메인 트레이딩 엔진.
    스케줄링, 상태 관리, 전략 실행을 조율한다.
    """
    
    def __init__(
        self,
        config: InfiniteConfig,
        state_repo: StateRepository,
        bot_service: BotService,
        market_provider=None, # 나중에 KIS API 주입
        order_executor=None   # 나중에 KIS API 주입
    ):
        self.config = config
        self.repo = state_repo
        self.bot = bot_service
        self.market = market_provider
        self.executor = order_executor
        
        self._running = False
        self._state: Optional[CycleState] = None

    async def start(self):
        """엔진 시작"""
        self._running = True
        logger.info("Trading Engine Started")
        
        # 1. 상태 로드
        await self._load_or_init_state()
        
        # 2. 봇 알림
        await self.bot.notify_info(f"🟢 <b>엔진 가동 시작</b>\n대상: {self.config.symbol}\n(일일 사이클 시작)")
        
        # 3. 메인 루프
        while self._running:
            try:
                await self._run_cycle_logic()
                
                # 1분 대기 (테스트를 위해 짧게 설정 가능)
                await asyncio.sleep(60) 
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await self.bot.notify_error(f"메인 루프 에러: {e}")
                await asyncio.sleep(60) # 에러 시 대기

    async def _load_or_init_state(self):
        """저장된 상태를 불러오거나 새로 초기화"""
        self._state = self.repo.load()
        if not self._state:
            logger.info("No saved state found. Initializing new cycle.")
            from datetime import date
            self._state = CycleState(
                cycle_id=f"cycle_{int(datetime.now().timestamp())}",
                symbol=self.config.symbol,
                start_date=date.today(),
                is_active=True
            )
            self.repo.save(self._state)

    async def _run_cycle_logic(self):
        """핵심 사이클 로직 (1일 1회 실행 보장)"""
        now = datetime.now()
        today = now.date()
        
        # 이미 오늘 매수를 완료했는지 확인
        if self._state.last_execution_date == today and self._state.daily_buy_completed:
            # logger.debug("Today's logic already completed.")
            return

        # TODO: 프리마켓 시간 체크 로직 (여기서는 무조건 실행하도록 둠 or 나중에 구현)
        # 지금은 '실행됐다' 가정하고 바로 진입
        
        logger.info("Executing daily strategy logic...")
        
        # 1. 포지션 조회 (Dummy for now)
        current_position = await self._get_position()
        
        # 2. 주문 생성
        orders = InfiniteBuyingLogic.generate_orders(
            self.config, 
            current_position, 
            current_date_executed=False # 위에서 체크했으므로 여기선 False
        )
        
        if not orders:
            logger.info("No orders to execute.")
            return

        # 3. 주문 실행
        logger.info(f"Placing {len(orders)} orders...")
        executed_orders = []
        for order in orders:
            if self.executor:
                if self.executor.place_order(order):
                    executed_orders.append(order)
            else:
                # Dummy executor logic
                executed_orders.append(order)
            
        # 4. 상태 업데이트 (체결 여부와 관계없이 주문 시도는 기록 or 체결된 것만 기록?)
        # 여기서는 보수적으로 '하나라도 성공하면' 완료 처리
        if executed_orders:
            self._state.last_execution_date = today
            self._state.daily_buy_completed = True
            self.repo.save(self._state)
            
            # 5. 알림
            await self.bot.notify_order_execution(executed_orders)

    async def _get_position(self) -> Position:
        """현재 포지션 조회 (추상화)"""
        # API 연동
        if self.market:
             # KisApi.get_position is synchronous, assuming blocking call is acceptable for now
             # or wrap in asyncio.to_thread if needed for high concurrency
             return self.market.get_position(self.config.symbol)
             
        # Dummy Position (Fallback)
        return Position(
            symbol=self.config.symbol,
            quantity=Quantity(0),
            avg_price=Money(0.0),
            current_price=Money(30.0) # $30 (충분히 낮아서 매수 주문이 뜸)
        )
