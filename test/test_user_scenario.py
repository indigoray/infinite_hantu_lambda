
import sys
import os
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src_rev.domain.models import InfiniteConfig, Position, OrderType, OrderSide
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
from src_rev.domain.common import Money, Quantity, Percentage

def verify_user_scenario():
    # User Input Data
    total_investment = 170000
    division_count = 40
    current_t = 10.9 # From Input
    avg_price = 43.19
    current_price = 38.58
    
    # We must construct a Position that yields T=10.9 approx.
    # 1 time = 4250. Total Cost = 46.325 -> T=10.9
    # To get Cost ~ 46342 with Price 43.19 -> Qty ~ 1073
    quantity = 1073 # Adjusted to match T=10.9 (User's T) for verification
    
    print(f"=== Running Scenario Verification ===")
    print(f"Params: TotalInvest={total_investment}, Avg=${avg_price}, Curr=${current_price}, Qty={quantity}")

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
    
    # Generate Orders
    orders = InfiniteBuyingLogic.generate_orders(config, position)
    
    print(f"\n[Generated Orders]")
    
    # Filter Orders
    buy_orders = [o for o in orders if o.side == OrderSide.BUY]
    sell_orders = [o for o in orders if o.side == OrderSide.SELL]
    
    # Calculate Profit Rate
    metrics = InfiniteBuyingLogic.calculate_metrics(config, position, ref_price=current_price)
    profit_rate = metrics["target_profit_rate"]
    print(f"\n[Metrics Verification]")
    print(f"Calculated Profit Rate: {profit_rate:.2f}% (Expected: 10.91%) -> {'MATCH' if abs(profit_rate - 10.91) < 0.05 else 'DIFF'}")

    print(f"\n[Sell Orders Verification]")
    print(f"{'Type':<12} | {'Price':<10} | {'Qty':<5} | {'Desc'}")
    print("-" * 50)
    
    for order in sell_orders:
        print(f"{order.order_type.name:<12} | ${order.price:<9.2f} | {order.quantity:<5} | {order.description}")

    # Verify Sell Quantities
    # Star Sell: 1073 / 4 = 268
    # Profit Sell: 1073 - 268 = 805
    
    star_sell = next((o for o in sell_orders if "Star" in o.description), None)
    profit_sell = next((o for o in sell_orders if "목표" in o.description), None)
    
    if star_sell:
        print(f"Star Sell Qty: {star_sell.quantity} (Expected 268) -> {'MATCH' if star_sell.quantity == 268 else 'DIFF'}")
        # Base Star Price Check: 45.16 (User) vs Calc
        # Sell Price should be Base (45.16)
        # Note: Code calculates StarPrice around 45.16 now with -2.0 param and T=10.9 adjusted.
        print(f"Star Sell Price: ${star_sell.price:.2f} (Expected ~$45.16)")
    else:
        print("Star Sell: Not Generated!")
        
    if profit_sell:
        print(f"Profit Sell Qty: {profit_sell.quantity} (Expected 800) -> {'MATCH' if profit_sell.quantity == 800 else 'DIFF'}")
        # Profit Price: 43.19 * (1 + 10.91%) = 47.90
        expected_profit_price = 43.19 * (1 + profit_rate/100)
        print(f"Profit Sell Price: ${profit_sell.price:.2f} (Expected ~${expected_profit_price:.2f})")
    else:
        print("Profit Sell: Not Generated!")

    # Filter Buy Orders for Comparison

    
    # Expected Data (Partial from user input)
    # Price, Qty
    expected_additional = [
        (42.92, 1), (42.50, 1), (41.66, 2), (40.86, 2), (40.09, 2),
        (39.35, 2), (38.63, 2), (37.94, 2), (37.28, 2), (36.63, 2),
        (36.01, 2)
    ]
    # Note: User provided more rows, but let's check top 10

    print(f"{'Type':<10} | {'Price':<10} | {'Qty':<5} | {'Desc'}")
    print("-" * 50)
    
    total_buy_qty = 0
    matched_count = 0
    
    for order in buy_orders:
        print(f"{order.order_type.name:<10} | ${order.price:<9.2f} | {order.quantity:<5} | {order.description}")
        total_buy_qty += order.quantity

    print("\n[Comparison with User Table (First few rows)]")
    # Star Buy (47) + Avg Buy (51)
    star_buy = next((o for o in buy_orders if "Star" in o.description and o.side == OrderSide.BUY), None)
    avg_buy = next((o for o in buy_orders if "평단" in o.description), None)
    
    if star_buy:
        print(f"Star Buy: Generated({star_buy.quantity}) vs Expected(47) -> {'MATCH' if star_buy.quantity == 47 else 'DIFF'}")
    else:
        print("Star Buy: Not Generated!")

    if avg_buy:
        print(f"Avg Buy : Generated({avg_buy.quantity}) vs Expected(51) -> {'MATCH' if avg_buy.quantity == 51 else 'DIFF'}")
    else:
        print("Avg Buy : Not Generated!")

    # Check Additional Buys
    additional_buys = [o for o in buy_orders if "추가매수" in o.description]
    print(f"Additional Buy Orders Generated: {len(additional_buys)}")
    
    print("\n[Price vs Cumulative Quantity Check]")
    print(f"{'Row':<4} | {'Gen CumQty':<10} | {'Gen Price':<10} | {'Exp Price (if match)'}")
    print("-" * 60)
    
    # Base Quantity (Star + Avg)
    base_qty = 47 + 51 # 98
    current_cum_qty = base_qty
    
    # User Expected Table (CumQty mapped to Price)
    # Row 1: Q+1=99, P=42.92
    # Row 2: Q+1=100, P=42.50
    # Row 3: Q+2=102, P=41.66
    # Row 4: Q+2=104, P=40.86
    user_data_points = {
        99: 42.92,
        100: 42.50,
        102: 41.66,
        104: 40.86,
        106: 40.09,
        108: 39.35,
        110: 38.63
    }
    
    for i, order in enumerate(additional_buys):
        current_cum_qty += order.quantity
        gen_price = order.price
        
        # Check if this CumQty exists in user data
        exp_price = user_data_points.get(current_cum_qty, None)
        
        match_str = ""
        if exp_price:
            diff = abs(gen_price - exp_price)
            if diff < 0.1:
                match_str = f"MATCH (Exp: {exp_price})"
            else:
                match_str = f"DIFF (Exp: {exp_price})"
        else:
            match_str = "-"
            
        print(f"{i+1:<4} | {current_cum_qty:<10} | {gen_price:<10.2f} | {match_str}")
        
        if i >= 10: break # Show top 10 only

if __name__ == "__main__":
    verify_user_scenario()
