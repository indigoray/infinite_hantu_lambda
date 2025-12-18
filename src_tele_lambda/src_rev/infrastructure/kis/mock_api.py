import logging
from typing import Dict, Any, Optional
from ...domain.common import Symbol, Money, Quantity
from ...domain.models import Position, Order, OrderSide
from .api import KisApi  # Type hint purposes

logger = logging.getLogger(__name__)

class MockKisApi:
    """
    테스트를 위한 Mock KIS API 구현체.
    실제 서버 통신 없이 고정된 데이터를 반환함.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_virtual = True
        logger.info("MOCK API Initialized with fix data.")

    def get_position(self, symbol: Symbol) -> Position:
        """
        고정된 잔고 데이터 반환 (엑셀 스크린샷 데이터 반영)
        """
        if symbol == "SOXL":
            # 엑셀 데이터: 수량 840, 평단 44.76, 현재가 36.01
            return Position(
                symbol=Symbol("SOXL"),
                quantity=Quantity(840),
                avg_price=Money(44.76),
                current_price=Money(36.01)
            )
        elif symbol == "TQQQ":
             # 가상의 TQQQ 데이터 (테스트용)
            return Position(
                symbol=Symbol("TQQQ"),
                quantity=Quantity(100),
                avg_price=Money(50.0),
                current_price=Money(55.0)
            )
        
        return Position(symbol, Quantity(0), Money(0.0))

    def get_market_price(self, symbol: Symbol) -> Money:
        """
        고정된 현재가 반환
        """
        if symbol == "SOXL":
            return Money(36.01)
        elif symbol == "TQQQ":
            return Money(55.0)
        
        return Money(0.0)

    def place_order(self, order: Order) -> bool:
        """
        주문 실행 시늉 (항상 성공)
        """
        side_str = "매수" if order.side == OrderSide.BUY else "매도"
        logger.info(f"[MOCK] Order Placed: {order.symbol} {side_str} {order.quantity}ea @ ${order.price}")
        return True
