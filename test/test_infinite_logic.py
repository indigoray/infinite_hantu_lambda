
import sys
import os
import math
from datetime import date

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src_rev.domain.models import InfiniteConfig, Position, OrderType, OrderSide
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
from src_rev.domain.common import Money, Quantity, Percentage

def test_infinite_logic(
    total_investment: float,
    division_count: int,
    quantity: int,
    avg_price: float,
    current_price: float
):
    print(f"=== Testing Infinite Strategy ===")
    print(f"Config: Investment=${total_investment}, Div={division_count}")
    print(f"Position: Qty={quantity}, Avg=${avg_price}, Curr=${current_price}")
    
    config = InfiniteConfig(
        symbol="SOXL",
        total_investment=Money(total_investment),
        division_count=division_count
    )
    
    position = Position(
        symbol="SOXL",
        quantity=Quantity(quantity),
        avg_price=Money(avg_price),
        current_price=Money(current_price)
    )
    
    # 1. Calculate Metrics
    metrics = InfiniteBuyingLogic.calculate_metrics(config, position, ref_price=current_price)
    
    print(f"\n[Metrics]")
    print(f"One Time Budget: ${metrics['one_time_budget']:,.2f}")
    print(f"Current T: {metrics['current_t']}")
    print(f"Progress: {metrics['progress_rate']:.2f}%")
    print(f"Target Profit: {metrics['target_profit_rate']:.2f}%")
    print(f"Star Price: ${metrics['star_price']:.2f} (Ratio: {metrics['star_ratio']:.2f}%)")
    print(f"Sell Price: ${metrics['sell_price']:.2f}")

    # 2. Generate Orders
    orders = InfiniteBuyingLogic.generate_orders(config, position)
    
    print(f"\n[Generated Orders]")
    if not orders:
        print("No orders generated.")
    else:
        for order in orders:
            type_name = order.order_type.name if hasattr(order.order_type, 'name') else str(order.order_type)
            print(f" - {order.side.name} {order.quantity} @ ${order.price:,.2f} ({type_name}) : {order.description}")

if __name__ == "__main__":
    # Example Case: Running in Cycle (e.g. T=9)
    # Total Invest: 20,000, Div: 40 => 1 time = 500
    # Current Cost roughly 4500 (T=9)
    test_infinite_logic(
        total_investment=20000,
        division_count=40,
        quantity=100,
        avg_price=45.0,
        current_price=40.0
    )
