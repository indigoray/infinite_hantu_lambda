
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf

# 루트 경로 추가 (모듈 임포트를 위해)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir)) # Infinite_hantu_simple
sys.path.append(project_root)

try:
    from src_rev.domain.models import InfiniteConfig, Position, Symbol, Money, Quantity, Percentage, OrderSide, OrderType
    from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
    from src_rev.infrastructure.config_loader import ConfigLoader
except ImportError as e:
    print(f"Import Error: {e}")
    print("프로젝트 루트에서 실행하거나 PYTHONPATH를 설정해주세요.")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtest")

class MockKisApi:
    """백테스트용 가상 거래소 API"""
    def __init__(self):
        self.positions = {} # {symbol: Position}
        self.cash = 0.0 # 보유 현금 (사용된 금액만 추적하거나, 초기 자본 설정 가능)
        self.total_invested = 0.0 # 총 투입 원금 (누적)
        self.realized_profit = 0.0 # 실현 손익

    def get_position(self, symbol_str):
        if symbol_str not in self.positions:
            return Position(
                symbol=Symbol(symbol_str),
                quantity=Quantity(0),
                avg_price=Money(0.0),
                current_price=Money(0.0)
            )
        return self.positions[symbol_str]

    def update_current_price(self, symbol_str, price):
        pos = self.get_position(symbol_str)
        pos.current_price = Money(price)
        self.positions[symbol_str] = pos

    def execute_buy(self, symbol_str, qty, price):
        pos = self.get_position(symbol_str)
        
        # 평단가조정: (기존총액 + 신규총액) / (기존수량 + 신규수량)
        prev_cost = pos.quantity * pos.avg_price
        new_cost = qty * price
        total_qty = pos.quantity + qty
        new_avg = (prev_cost + new_cost) / total_qty
        
        pos.quantity = Quantity(total_qty)
        pos.avg_price = Money(new_avg)
        self.positions[symbol_str] = pos
        
        cost = qty * price
        self.total_invested += cost
        # logger.info(f"[매수] {qty}주 @ ${price:.2f} (총보유: {pos.quantity}, 평단: ${pos.avg_price:.2f})")

    def execute_sell(self, symbol_str, qty, price):
        pos = self.get_position(symbol_str)
        
        if pos.quantity < qty:
            logger.warning(f"매도 수량 부족! 보유: {pos.quantity}, 요청: {qty}")
            qty = pos.quantity
        
        # 수익 실현
        # 매도 금액
        sell_amt = qty * price
        # 매수 원금 (평단 기준)
        buy_cost = qty * pos.avg_price
        
        profit = sell_amt - buy_cost
        self.realized_profit += profit
        
        # 수량 감소
        pos.quantity = Quantity(pos.quantity - qty)
        
        if pos.quantity == 0:
            pos.avg_price = Money(0.0)
            # logger.info(f"[매도완료] {qty}주 @ ${price:.2f} | 수익: ${profit:.2f}")
        else:
            pass
            # logger.info(f"[매도] {qty}주 @ ${price:.2f} | 남은수량: {pos.quantity}")
            
        self.positions[symbol_str] = pos
        return profit

