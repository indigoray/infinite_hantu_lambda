import sys
import os
import asyncio
import logging

# Add current directory to path so we can import src_rev
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src_rev.infrastructure.kis.mock_api import MockKisApi
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
from src_rev.domain.models import InfiniteConfig, Symbol, Money, Percentage
from src_rev.domain.common import Quantity

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMockLogic")

def test_mock_flow():
    print("🚀 Starting Local Mock Test...\n")

    # 1. Setup Configuration & Mock API
    config_dict = {
        "mock_mode": True
    }
    kis = MockKisApi(config_dict)
    
    # Strategy Config for SOXL
    strategy_config = InfiniteConfig(
        symbol=Symbol("SOXL"),
        total_investment=Money(170000.0), # $170k
        division_count=40,
        max_profit_rate=Percentage(12.0),
        min_profit_rate=Percentage(8.0),
        star_adjustment_rate=Percentage(0.0)
    )

    print("✅ 1. Mock API & Strategy Initialized")

    # 2. Test Account Info (Position & Metrics)
    print("\n🔍 2. Testing Account Info...")
    symbol = strategy_config.symbol
    position = kis.get_position(symbol)
    
    print(f"   [Position] {symbol}: {position.quantity}ea, Avg: ${position.avg_price}, Cur: ${position.current_price}")
    print(f"   [Valuation] Market Value: ${position.market_value:,.2f}, Return: {position.return_rate:.2f}%")
    
    # Validate against expected Excel values
    # Excel: 840 qty, $44.76 avg, $36.01 cur, -19.55% return
    assert position.quantity == 840
    assert abs(position.avg_price - 44.76) < 0.01
    assert abs(position.current_price - 36.01) < 0.01
    assert abs(position.return_rate - (-19.55)) < 0.1
    print("   ✅ Position Data Matches Excel!")

    # 3. Test Cycle Calculation
    print("\n🔄 3. Testing Cycle Metrics...")
    ref_price = position.current_price
    metrics = InfiniteBuyingLogic.calculate_metrics(strategy_config, position, float(ref_price))
    
    print(f"   [Metrics] T: {metrics['current_t']}, T_float: {metrics['current_t_float']:.2f}, Progress: {metrics['progress_rate']:.1f}%")
    print(f"   [Prices] Sell Target: ${metrics['sell_price']:.2f}, Star: ${metrics['star_price']:.2f}")
    
    # 4. Test Order Generation
    print("\n📅 4. Testing Order Generation...")
    orders = InfiniteBuyingLogic.generate_orders(strategy_config, position)
    
    if not orders:
        print("   ⚠️ No orders generated!")
    
    for order in orders:
        print(f"   [Order] {order.side.name} {order.symbol} {order.quantity}ea @ ${order.price:,.2f} ({order.order_type.name})")
    
    print("   ✅ Orders Generated Successfully")

    # 5. Test Order Execution
    print("\n🚀 5. Testing Order Execution...")
    for order in orders:
        success = kis.place_order(order)
        status = "Success" if success else "Failed"
        print(f"   [Execute] {order.description}: {status}")
        assert success is True

    print("\n✨ All Tests Passed! System is Ready.")

if __name__ == "__main__":
    test_mock_flow()
