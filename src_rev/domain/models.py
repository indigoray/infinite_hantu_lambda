from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from .common import Symbol, Money, Quantity, Percentage

class OrderType(str, Enum):
    LIMIT = "LIMIT"                 # 지정가
    MARKET = "MARKET"               # 시장가
    LOC = "LOC"                     # Limit On Close (종가 지정가)
    AFTER_MARKET = "AFTER_MARKET"   # 애프터마켓 지정가

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Position:
    """현재 보유 종목 상태"""
    symbol: Symbol
    quantity: Quantity
    avg_price: Money
    current_price: Money = field(default=Money(0.0))

    @property
    def total_cost(self) -> Money:
        """총 매입 금액"""
        return Money(self.quantity * self.avg_price)
    
    @property
    def market_value(self) -> Money:
        """현재 평가 금액"""
        return Money(self.quantity * self.current_price)

@dataclass
class Order:
    """주문 요청 객체"""
    symbol: Symbol
    side: OrderSide
    price: Money
    quantity: Quantity
    order_type: OrderType
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""  # 예: "Star 매수", "평단 매수"

@dataclass
class CycleState:
    """전략 사이클 상태 (영속성 대상)"""
    cycle_id: str
    symbol: Symbol
    start_date: date
    is_active: bool = True
    end_date: Optional[date] = None
    accumulated_profit: Money = field(default=Money(0.0))
    
    # 일일 실행 상태 추적
    last_execution_date: Optional[date] = None
    daily_buy_completed: bool = False
    daily_sell_completed: bool = False

@dataclass
class InfiniteConfig:
    """무한매수 전략 설정값"""
    symbol: Symbol
    total_investment: Money        # 총 투자금
    division_count: int = 40       # 분할 수 (기본 40)
    max_profit_rate: Percentage = Percentage(12.0) # 목표 수익률 (12%)
    min_profit_rate: Percentage = Percentage(8.0)  # 최소 수익률 (8%) - 후반전
    star_adjustment_rate: Percentage = Percentage(0.0) # Star 비율 보정