class BacktestEngine:
    def __init__(self, config: InfiniteConfig, system_config: Dict, start_date, end_date):
        self.config = config
        # 초기 전략 할당금 (예: 150,000)
        self.initial_strategy_investment = float(config.total_investment)
        
        # 시스템 설정에서 전체 계좌 자산 로드 (예: 210,000)
        # 없으면 전략 할당금과 동일하게 설정
        backtest_conf = system_config.get("backtest", {})
        self.initial_account_balance = float(backtest_conf.get("total_balance", self.initial_strategy_investment))
        
        self.system_config = system_config
        self.start_date = start_date
        self.end_date = end_date
        self.exchange = MockKisApi()
        self.history = [] # 일별 자산 기록
        self.trade_log = [] # 매매 일지

    def fetch_data(self):
        symbol = self.config.symbol
        logger.info(f"데이터 다운로드 중: {symbol} ({self.start_date} ~ {self.end_date})")
        df = yf.download(symbol, start=self.start_date, end=self.end_date, progress=False)
        if df.empty:
            logger.error("데이터가 없습니다. 기간이나 종목명을 확인해주세요.")
            return None
        return df

    def run(self):
        df = self.fetch_data()
        if df is None: return

        logger.info("============== 백테스트 시작 ==============")
        
        # 복리 모드 확인
        use_compound = self.system_config.get("backtest", {}).get("use_compound_interest", False)
        mode_str = "복리(Compound)" if use_compound else "단리(Fixed)"
        
        logger.info(f"모드: {mode_str}")
        logger.info(f"초기 계좌 자본: ${self.initial_account_balance:,.2f}")
        logger.info(f"초기 전략 할당: ${self.initial_strategy_investment:,.2f}")

        # 첫 사이클 예산 설정
        self.current_budget = self.initial_strategy_investment
        
        # 날짜별 루프
        cycle_count = 1
        self.cycle_results = []
        prev_profit = 0.0
        current_cycle_start = None

        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            
            # 1. 시세 업데이트 (High/Low/Close)
            # yfinance 최신 버전에서는 row['Close']가 스칼라가 아닐 수 있음 (MultiIndex)
            # 여기서는 단일 종목 가정
            try:
                close_price = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
            except:
                close_price = float(row['Close'])
                
            self.exchange.update_current_price(self.config.symbol, close_price)
            position = self.exchange.get_position(self.config.symbol)
            
            # --- [Compounding Logic] ---
            # 보유량이 0이면(사이클 시작 전), 투자금 설정 업데이트
            if position.quantity == 0:
                if current_cycle_start is None:
                    current_cycle_start = date_str
                
                # [수정된 복리 로직]
                # Strategy Budget은 Profit에 따라 증액됨.
                # 단, 여기서는 일별로 계속 바꾸는게 아니라 '사이클 시작 시점'에 확정된 예산으로 플레이.
                # 현재 코드 위치는 매일 장 시작 전 체크이므로, 사이클 내내 동일 예산 유지.
                # 사이클 종료 후(매도 후) 예산 업데이트가 필요함.
                # 따라서 여기서는 self.current_budget 값을 config에 적용하기만 하면 됨.
                
                self.config.total_investment = Money(self.current_budget)
            # ---------------------------

            # 2. 주문 생성 (장중 예약 -> 장마감 동시호가 체결 가정)
            # 실제로는 '내일' 주문을 오늘 밤에 내는 것이지만, 
            # 백테스트에서는 '오늘' 데이터 보고 '오늘 종가'에 샀다고 가정하는 것이 간편 (LOC)
            
            orders = InfiniteBuyingLogic.generate_orders(self.config, position)
            
            daily_buy_amt = 0
            daily_sell_amt = 0
            
            # 3. 주문 체결 시뮬레이션
            for order in orders:
                if order.side == OrderSide.BUY:
                    # LOC 매수 -> 종가 체결 확인
                    # 단, 지정가보다 종가가 낮아야 체결됨 (LOC 조건)
                    # 여기서는 간단히 '조건 만족하면 종가 체결'
                    # order.price (LOC limit) >= close_price
                    if order.order_type == OrderType.LOC:
                        if order.price >= close_price:
                            self.exchange.execute_buy(self.config.symbol, order.quantity, close_price)
                            daily_buy_amt += order.quantity * close_price
                            self.trade_log.append({
                                "date": date_str, "type": "BUY", "price": close_price, "qty": order.quantity, "note": order.description
                            })
                    elif order.order_type == OrderType.MARKET:
                        self.exchange.execute_buy(self.config.symbol, order.quantity, close_price)
                        daily_buy_amt += order.quantity * close_price
                
                elif order.side == OrderSide.SELL:
                    # 매도 주문
                    # LOC 매도: 종가가 지정가 이상일 때 체결 (유리한 가격)
                    # AfterMarket: 종가 체결 가정 (보수적) or Mock logic
                    
                    is_executed = False
                    exec_price = close_price
                    
                    if order.order_type == OrderType.LOC:
                        if close_price >= order.price: # 내 평단보다 높게 팔림
                            is_executed = True
                    elif order.order_type == OrderType.AFTER_MARKET:
                        # 애프터 마켓은 종가와 비슷하거나 약간 변동. 여기선 종가로 근사.
                        if close_price >= order.price:
                            is_executed = True
                    elif order.order_type == OrderType.MOC:
                        # MOC(Market On Close)는 무조건 종가 체결
                        is_executed = True
                            
                    if is_executed:
                        profit = self.exchange.execute_sell(self.config.symbol, order.quantity, exec_price)
                        daily_sell_amt += order.quantity * exec_price
                        self.trade_log.append({
                            "date": date_str, "type": "SELL", "price": exec_price, "qty": order.quantity, "profit": profit, "note": order.description
                        })

            # 4. 자산 기록
            pos = self.exchange.get_position(self.config.symbol)
            
            # 자산 가치 계산
            unrealized = pos.market_value - pos.total_cost
            net_value = self.exchange.realized_profit + unrealized
            
            # 현재 총 자산 (Equity) = 초기 계좌 자본 + 누적 실현 손익
            total_equity = self.initial_account_balance + net_value
            
            # 현 사이클에 할당된 예산 (Total Investment setting)
            cycle_budget = float(self.config.total_investment)
            
            self.history.append({
                "date": date_idx,
                "close": close_price,
                "holdings_val": float(pos.market_value),
                "holdings_qty": int(pos.quantity),
                "avg_price": float(pos.avg_price),
                "realized_profit": self.exchange.realized_profit,
                "net_value": net_value,
                "invested_principal": float(pos.total_cost),
                "total_equity": total_equity,
                "cycle_budget": cycle_budget
            })
            
            # 사이클 종료 체크 (보유량 0이고, 과거에 매수한 적이 있을 때)
            # 여기서는 매도시 수량이 0이 되면 사이클 종료로 봄
            if pos.quantity == 0 and daily_sell_amt > 0:
                cycle_profit = self.exchange.realized_profit - prev_profit
                
                # [예산 업데이트]
                if use_compound:
                    self.current_budget += cycle_profit
                    # 예산이 0 이하로 떨어지지 않게 방어
                    if self.current_budget < 0: self.current_budget = 0
                else:
                    self.current_budget = self.initial_strategy_investment

                # 사이클 정보 저장
                self.cycle_results.append({
                    "cycle": cycle_count,
                    "start": current_cycle_start,
                    "end": date_str,
                    "profit": cycle_profit,
                    "return": (cycle_profit / float(self.config.total_investment)) * 100, # 현재 사이클 예산 대비 수익률
                    "budget": float(self.config.total_investment)
                })

                logger.info(f"✨ 사이클 {cycle_count} 종료! 손익: ${cycle_profit:.2f} | 다음 예산: ${self.current_budget:,.0f} ({date_str})")
                
                cycle_count += 1
                prev_profit = self.exchange.realized_profit
                current_cycle_start = None
                
        logger.info("============== 백테스트 종료 ==============")
        self.generate_report()

    def generate_report(self):
        df_hist = pd.DataFrame(self.history)
        df_hist.set_index('date', inplace=True)
        
        # 그래프에서 0원(미보유) 구간이 바닥을 치지 않도록 NaN 처리
        df_hist['avg_price'] = df_hist['avg_price'].replace(0.0, float('nan'))
        df_hist['invested_principal'] = df_hist['invested_principal'].replace(0.0, float('nan'))
        df_hist['holdings_qty'] = df_hist['holdings_qty'].replace(0, float('nan'))
        
        final_profit = self.exchange.realized_profit
        logger.info(f"최종 실현 수익: ${final_profit:,.2f}")
        
        # 1. 텍스트 리포트 저장
        with open("backtest_report.txt", "w", encoding="utf-8") as f:
            f.write("=== 백테스트 상세 로그 (매도 및 주요 이벤트) ===\n")
            for log in self.trade_log:
                # 사용자가 '추가매수' 로그 제외를 요청함
                if "추가" in log.get("note", ""):
                    continue
                f.write(f"{log}\n")
        logger.info("상세 로그 저장: backtest_report.txt")
        
        # ---------------------------------------------------------
        # 성과 지표 계산 (Performance Metrics)
        # ---------------------------------------------------------
        # 초기 자본: 시스템 설정의 Total Balance 사용
        initial_capital = self.initial_account_balance
        
        # 일별 수익률 계산 (Net Value 기준)
        # 평가는 0에서 시작하는 realized_profit + unrealized 이므로,
        # 총 자산 관점(NAV)으로 변환해야 수익률 계산이 용이함.
        # NAV = Initial Capital + Net Value
        df_hist['nav'] = initial_capital + df_hist['net_value']
        df_hist['daily_return'] = df_hist['nav'].pct_change().fillna(0)
        
        # 1. Total Return (%)
        total_return_rate = (final_profit / initial_capital) * 100
        
        # 2. MDD (Maximum Drawdown)
        running_max = df_hist['nav'].cummax()
        drawdown = (df_hist['nav'] - running_max) / running_max
        mdd = drawdown.min() * 100 # percentage (negative)
        
        # 3. Sharpe Ratio (Annualized, risk-free=0 assumption)
        import numpy as np
        daily_volatility = df_hist['daily_return'].std()
        annual_volatility = daily_volatility * np.sqrt(252)
        if annual_volatility == 0:
            sharpe_ratio = 0.0
        else:
            # 연환산 수익률 (CAGR approx or arithmetic)
            # Arithmetic mean annualized
            avg_daily_return = df_hist['daily_return'].mean()
            annual_return = avg_daily_return * 252
            sharpe_ratio = annual_return / annual_volatility

        # ---------------------------------------------------------
        # 리포트 작성
        # ---------------------------------------------------------
        
        # 0. 설정 요약 (Configuration Summary)
        # ---------------------------------------------------------
        use_compound = self.system_config.get("backtest", {}).get("use_compound_interest", False)
        compound_str = "적용 (Compound)" if use_compound else "미적용 (Fixed)"
        
        config_summary = [
            "\n",
            "=== 백테스트 설정 (Configuration) ===",
            f"종목 코드      : {self.config.symbol}",
            f"초기 계좌자본  : ${self.initial_account_balance:,.2f}",
            f"초기 전략할당  : ${self.initial_strategy_investment:,.2f}",
            f"분할 수        : {self.config.division_count}회",
            f"목표 수익률    : {float(self.config.max_profit_rate)}%",
            f"수익 재투자    : {compound_str}",
            "====================================="
        ]

        summary_text = [
            "\n",
            "=== 전략 성과 요약 (Performance Summary) ===",
            f"투자 원금      : ${initial_capital:,.2f}",
            f"최종 순수익    : ${final_profit:,.2f}",
            f"총 수익률      : {total_return_rate:.2f}%",
            f"MDD            : {mdd:.2f}%",
            f"Sharpe Ratio   : {sharpe_ratio:.4f}",
            f"연환산 변동성  : {annual_volatility*100:.2f}%",
            "============================================"
        ]
        
        cycle_summary = [
            "\n=== 사이클별 성과 (Cycle Summary) ===",
            f"{'Cycle':<6} | {'Start Date':<12} | {'End Date':<12} | {'Budget':<12} | {'Profit':<12} | {'Return':<8}",
            "-" * 75
        ]
        
        for res in self.cycle_results:
            line = f"{res['cycle']:<6} | {res['start']:<12} | {res['end']:<12} | ${res['budget']:<11,.0f} | ${res['profit']:<11,.2f} | {res['return']:<6.2f}%"
            cycle_summary.append(line)
        cycle_summary.append("===========================================================================\n")
        
        # 전체 텍스트 합치기
        full_summary = config_summary + cycle_summary + summary_text
        
        for line in full_summary:
            print(line.strip())

        # 1. 텍스트 리포트 저장 (Append Summary)
        with open("backtest_report.txt", "a", encoding="utf-8") as f:
            for line in full_summary:
                f.write(f"{line}\n")
        
        logger.info("성과 요약 리포트 작성 완료")
        
        # 2. 그래프 생성
        plt.figure(figsize=(12, 12)) # 그래프 크기 확대 (3단)
        
        # 상단: 주가 및 평단가
        plt.subplot(3, 1, 1)
        plt.plot(df_hist.index, df_hist['close'], label='Close Price', color='gray', alpha=0.5)
        plt.plot(df_hist.index, df_hist['avg_price'], label='Avg Price', color='orange', linestyle='--')
        plt.title(f"Price History ({self.config.symbol})")
        plt.legend()
        plt.grid(True)
        
        # 중단: 평가 손익 (Net Value) -> 총 자산(Total Equity) 그래프로 변경하는 것이 더 직관적일 수 있음
        # 사용자가 "계좌 잔고와 Cycle당 투자액 구분"을 요청했으므로,
        # 중단을 "Total Account Balance" (Equity)로 표시하고, Cycle Budget도 같이 표시?
        
        plt.subplot(3, 1, 2)
        plt.plot(df_hist.index, df_hist['total_equity'], label='Total Account Balance', color='blue')
        plt.plot(df_hist.index, df_hist['cycle_budget'], label='Cycle Budget Limit', color='green', linestyle=':', alpha=0.7)
        plt.title(f"Account Balance & Budget (MDD: {mdd:.2f}%)")
        plt.legend()
        plt.grid(True)
        
        # 하단: 매수 원금 & 보유 수량 (Dual Y-Axis)
        ax1 = plt.subplot(3, 1, 3)
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Invested Principal ($)', color='green')
        # fill_between uses 0 as baseline, so nan needs handling or simple plot
        # Using plot with area fill
        ax1.fill_between(df_hist.index, df_hist['invested_principal'], 0, color='green', alpha=0.3, label='Invested Principal')
        ax1.tick_params(axis='y', labelcolor='green')
        ax1.grid(True)
        
        ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
        ax2.set_ylabel('Quantity', color='purple')  # we already handled the x-label with ax1
        ax2.plot(df_hist.index, df_hist['holdings_qty'], color='purple', linestyle='-', linewidth=1.5, label='Holdings Qty')
        ax2.tick_params(axis='y', labelcolor='purple')
        
        plt.title("Invested Capital & Quantity")
        
        plt.tight_layout()
        plt.savefig("backtest_result.png")
        logger.info("그래프 저장: backtest_result.png")
        print(f"\n[완료] 결과 그래프 'backtest_result.png'가 생성되었습니다.")

