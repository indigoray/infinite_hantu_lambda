
import unittest
from src_rev.domain.models import InfiniteConfig, Position, Symbol, Money, Quantity, Percentage, OrderSide, OrderType
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic

class TestT40Logic(unittest.TestCase):
    def setUp(self):
        self.config = InfiniteConfig(
            symbol=Symbol("SOXL"),
            total_investment=Money(4000), # 1회 = 100
            division_count=40
        )
        self.one_time = 100

    def test_t_less_than_40(self):
        # T=40 -> Normal Logic
        pos = Position(
            symbol=Symbol("SOXL"),
            quantity=Quantity(1),
            avg_price=Money(100.0), # Total Cost = 100
            current_price=Money(100.0)
        )
        # T=1. No MOC.
        orders = InfiniteBuyingLogic.generate_orders(self.config, pos)
        has_moc = any(o.order_type == OrderType.MOC for o in orders)
        self.assertFalse(has_moc, "T=1 should not trigger MOC")

    def test_t_equal_40(self):
        # Total Cost = 4000 (40 * 100). T=40.0
        pos = Position(
            symbol=Symbol("SOXL"),
            quantity=Quantity(100),
            avg_price=Money(40.0), # 40 * 100 = 4000
            current_price=Money(40.0)
        )
        # Check metrics internal (optional) or just orders
        # Should NOT trigger MOC (User: "T=40이 될 때는 주문할 돈이 남았으니까 그 돈으로 진행")
        orders = InfiniteBuyingLogic.generate_orders(self.config, pos)
        has_moc = any(o.order_type == OrderType.MOC for o in orders)
        self.assertFalse(has_moc, "T=40.0 should not trigger MOC")

    def test_t_greater_than_40(self):
        # Total Cost = 4100 (41 * 100). T=41.0
        pos = Position(
            symbol=Symbol("SOXL"),
            quantity=Quantity(100),
            avg_price=Money(41.0), # 41 * 100 = 4100
            current_price=Money(41.0)
        )
        # Should trigger MOC (25% of 100 = 25)
        orders = InfiniteBuyingLogic.generate_orders(self.config, pos)
        
        # Verify only 1 order
        self.assertEqual(len(orders), 1, "Should generate exactly 1 MOC order")
        order = orders[0]
        self.assertEqual(order.order_type, OrderType.MOC)
        self.assertEqual(order.side, OrderSide.SELL)
        self.assertEqual(order.quantity, 25) # 100 * 0.25
        print(f"Verified Order: {order}")

if __name__ == '__main__':
    unittest.main()
