
import sys
import os
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src_rev.domain.models import InfiniteConfig, Position, OrderType, OrderSide
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
from src_rev.domain.common import Money, Quantity, Percentage
from src_rev.infrastructure.config_loader import ConfigLoader # Use defaults or mocked

def verify_t22_scenario():
    # User Input Data
    total_investment = 170000
    division_count = 40
    # Calculated T should be 22.4
    avg_price = 43.19
    current_price = 38.58
    quantity = 2200
    
    print(f"=== Running T=22.4 Scenario Verification ===")
    print(f"Params: TotalInvest={total_investment}, Avg=${avg_price}, Curr=${current_price}, Qty={quantity}")

    config = InfiniteConfig(
        symbol="SOXL",
        total_investment=Money(total_investment),
        division_count=division_count,
        max_profit_rate=Percentage(12.0),
        min_profit_rate=Percentage(8.0)
    )
    
    position = Position(
        symbol="SOXL",
        quantity=Quantity(quantity),
        avg_price=Money(avg_price),
        current_price=Money(current_price)
    )
    
    # Generate Orders
    orders = InfiniteBuyingLogic.generate_orders(config, position)
    metrics = InfiniteBuyingLogic.calculate_metrics(config, position, ref_price=current_price)
    
    print(f"\n[Metrics]")
    print(f"T: {metrics['current_t']} (Expected 22.4)")
    print(f"Star Price: {metrics['star_price']:.2f} (Expected 42.67)")
    print(f"Profit Rate: {metrics['target_profit_rate']:.2f}% (Expected 9.76%)")
    
    print(f"\n[Generated Orders]")
    
    buy_orders = [o for o in orders if o.side == OrderSide.BUY]
    sell_orders = [o for o in orders if o.side == OrderSide.SELL]
    
    print(f"{'Type':<12} | {'Price':<10} | {'Qty':<5} | {'Desc'}")
    print("-" * 50)
    for order in sell_orders:
        print(f"{order.order_type.name:<12} | ${order.price:<9.2f} | {order.quantity:<5} | {order.description}")
        
    print("-" * 50)
    for order in buy_orders:
        print(f"{order.order_type.name:<12} | ${order.price:<9.2f} | {order.quantity:<5} | {order.description}")

    # Specific Checks
    print("\n[Comparison with User Table]")
    
    # 1. Sell Orders
    star_sell = next((o for o in sell_orders if "Star" in o.description), None)
    if star_sell:
        print(f"Star Sell: Qty {star_sell.quantity} (Exp 550) | Price ${star_sell.price:.2f} (Exp 42.67)")
    
    prof_sell = next((o for o in sell_orders if "목표" in o.description), None)
    if prof_sell:
        print(f"Prof Sell: Qty {prof_sell.quantity} (Exp 1650) | Price ${prof_sell.price:.2f} (Exp 47.41)")

    # 2. Buy Orders
    star_buy = next((o for o in buy_orders if "Star" in o.description), None)
    if star_buy:
        print(f"Star Buy: Qty {star_buy.quantity} (Exp 99) | Price ${star_buy.price:.2f} (Exp 42.66)")
        
    # 3. Additional Buys Sequence
    print("\n[Additional Buy Sequence Check]")
    # User User Table: 
    # Starts at 42.07 (Qty 2) -> Cum 101 (StarBuy=99 + 2)
    # 41.26 (Qty 2) -> Cum 103
    # ...
    # 33.20 (Qty 5) -> Cum 128
    
    additional_buys = [o for o in buy_orders if "추가매수" in o.description]
    
    base_qty = 99 # Star Buy Qty
    curr_cum = base_qty
    
    expected_points = {
        101: 42.07,
        103: 41.26,
        123: 34.55,
        128: 33.20
    }
    
    found_points = []
    
    for order in additional_buys:
        curr_cum += order.quantity
        if curr_cum in expected_points:
            exp_p = expected_points[curr_cum]
            match = abs(order.price - exp_p) < 0.2
            print(f"Cum {curr_cum}: Gen ${order.price:.2f} (Qty {order.quantity}) vs Exp ${exp_p} -> {'MATCH' if match else 'DIFF'}")
            found_points.append(curr_cum)
    
    if not additional_buys:
        print("No Additional Buys Generated.")

if __name__ == "__main__":
    verify_t22_scenario()
