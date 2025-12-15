
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from src_rev.domain.common import Money, Quantity, Percentage, Symbol
from src_rev.domain.models import InfiniteConfig, Position, OrderType, OrderSide
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic

def test_initial_entry_orders():
    """T=0 (초기 진입) 시 주문 생성 테스트"""
    # Given
    config = InfiniteConfig(
        symbol=Symbol("SOXL"),
        total_investment=Money(10000.0), # 1만불
        division_count=40
    )
    # 1회 매수금 = 250불
    
    position = Position(
        symbol=Symbol("SOXL"),
        quantity=Quantity(0),
        avg_price=Money(0.0),
        current_price=Money(100.0)
    )
    
    # When
    orders = InfiniteBuyingLogic.generate_orders(config, position)
    
    # Then
    assert len(orders) > 0
    
    # 초기에는 Star매수(0.5회) + 평단매수(0.5회)
    # Star 수량 = 125 / (100 * Star비율) -> 대략 1개
    # 평단 수량 = 125 / 100 -> 1개
    buy_orders = [o for o in orders if o.side == OrderSide.BUY]
    assert len(buy_orders) >= 2
    
    # 주문 타입 확인 (LOC)
    for order in buy_orders:
        assert order.order_type == OrderType.LOC

def test_metrics_calculation():
    """주요 지표 계산 로직 검증"""
    config = InfiniteConfig(
        symbol=Symbol("SOXL"),
        total_investment=Money(40000.0), # 4만불
        division_count=40
    )
    # 1회 = 1000불
    
    position = Position(
        symbol=Symbol("SOXL"),
        quantity=Quantity(200), # 200개 보유
        avg_price=Money(100.0),  # 평단 100불
        current_price=Money(100.0)
    )
    # 총 매입 = 20,000불 -> T=20 (정확히 절반)
    
    metrics = InfiniteBuyingLogic.calculate_metrics(config, position)
    
    # T=20
    assert metrics["current_t"] == 20
    assert metrics["progress_rate"] == 50.0 # 20/40
    
    # 목표 수익률 계산 (10% ~ 5% 사이)
    # 50% 진행이므로 딱 중간 7.5% 예상
    expected_profit_rate = 10.0 - (50.0 / 100.0 * (10.0 - 5.0))
    assert metrics["target_profit_rate"] == expected_profit_rate
    
    # 매도 가격
    assert metrics["sell_price"] == 100.0 * (1 + 7.5/100)

def test_sell_orders_generation():
    """매도 주문 생성 로직 테스트"""
    config = InfiniteConfig(
        symbol=Symbol("SOXL"),
        total_investment=Money(1000.0),
        division_count=10
    )
    position = Position(
        symbol=Symbol("SOXL"),
        quantity=Quantity(100),
        avg_price=Money(10.0),
        current_price=Money(12.0) # 수익권
    )
    
    orders = InfiniteBuyingLogic.generate_orders(config, position)
    sell_orders = [o for o in orders if o.side == OrderSide.SELL]
    
    # Star 매도(1/4) + 익절 매도(3/4)
    assert len(sell_orders) == 2
    
    star_sell = next(o for o in sell_orders if "Star" in o.description)
    profit_sell = next(o for o in sell_orders if "목표" in o.description)
    
    assert star_sell.quantity == 25  # 100의 1/4
    assert profit_sell.quantity == 75 # 나머지
    assert profit_sell.order_type == OrderType.AFTER_MARKET

def test_late_execution_logic():
    """늦은 실행 시에도 주문이 생성되어야 함"""
    config = InfiniteConfig(
        symbol=Symbol("SOXL"),
        total_investment=Money(1000.0),
        division_count=10
    )
    position = Position(
        symbol=Symbol("SOXL"),
        quantity=Quantity(0),
        avg_price=Money(0.0),
        current_price=Money(10.0)
    )
    
    # 오늘 이미 실행했다면 주문 없어야 함
    orders_executed = InfiniteBuyingLogic.generate_orders(config, position, current_date_executed=True)
    assert len(orders_executed) == 0
    
    # 실행 안했다면 주문 있어야 함
    orders_not_executed = InfiniteBuyingLogic.generate_orders(config, position, current_date_executed=False)
    assert len(orders_not_executed) > 0
