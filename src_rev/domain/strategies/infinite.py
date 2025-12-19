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
        
        # 2. 현재 회차 (T) 계산 = 총 매입금 / 1회 매수 금액
        #    정밀한 T값 (소수점 1째 자리 반올림) 지원
        current_t = 0.0
        if position.total_cost > 0 and one_time_budget > 0:
            current_t = round(position.total_cost / one_time_budget, 1)
            
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
        #    공식: (Max - 2.0) - (진행률/100 * (Max-2.0)*2) + 보정
        #    (User Feedback: 2.5가 아닌 2.0을 사용해야 데이터와 일치)
        base_star_ratio = config.max_profit_rate - 2.0
        star_ratio = base_star_ratio - (progress_rate / 100.0 * base_star_ratio * 2) + config.star_adjustment_rate
        
        # If avg_price is 0 (initial entry), use ref_price (current_price)
        base_price = position.avg_price if position.avg_price > 0 else ref_price
        star_price = base_price * (1 + star_ratio / 100.0)
        
        return {
            "one_time_budget": one_time_budget,
            "current_t": current_t,
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
            
            # Star 매도 주문 (LOC) - Star가격 그대로 (User Request)
            # 매수가는 Star-0.01, 매도는 Star -> 0.01 차이 발생
            if star_sell_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.SELL,
                    price=metrics["star_price"], # Star가격
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

        # T 0~20회차 (전반전)
        star_buy_qty = 0
        avg_buy_qty = 0
        buy_price = 0.0
        
        if current_t <= 20: 
            # 1. Star 매수 수량 계산 (User Formula: round(1회매수금/2/Star가격))
            star_buy_budget = one_time_budget / 2
            # metrics["star_price"] is float, round returns int (py3)
            star_buy_qty = round(star_buy_budget / metrics["star_price"])
            
            if star_buy_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.BUY,
                    price=metrics["star_price"] - 0.01, # Star가격 - 0.01
                    quantity=star_buy_qty,
                    order_type=OrderType.LOC,
                    description="Star 가격 매수"
                ))
            
            # 2. 평단 매수 수량 계산
            # User Input: "1회매수금/Star가격 - 그 수량" (Text) vs Table (51)
            # Table Logic: (4250 / 43.19) - 47 = 98.4 - 47 = 51.
            # Thus, formula is "Total Capacity at AvgPrice - StarQty".
            # 평단가가 0(첫 매수)이면 현재가 기준
            buy_price = position.avg_price if position.avg_price > 0 else ref_price
            
            if buy_price > 0:
                # Total desired quantity for this turn
                total_turn_qty = int(one_time_budget / buy_price)
                avg_buy_qty = total_turn_qty - star_buy_qty
            else:
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
        
        else: # T > 20회차 (후반전)
            # Star 가격 전액 매수 (평단 매수 없음)
            full_buy_qty = math.floor(one_time_budget / metrics["star_price"])
            star_buy_qty = full_buy_qty
            avg_buy_qty = 0
            
            # T>20 에서는 평단 매수가 없으므로, Additional Buy의 기준 가격을 Star가격으로 설정
            buy_price = metrics["star_price"]
            
            if full_buy_qty > 0:
                orders.append(Order(
                    symbol=config.symbol,
                    side=OrderSide.BUY,
                    price=metrics["star_price"] - 0.01, # Star가격 - 0.01
                    quantity=full_buy_qty,
                    order_type=OrderType.LOC,
                    description="Star 가격 전액 매수 (후반전)"
                ))

        # --- Additional Buy (추가매수) 로직 ---
        # 공식: 1일매수금 / (Star수량 + 평단매수수량 + i)
        # Gap Logic: 평단가 vs 현재가 이격도에 따라 묶음 주문
        
        base_qty = star_buy_qty + avg_buy_qty
        
        current_price = position.current_price if position.current_price > 0 else position.avg_price
        avg_price = position.avg_price
        
        # 이격도 계산
        gap_rate = 0.0
        if current_price > 0 and avg_price > 0:
            gap_rate = (avg_price - current_price) / current_price
        
        added_orders = 0
        curr_i = 1
        last_price = buy_price
        current_denom = base_qty
        
        # 무한루프 방지
        while added_orders < 30:
            # 다음 단계 가격 임시 계산
            temp_denom = current_denom + 1
            temp_price = one_time_budget / temp_denom
            
            step_bundle = 1
            
            if current_t > 20:
                # T>20 (후반전) 로직 - User Table Matching (2 then 5)
                if gap_rate >= 0.02:
                    # 대이격 상태 (Gap > 2%)
                    # Zone B 심화 (가격 급락 시): 5주 
                    # Threshold: 33.20 is roughly -14% from 38.58.
                    # Let's say if Price < Current * 0.9 (10% lower), use 5.
                    if temp_price < current_price * 0.90: 
                            step_bundle = 5
                    else:
                            step_bundle = 2 # 기본 2주 (대이격 상세 대응)
                else:
                    step_bundle = 1 # 이격 없으면 1주
            else:
                # T<=20 (전반전) 로직 - 문서 기준 (4/2/1)
                # 사용자 요청: "TradingStrategy.md에 있는 대로 4개씩 묶는 주문"
                if gap_rate >= 0.02:
                    step_bundle = 4 # Zone A
                elif gap_rate > 0:
                    step_bundle = 2 # Zone B
                else:
                    step_bundle = 1
            
            # 실제 적용 (분모 증가)
            current_denom += step_bundle
            order_price = one_time_budget / current_denom
            
            # Check stop condition (50% drop safety)
            if order_price < last_price * 0.5: 
                break
            
            orders.append(Order(
                symbol=config.symbol,
                side=OrderSide.BUY,
                price=order_price,
                quantity=step_bundle,
                order_type=OrderType.LOC,
                description=f"추가매수 (+{step_bundle})"
            ))
            
            added_orders += 1
            last_price = order_price

        return orders
