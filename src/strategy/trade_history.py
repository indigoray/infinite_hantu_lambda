import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from src.api.kis_client import KISClient

logger = logging.getLogger(__name__)

class TradeHistory:
    """거래 내역 조회 및 테이블 생성 클래스"""
    
    def __init__(self, kis_client: KISClient, symbol: str, strategy_params: Dict, test_mode: bool = False):
        """거래 내역 관리 클래스 초기화
        
        Args:
            kis_client: 한국투자증권 API 클라이언트
            symbol: 거래 종목
            strategy_params: 전략 파라메터
            test_mode: 테스트 모드 (가상 거래내역 사용)
        """
        self.client = kis_client
        self.symbol = symbol
        self.strategy_params = strategy_params
        self.test_mode = test_mode
        
        if self.test_mode:
            logger.info(f"🧪 {symbol} 거래내역 테스트 모드 활성화 - 가상 데이터 사용")
        
    def get_trading_history_table(self, days: int = 30, cycle_start_date: Optional[str] = None) -> pd.DataFrame:
        """거래 내역을 날짜별로 집계한 테이블 반환
        
        Args:
            days: 조회할 일수 (기본 30일)
            cycle_start_date: 사이클 시작 날짜 (ISO 형식)
            
        Returns:
            pd.DataFrame: 날짜별 거래 내역 테이블
        """
        try:
            logger.info(f"📊 거래내역 테이블 생성 시작: days={days}, test_mode={self.test_mode}, symbol={self.symbol}")
            
            # 전략 시작 날짜 확인
            start_date = None
            if cycle_start_date:
                start_date = datetime.fromisoformat(cycle_start_date).date()
                logger.info(f"🔧 cycle_start_date가 제공됨: {cycle_start_date} -> {start_date}")
            else:
                start_date = (datetime.now() - timedelta(days=days)).date()
                logger.info(f"🔧 days 기준으로 시작날짜 계산: {days}일 전 -> {start_date}")
            
            logger.info(f"📊 조회 기간: {start_date} ~ {datetime.now().date()}")
            
            # 거래 내역 가져오기
            trades = self._get_trade_history(start_date)
            
            if not trades:
                logger.info("거래 내역이 없습니다.")
                return pd.DataFrame()
            
            # 날짜별 집계
            daily_summary = self._aggregate_trades_by_date(trades)
            
            # 테이블 생성
            table_data = self._create_trading_table(daily_summary, start_date)
            
            return pd.DataFrame(table_data)
            
        except Exception as e:
            logger.error(f"거래 내역 테이블 생성 중 오류: {str(e)}")
            return pd.DataFrame()
    
    def _get_trade_history(self, start_date: datetime.date) -> List[Dict]:
        """지정된 날짜부터 현재까지의 거래 내역 조회
        
        Args:
            start_date: 시작 날짜
            
        Returns:
            List[Dict]: 거래 내역 리스트
        """
        # 테스트 모드인 경우 가상 데이터 반환
        if self.test_mode:
            mock_data = self._generate_mock_trade_history(start_date)
            logger.info(f"🧪 테스트 모드: {len(mock_data)}건의 가상 거래 데이터 생성 (기간: {start_date}~)")
            return mock_data
            
        try:
            all_trades = []
            current_date = datetime.now().date()
            
            # 날짜별로 거래 내역 조회 (최대 30일)
            date_cursor = start_date
            while date_cursor <= current_date:
                try:
                    order_date = date_cursor.strftime("%Y%m%d")
                    orders_result = self.client.get_oversea_orders(order_date)
                    
                    if orders_result.get("rt_cd") == "0":
                        orders = orders_result.get("output1", [])
                        
                        # 해당 종목의 체결된 주문만 필터링
                        for order in orders:
                            if (order.get("pdno") == self.symbol and 
                                order.get("ccld_yn") == "Y" and 
                                int(order.get("ccld_qty", "0")) > 0):
                                
                                trade = {
                                    "date": date_cursor,
                                    "side": "BUY" if order.get("sll_buy_dvsn_cd") == "02" else "SELL",
                                    "quantity": int(order.get("ccld_qty", "0")),
                                    "price": float(order.get("ccld_unpr", "0")),
                                    "amount": int(order.get("ccld_qty", "0")) * float(order.get("ccld_unpr", "0")),
                                    "order_time": order.get("ord_tmd", ""),
                                    "order_no": order.get("odno", "")
                                }
                                all_trades.append(trade)
                                
                except Exception as e:
                    logger.debug(f"날짜 {date_cursor} 거래 내역 조회 실패: {str(e)}")
                
                date_cursor += timedelta(days=1)
                
            logger.info(f"총 {len(all_trades)}건의 거래 내역을 조회했습니다. (기간: {start_date} ~ {current_date})")
            return all_trades
            
        except Exception as e:
            logger.error(f"거래 내역 조회 중 오류: {str(e)}")
            return []
    
    def _aggregate_trades_by_date(self, trades: List[Dict]) -> Dict:
        """거래 내역을 날짜별로 집계
        
        Args:
            trades: 거래 내역 리스트
            
        Returns:
            Dict: 날짜별 집계 데이터
        """
        daily_data = {}
        
        for trade in trades:
            date_str = trade["date"].strftime("%Y-%m-%d")
            
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "date": trade["date"],
                    "buy_quantity": 0,
                    "sell_quantity": 0,
                    "buy_amount": 0.0,
                    "sell_amount": 0.0,
                    "trades": []
                }
            
            daily_data[date_str]["trades"].append(trade)
            
            if trade["side"] == "BUY":
                daily_data[date_str]["buy_quantity"] += trade["quantity"]
                daily_data[date_str]["buy_amount"] += trade["amount"]
            else:  # SELL
                daily_data[date_str]["sell_quantity"] += trade["quantity"]
                daily_data[date_str]["sell_amount"] += trade["amount"]
        
        return daily_data
    
    def _create_trading_table(self, daily_summary: Dict, start_date: datetime.date) -> List[Dict]:
        """거래 내역 테이블 데이터 생성
        
        Args:
            daily_summary: 날짜별 집계 데이터
            start_date: 시작 날짜
            
        Returns:
            List[Dict]: 테이블 데이터 (최신 날짜가 위로)
        """
        # 1단계: 날짜 순서대로 누적 계산 진행 (과거→현재)
        cumulative_data = {}
        current_date = start_date
        end_date = datetime.now().date()
        
        # 누적 정보 추적
        cumulative_quantity = 0
        cumulative_investment = 0.0
        cumulative_proceeds = 0.0
        total_buy_amount = 0.0
        cumulative_realized_profit = 0.0
        
        # 날짜 순서대로 누적 계산
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data = daily_summary.get(date_str, {})
            
            # 당일 거래 정보
            buy_qty = daily_data.get("buy_quantity", 0)
            sell_qty = daily_data.get("sell_quantity", 0)
            buy_amount = daily_data.get("buy_amount", 0.0)
            sell_amount = daily_data.get("sell_amount", 0.0)
            
            # 수량 변동
            quantity_change = buy_qty - sell_qty
            cumulative_quantity += quantity_change
            
            # 투자금 누적
            cumulative_investment += buy_amount
            cumulative_proceeds += sell_amount
            total_buy_amount += buy_amount
            
            # 해당 날짜의 가격 정보 (거래 데이터에서 추출)
            daily_price = 0
            if daily_data.get("trades"):
                # 해당 날짜 거래가 있으면 그 거래의 평균 가격 사용
                total_value = sum(trade["price"] * trade["quantity"] for trade in daily_data["trades"])
                total_qty = sum(trade["quantity"] for trade in daily_data["trades"])
                daily_price = total_value / total_qty if total_qty > 0 else 0
            else:
                # 거래가 없으면 현재가 사용 (테스트 모드)
                daily_price = self._get_current_price()
            
            # 평단가 계산 (현재 보유 수량 기준)
            avg_price = 0
            if cumulative_quantity > 0 and cumulative_investment > cumulative_proceeds:
                avg_price = (cumulative_investment - cumulative_proceeds) / cumulative_quantity
            
            # Star가격 계산 
            star_price = 0
            if avg_price > 0:
                star_price = self._calculate_star_price(avg_price, cumulative_quantity)
            
            # 실현손익 계산 (매도시에만)
            realized_profit = 0
            if sell_qty > 0 and avg_price > 0:
                # 매도수량에 대한 실현손익 = (매도가격 - 평단가) * 매도수량
                if daily_data.get("trades"):
                    sell_trades = [t for t in daily_data["trades"] if t["side"] == "SELL"]
                    for trade in sell_trades:
                        realized_profit += (trade["price"] - avg_price) * trade["quantity"]
            
            # 누적 실현손익 계산 (매도 거래의 실현손익만 누적)
            cumulative_realized_profit += realized_profit
            
            # 당일투자액 (달러)
            daily_investment_amount = buy_amount
            
            # 누적투자액 (달러)  
            cumulative_investment_amount = cumulative_investment
            
                        # 잔고수익률 (현재 포지션 기준)
            position_profit_rate = ((daily_price - avg_price) / avg_price) * 100 if avg_price > 0 and cumulative_quantity > 0 else 0
            
            # 테스트 모드에서는 모든 날짜 표시, 실제 모드에서는 거래가 있는 날만 표시
            if self.test_mode:
                # 테스트 모드: 가격 정보가 있는 모든 날짜 표시
                show_row = daily_price > 0
                logger.debug(f"📅 {current_date}: 테스트모드 show_row={show_row}, daily_price={daily_price}")
            else:
                # 실제 모드: 포지션이나 거래가 있는 날만 표시
                show_row = (buy_qty > 0 or sell_qty > 0 or cumulative_quantity > 0 or 
                           cumulative_investment > 0 or realized_profit != 0)
                logger.debug(f"📅 {current_date}: 실제모드 show_row={show_row}, buy={buy_qty}, sell={sell_qty}, qty={cumulative_quantity}")
                
            if show_row:
                # 누적 데이터 저장 (날짜 키로)
                cumulative_data[current_date] = {
                    "Date": current_date.strftime("%Y.%m.%d"),
                    "Close": f"${daily_price:.2f}" if daily_price > 0 else "",
                    "평단가": f"${avg_price:.2f}" if avg_price > 0 else "",
                    "Star가격": f"${star_price:.2f}" if star_price > 0 else "",
                    "수량": cumulative_quantity,
                    "수량변동": f"+{quantity_change}" if quantity_change > 0 else str(quantity_change) if quantity_change < 0 else "",
                    "실현손익($)": f"${realized_profit:.2f}" if realized_profit != 0 else "",
                    "누적손익($)": f"${cumulative_realized_profit:.2f}" if cumulative_realized_profit != 0 else "",
                    "누적투자액($)": f"${cumulative_investment_amount:.2f}" if cumulative_investment_amount > 0 else "",
                    "당일투자액($)": f"${daily_investment_amount:.2f}" if daily_investment_amount > 0 else "",
                    "잔고수익률": f"{position_profit_rate:.2f}%" if position_profit_rate != 0 else ""
                }
                
            current_date += timedelta(days=1)
        
        # 2단계: 날짜 순서대로 정렬하여 테이블 데이터 생성 (아래로 갈수록 최신)
        table_data = []
        sorted_dates = sorted(cumulative_data.keys())  # 시간순 정렬 (과거→현재)
        
        for date in sorted_dates:
            table_data.append(cumulative_data[date])
        
        logger.info(f"📊 거래내역 테이블 생성 완료: {len(table_data)}행")
        
        return table_data
    
    def _get_current_price(self) -> float:
        """현재가 조회"""
        # 테스트 모드인 경우 가상 현재가 반환
        if self.test_mode:
            # SOXL 기준 현실적인 현재가
            base_price = 35.50
            # 최근 며칠간의 변동을 반영한 현재가
            price_variation = random.uniform(-0.1, 0.1)  # ±10% 변동
            mock_current_price = base_price * (1 + price_variation)
            return round(max(10.0, mock_current_price), 2)
        
        try:
            price_info = self.client.get_oversea_stock_price(self.symbol)
            return float(price_info.get("current_price", 0))
        except Exception as e:
            logger.warning(f"현재가 조회 실패: {str(e)}")
            return 0.0
    
    def _get_current_avg_price(self) -> float:
        """현재 평단가 조회"""
        # 테스트 모드인 경우 거래 내역에서 평단가 계산
        if self.test_mode:
            # 가상 거래 내역에서 평단가 계산
            return self._calculate_avg_price_from_mock_data()
        
        try:
            balance = self.client.get_oversea_balance()
            for item in balance:
                if item["symbol"] == self.symbol:
                    return float(item["avg_price"])
            return 0.0
        except Exception as e:
            logger.warning(f"평단가 조회 실패: {str(e)}")
            return 0.0
    
    def _calculate_avg_price_from_mock_data(self) -> float:
        """가상 거래 데이터에서 평단가 계산"""
        try:
            # 간단한 평단가 계산 (SOXL 기준 현실적인 값)
            base_price = 35.50
            price_variation = random.uniform(-0.15, 0.15)  # ±15% 변동
            mock_avg_price = base_price * (1 + price_variation)
            return round(max(20.0, mock_avg_price), 2)
            
        except Exception as e:
            logger.warning(f"가상 평단가 계산 실패: {str(e)}")
            return 32.50  # 기본값
    
    def _calculate_star_price(self, avg_price: float, cumulative_quantity: int) -> float:
        """Star가격 계산
        
        Args:
            avg_price: 평단가
            cumulative_quantity: 누적 수량
            
        Returns:
            float: Star가격
        """
        try:
            # 현재 진행률 기준으로 Star가격 계산
            total_cost = cumulative_quantity * avg_price
            progress_ratio = (total_cost / self.strategy_params["total_investment"]) * 100
            
            max_star_ratio = self.strategy_params["max_profit_rate"] - 2.5
            star_adjustment_rate = self.strategy_params.get("star_adjustment_rate", 0)
            
            star_price_ratio = max_star_ratio - (progress_ratio/100) * max_star_ratio * 2 + star_adjustment_rate
            star_price = avg_price * (1 + star_price_ratio/100)
            
            return star_price
            
        except Exception as e:
            logger.warning(f"Star가격 계산 실패: {str(e)}")
            return 0.0
    
    def _generate_mock_trade_history(self, start_date: datetime.date) -> List[Dict]:
        """테스트용 가상 거래내역 생성 (30건 고정, 매수->매도 패턴)
        
        Args:
            start_date: 시작 날짜
            
        Returns:
            List[Dict]: 가상 거래 내역 리스트
        """
        try:
            mock_trades = []
            current_date = datetime.now().date()
            total_days = (current_date - start_date).days + 1
            
            # 가상 거래 생성을 위한 초기 설정
            base_price = 35.50  # SOXL 기준 시작가
            current_price = base_price
            total_quantity = 0
            order_counter = 1
            target_trades = 30  # 목표 거래 수
            generated_trades = 0
            
            # 거래 패턴: 처음 70%는 매수 위주, 나머지 30%는 매도 위주
            buy_phase_trades = int(target_trades * 0.7)  # 21건 매수 위주
            sell_phase_trades = target_trades - buy_phase_trades  # 9건 매도 위주
            
            # 날짜 배분 (전체 기간에 고르게 분포)
            dates_for_trades = []
            for i in range(target_trades):
                days_offset = int((i / target_trades) * total_days)
                trade_date = start_date + timedelta(days=days_offset)
                if trade_date > current_date:
                    trade_date = current_date
                dates_for_trades.append(trade_date)
            
            for i, trade_date in enumerate(dates_for_trades):
                # 가격 변동 (SOXL 특성: 높은 변동성)
                price_change_pct = random.uniform(-0.08, 0.12)  # -8%~+12% 변동 (약간 상승 편향)
                current_price = max(15.0, current_price * (1 + price_change_pct))
                
                # 거래 타입 결정 (단계별 패턴)
                if i < buy_phase_trades:
                    # 초기 단계: 매수 위주 (95% 매수)
                    trade_type = "BUY" if random.random() < 0.95 else "SELL"
                else:
                    # 후반 단계: 매도 위주 (70% 매도)
                    trade_type = "SELL" if random.random() < 0.7 else "BUY"
                
                # 거래 수량 결정
                if trade_type == "BUY":
                    # 매수: 1일 매수금액 기준 (현실적인 수량)
                    daily_amount = self.strategy_params["total_investment"] / self.strategy_params["division_count"]
                    # 원화를 달러로 환산 (환율 1300 가정)
                    daily_amount_usd = daily_amount / 1300
                    base_quantity = max(1, int(daily_amount_usd / current_price))
                    quantity = random.randint(max(1, base_quantity - 1), base_quantity + 2)
                    total_quantity += quantity
                else:  # SELL
                    # 매도: 보유 수량이 있을 때만
                    if total_quantity > 0:
                        # 후반부에는 더 많이 매도 (20-60%)
                        if i >= buy_phase_trades:
                            sell_ratio = random.uniform(0.2, 0.6)
                        else:
                            sell_ratio = random.uniform(0.1, 0.3)
                        quantity = max(1, min(total_quantity, int(total_quantity * sell_ratio)))
                        total_quantity -= quantity
                    else:
                        # 보유량이 없으면 소량 매수로 변경
                        trade_type = "BUY"
                        quantity = random.randint(1, 3)
                        total_quantity += quantity
                
                # 거래 시간 생성
                trade_hour = random.choice([9, 10, 11, 14, 15, 16])  # 주요 거래 시간
                trade_minute = random.randint(0, 59)
                trade_second = random.randint(0, 59)
                order_time = f"{trade_hour:02d}{trade_minute:02d}{trade_second:02d}"
                
                # 체결가 (현재가 기준 약간 변동)
                execution_price = current_price + random.uniform(-0.30, 0.30)
                execution_price = max(1.0, round(execution_price, 2))
                
                # 가상 거래 데이터 생성
                trade = {
                    "date": trade_date,
                    "side": trade_type,
                    "quantity": quantity,
                    "price": execution_price,
                    "amount": quantity * execution_price,
                    "order_time": order_time,
                    "order_no": f"MOCK{order_counter:06d}"
                }
                
                mock_trades.append(trade)
                order_counter += 1
                generated_trades += 1
                
                # 목표 거래 수에 도달하면 종료
                if generated_trades >= target_trades:
                    break
            
            # 거래 내역을 시간순으로 정렬
            mock_trades.sort(key=lambda x: (x["date"], x["order_time"]))
            
            logger.info(f"🧪 가상 거래내역 생성 완료: {len(mock_trades)}건 (목표: {target_trades}건)")
            logger.info(f"🧪 매수 위주 단계: {buy_phase_trades}건, 매도 위주 단계: {sell_phase_trades}건")
            logger.info(f"🧪 최종 포지션: {total_quantity}주, 마지막 가격: ${current_price:.2f}")
            
            return mock_trades
            
        except Exception as e:
            logger.error(f"가상 거래내역 생성 중 오류: {str(e)}")
            return [] 