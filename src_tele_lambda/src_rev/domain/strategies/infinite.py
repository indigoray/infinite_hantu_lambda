from datetime import date
from typing import List, Tuple, Dict, Any
import math

from ..common import Money, Quantity, Percentage
from ..models import (
    InfiniteConfig, 
    Position, 
    Order, 
    OrderSide, 
    OrderType,
    CycleState
)

class InfiniteBuyingLogic:
    """
    무한매수법(Laor's Infinite Buying) 순수 로직 구현체.
    상태를 직접 저장하지 않고, 입력(Config, Position)에 따라 행동(Order)을 결정한다.
    """

    @staticmethod
    def calculate_metrics(
        config: InfiniteConfig, 
        position: Position,
        ref_price: float = 0.0
    ) -> Dict[str, Any]:
        """
        현재 상태에 따른 주요 지표(진행률, Star가격 등) 계산
        """
        # 1. 1회 매수 금액 (총 투자금 / 분할 수)
        one_time_budget = config.total_investment / config.division_count
        
        # 3. 현재 회차 (T) 계산 = 총 매입금 / 1회 매수 금액
        #    소수점은 내림 처리하여 보수적으로 계산
        current_t = 0
        current_t_float = 0.0
        if position.total_cost > 0 and one_time_budget > 0:
            current_t_float = position.total_cost / one_time_budget
            current_t = math.floor(current_t_float)
            
        # 3. 진행률 (%)
        progress_rate = (current_t / config.division_count) * 100
        
        # 4. 목표 수익률 동적 계산 (전반전 vs 후반전)
        #    진행률이 0%면 max_profit_rate, 100%면 min_profit_rate가 되도록 선형 보간
        #    공식: Max - (진행률 * (Max - Min))
        target_profit_rate = config.max_profit_rate - (
            progress_rate / 100.0 * (config.max_profit_rate - config.min_profit_rate)
        )
        
        # 5. 익절 목표 가격 (평단가 기준)
        sell_price = position.avg_price * (1 + target_profit_rate / 100.0)
        
        # 6. Star 비율 및 가격 계산 (매수 기준가)
        #    공식: (Max - 2.5) - (진행률/100 * (Max-2.5)*2) + 보정
        #    이는 진행률이 높을수록(후반전) 더 낮은 가격에 매수하도록 유도함
        base_star_ratio = config.max_profit_rate - 2.5
        star_ratio = base_star_ratio - (progress_rate / 100.0 * base_star_ratio * 2) + config.star_adjustment_rate
        
        # If avg_price is 0 (initial entry), use ref_price (current_price)
        base_price = position.avg_price if position.avg_price > 0 else ref_price
        star_price = base_price * (1 + star_ratio / 100.0)
        
        return {
            "one_time_budget": one_time_budget,
            "current_t": current_t,
            "current_t_float": current_t_float,
            "progress_rate": progress_rate,
            "target_profit_rate": target_profit_rate,
            "sell_price": sell_price,
            "star_price": star_price,
            "star_ratio": star_ratio
        }

    @classmethod
    def generate_orders(
        cls, 
        config: InfiniteConfig, 
        position: Position, 
        current_date_executed: bool = False
    ) -> List[Order]:
        """
        전략에 따라 매수/매도 주문 목록을 생성한다.
        실행 여부(current_date_executed)는 호출자가 판단해서 넘겨야 한다.
        이미 실행했다면 빈 리스트 반환.
        """
    
        if current_date_executed:
            return []

        ref_price = position.current_price if position.current_price > 0 else position.avg_price
        metrics = cls.calculate_metrics(config, position, ref_price=float(ref_price))
        orders: List[Order] = []
        
        # A. 매도 주문 생성 (보유 수량이 있을 때만)
        if position.quantity > 0:
            # 1. 익절 매도 (After Market, 전량에서 Star매도분 제외)
            # 2. Star 매도 (LOC, 보유량의 1/4)
            #    단, 원칙적으로는 LOC 매수가 체결될 수 있으므로, 매도는 보수적으로 접근 
            #    (여기서는 표준 전략인 '익절 매도'와 'Star 매도'를 동시에 냄)
            
            # Star 매도: 평단보다 높게 설정해야 손해가 없음. 
            # 하지만 무한매수법에서는 '현금 확보'가 목적이므로 Star가격+알파에 일부 매도.
            star_sell_qty = math.floor(position.quantity / 4)
            profit_sell_qty = position.quantity - star_sell_qty
            
            # 가격 단위(Tick) 처리는 여기서는 생략하고 float 그대로 둠 (Infrastructure 레벨에서 처리)
            
            # Star 매도 주문 (LOC) - Star가격보다 조금 높게 (예: +0.1%)
            if star_sell_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.SELL,
                    price=metrics["star_price"] + 0.01, # Star가격 + 0.01
                    quantity=star_sell_qty,
                    order_type=OrderType.LOC,
                    description="Star 리밸런싱 매도"
                ))
            
            # 익절 매도 주문 (After Market) - 목표 수익률 가격
            if profit_sell_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.SELL,
                    price=metrics["sell_price"],
                    quantity=profit_sell_qty,
                    order_type=OrderType.AFTER_MARKET,
                    description="목표 수익 달성 매도"
                ))

        # B. 매수 주문 생성
        # 초기 진입이거나 (quantity=0), 계속 진행 중일 때
        
        one_time_budget = metrics["one_time_budget"]
        current_t = metrics["current_t"]
        
        # 현재 시장가(current_price)가 0이면(장전 등) LOC 주문을 내기 어려울 수 있으나,
        # LOC는 '종가' 기준이므로 현재가와 무관하게 가격 지정 가능.
        # 단, 수량 계산을 위해 '기준가'가 필요한데, 여기서는 '현재가' 또는 '직전 종가'를 사용해야 함.
        # Position에 있는 current_price가 유효하다고 가정.
        
        ref_price = position.current_price if position.current_price > 0 else position.avg_price
        if ref_price <= 0:
            # 가격 정보가 없으면 매수 수량 계산 불가 -> 주문 생성 스킵 (안전가드)
            return orders

        # 매수 수량 계산 (1회 예산 / 기준가)
        # LOC 주문이므로 실제 체결가는 다를 수 있지만, 대략적인 수량을 정해서 냄
        
        # T <= 20 (전반전)
        if current_t <= 20: 
            # Star 가격 매수 (예산 절반) - MDC: (1일 매수금/2/Star가격)에서 소수점 버림
            star_buy_budget = one_time_budget / 2
            star_qty = math.floor(star_buy_budget / metrics["star_price"])
            
            if star_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.BUY,
                    price=metrics["star_price"],
                    quantity=star_qty,
                    order_type=OrderType.LOC,
                    description="Star 가격 매수"
                ))
            
            # 평단 매수 (예산 절반) - MDC: (1일 매수금 / 1일 매수수량) - Star매수수량
            # 여기서 '1일 매수수량'은 '1일 매수금 / 기준가격'을 의미한다고 판단됨 (통상적인 무한매수 로직)
            buy_price = position.avg_price if position.avg_price > 0 else ref_price
            
            # MDC 식 적용
            total_daily_qty = math.floor(one_time_budget / buy_price)
            avg_buy_qty = total_daily_qty - star_qty
            
            # 만약 avg_buy_qty가 0보다 작으면 0으로 보정
            if avg_buy_qty < 0:
                avg_buy_qty = 0
            
            if avg_buy_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.BUY,
                    price=buy_price,
                    quantity=avg_buy_qty,
                    order_type=OrderType.LOC,
                    description="평단 매수"
                ))

        # T > 20 (후반전)
        else:
            # Star 가격 매수 - MDC: 1일매수금/Star가격 갯수
            star_qty = math.floor(one_time_budget / metrics["star_price"])
            
            if star_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.BUY,
                    price=metrics["star_price"],
                    quantity=star_qty,
                    order_type=OrderType.LOC,
                    description="Star 가격 전액 매수 (후반전)"
                ))
            
            # 평단 매수 없음 (avg_buy_qty = 0 유지)
            avg_buy_qty = 0

        # --- 2. 추가 매수 (거미줄/Grid) ---
        # MDC 공식: 1일매수금 / (Star수량 + 평단매수수량 + 1) ... 가격이 현재가보다 30% 떨어질 때까지
        # T > 20이면 평단매수수량: 0
        
        base_divisor_qty = star_qty + avg_buy_qty
        
        i = 1
        stop_price = ref_price * 0.7 # 현재가 대비 -30%
        
        while True:
            # 추가 매수 가격 계산
            divisor = base_divisor_qty + i
            if divisor == 0: 
                divisor = 1
                
            add_buy_price = one_time_budget / divisor
            
            # 종료 조건: 가격이 stop_price 미만이면 중단
            if add_buy_price < stop_price:
                break
                
            # 주문 생성 (수량 1개 고정)
            orders.append(Order(
                symbol=config.symbol,
                side=OrderSide.BUY,
                price=add_buy_price,
                quantity= Quantity(1),
                order_type=OrderType.LOC,
                description=f"추가 매수 [{i}]"
            ))
            
            i += 1
            # 무한 루프 방지 안전장치
            if i > 200:
                break

        return orders