def main():
    parser = argparse.ArgumentParser(description="무한매수법 백테스트")
    parser.add_argument("--symbol", type=str, default="SOXL", help="종목 코드 (예: SOXL, TQQQ)")
    parser.add_argument("--start", type=str, default="2024-01-01", help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="종료일 (YYYY-MM-DD)")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="설정 파일 경로")
    
    args = parser.parse_args()
    
    # 설정 로드
    # config_loader는 src_rev가 아니라 src_tele_lambda 내의 구조에 맞게 로드 될 수 있음.
    # 하지만 여기는 standalone script이므로 config path를 잘 찾아야 함.
    
    # 상대경로 처리
    real_config_path = os.path.join(project_root, args.config)
    if not os.path.exists(real_config_path):
        # src_tele_lambda 내부에서 실행될 경우를 대비해 상위 경로 등 체크
        real_config_path = os.path.join(current_dir, "config", "config.yaml")
        if not os.path.exists(real_config_path):
             print(f"Config Error: {args.config}를 찾을 수 없습니다.")
             return

    loader = ConfigLoader(real_config_path)
    # config_loader returns list or single obj depending on version. 
    # Current main.py logic suggests it returns list.
    domain_configs, system_config = loader.load()
    
    # Select config for the requested symbol
    target_config = None
    if isinstance(domain_configs, list):
        for cfg in domain_configs:
            if cfg.symbol == args.symbol:
                target_config = cfg
                break
    else:
        if domain_configs.symbol == args.symbol:
            target_config = domain_configs

    if not target_config:
        print(f"Configuration for symbol {args.symbol} not found in config.yaml.")
        # Fallback: Create default config
        print("Using Default Config...")
        target_config = InfiniteConfig(
            symbol=Symbol(args.symbol),
            total_investment=Money(20000), # Default 20k
            division_count=40
        )

    print(f"Running Backtest for {args.symbol} from {args.start} to {args.end}")
    engine = BacktestEngine(target_config, system_config, args.start, args.end)
    engine.run()

if __name__ == "__main__":
    main()
