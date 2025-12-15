import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path

# 애플리케이션 컴포넌트 임포트
from src.utils.logger import setup_logger
from src.utils.telegram import TelegramHandler
from src.config import Config
from src.api.kis_client import KISClient
from src.event_bus import EventBus
from src.trading_engine import TradingEngine
from src.strategy.infinite_buying import InfiniteBuyingStrategy

# 전역 컴포넌트
components = None

# 로거 설정
logger = logging.getLogger(__name__)

def initialize_application():
    """애플리케이션 초기화 - 한 번만 실행"""
    global components
    
    # 강제 초기화 체크 (개발 중 설정 변경 시 사용)
    force_reinit = st.sidebar.button("🔄 앱 재초기화", help="설정 변경 후 클릭하세요")
    
    # 이미 초기화되었고 강제 초기화가 아니라면 스킵
    if 'app_initialized' in st.session_state and not force_reinit:
        return st.session_state['components']
    
    # 강제 초기화 시 세션 상태 정리
    if force_reinit:
        for key in list(st.session_state.keys()):
            if key.startswith('app_') or key == 'components':
                del st.session_state[key]
        st.info("앱이 재초기화됩니다...")
    
    # 1. 설정 파일 로드
    config = Config()
    
    # 2. 로깅 설정
    setup_logger()
    logger = logging.getLogger(__name__)
    logger.info("무한매수 전략 애플리케이션 시작...")
    
    # 3. 이벤트 버스 초기화
    event_bus = EventBus()
    
    # 4. 텔레그램 핸들러 초기화 (활성화된 경우)
    telegram_handler = None
    if config.telegram.get("enabled", False):
        telegram_handler = TelegramHandler(config.telegram)
        telegram_handler.send_message("🚀 무한매수 전략 시스템이 시작되었습니다.")
        
        # 텔레그램 웹훅 리스너 시작 (주문 승인 시스템)
        try:
            telegram_handler.start_webhook_listener()
            logger.info("텔레그램 웹훅 리스너 시작됨")
        except Exception as e:
            logger.warning(f"텔레그램 웹훅 시작 실패: {e}")
            logger.info("폴링 모드로 주문 승인 시스템이 동작합니다.")
    
    # 5. 한국투자증권 API 클라이언트 초기화
    kis_client = KISClient(config.api)
    
    # 6. 계정 로그인
    if not kis_client.login():
        logger.error("한국투자증권 API 로그인 실패")
        st.error("한국투자증권 API 로그인에 실패했습니다.")
        return None
    
    # 7. 트레이딩 엔진 초기화 (kis_client 추가)
    trading_engine = TradingEngine(event_bus, kis_client)
    
    # 8. 무한매수 전략 생성 및 추가
    strategy = InfiniteBuyingStrategy(kis_client, config, event_bus)
    symbol = config.trading.get("infinite_buying_strategy", {}).get("symbol", "SOXL")
    strategy_name = f"infinite_buying_{symbol}"
    trading_engine.add_strategy(strategy_name, strategy)
    
    # 전략 스케줄 설정 (5분 간격으로 변경 - 더 효율적)
    trading_engine.strategies[strategy_name]["schedule"] = "5m"
    
    # 9. 트레이딩 엔진 시작
    trading_engine.start()
    
    # 10. 컴포넌트 저장
    components = {
        'config': config,
        'trading_engine': trading_engine,
        'event_bus': event_bus,
        'kis_client': kis_client,
        'telegram_handler': telegram_handler,
        'strategy': strategy
    }
    
    # 세션 상태에 저장
    st.session_state['components'] = components
    st.session_state['app_initialized'] = True
    
    # 이벤트 핸들러 설정
    _setup_event_handlers(components)
    
    logger.info("애플리케이션 초기화 완료")
    return components

def _setup_event_handlers(components):
    """이벤트 핸들러 설정"""
    event_bus = components['event_bus']
    telegram = components['telegram_handler']
    
    # 전략 시작/중지 이벤트
    if telegram:
        event_bus.subscribe("strategy_started", 
            lambda data: telegram.send_message(f"✅ 전략 시작: {data['name']}"))
        event_bus.subscribe("strategy_stopped", 
            lambda data: telegram.send_message(f"⏹ 전략 중지: {data['name']}"))
        event_bus.subscribe("strategy_error",
            lambda data: telegram.send_message(f"❌ 전략 오류: {data['name']}\n{data['error']}"))

def setup_page():
    """페이지 기본 설정"""
    st.set_page_config(
        page_title="무한매수 전략 대시보드",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def render_header():
    """헤더 렌더링"""
    st.title("무한매수 전략 대시보드 📈")
    st.markdown("---")

def render_sidebar(components):
    """사이드바 렌더링"""
    config = components['config']  # config 추가
    with st.sidebar:
        # 투자 모드 표시
        kis_client = components['kis_client']
        if kis_client.is_virtual:
            st.success("🧪 모의투자 모드")
            st.caption(f"API URL: {kis_client.base_url}")
        else:
            st.error("⚠️ 실전투자 모드")
            st.caption(f"API URL: {kis_client.base_url}")

        st.markdown("---")
        
        # StockSubscriber 상태 표시
        st.header("📊 가격 모니터링")
        trading_engine = components['trading_engine']
        
        if trading_engine.stock_subscriber:
            # 구독 상태
            if trading_engine.stock_subscriber.is_running:
                st.success("🟢 실행 중")
            else:
                st.warning("🟡 중지됨")
            
            # 구독 중인 심볼들
            subscribed_symbols = trading_engine.get_subscribed_symbols()
            if subscribed_symbols:
                st.subheader("구독 심볼")
                for symbol, info in subscribed_symbols.items():
                    market_flag = "🇺🇸" if info["market"] == "us" else "🇰🇷"
                    price_text = f"${info['last_price']:.2f}" if info["last_price"] > 0 else "대기 중"
                    
                    with st.container():
                        col1, col2 = st.columns([3, 2])
                        with col1:
                            st.write(f"{market_flag} **{symbol}**")
                        with col2:
                            st.write(price_text)
                        
                        if info["last_update"]:
                            from datetime import datetime
                            # last_update가 이미 datetime 객체인지 문자열인지 확인
                            if isinstance(info["last_update"], datetime):
                                last_update = info["last_update"]
                            elif isinstance(info["last_update"], str):
                                last_update = datetime.fromisoformat(info["last_update"])
                            else:
                                st.caption("업데이트 시간 형식 오류")
                                continue
                            st.caption(f"마지막 업데이트: {last_update.strftime('%H:%M:%S')}")
                        else:
                            st.caption("업데이트 대기 중")
            else:
                st.info("구독 중인 심볼 없음")
                
            # 심볼 추가/제거 인터페이스
            st.subheader("심볼 관리")
            
            # 새 심볼 추가
            with st.form("add_symbol_form"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_symbol = st.text_input("심볼", placeholder="예: AAPL 또는 000660")
                with col2:
                    market = st.selectbox("시장", ["us", "kr"])
                
                if st.form_submit_button("➕ 추가"):
                    if new_symbol:
                        if trading_engine.subscribe_symbol(new_symbol, market):
                            st.success(f"✅ {new_symbol} 구독 추가됨")
                            st.rerun()
                        else:
                            st.error("❌ 구독 추가 실패")
                            
            # 심볼 제거
            if subscribed_symbols:
                symbol_to_remove = st.selectbox(
                    "제거할 심볼", 
                    options=list(subscribed_symbols.keys()),
                    key="remove_symbol_select"
                )
                if st.button("➖ 제거"):
                    if trading_engine.unsubscribe_symbol(symbol_to_remove):
                        st.success(f"✅ {symbol_to_remove} 구독 제거됨")
                        st.rerun()
                    else:
                        st.error("❌ 구독 제거 실패")
        else:
            st.error("❌ StockSubscriber 사용 불가")
            st.caption("KIS Client가 초기화되지 않음")

        st.markdown("---")

        # 전략 제어
        st.header("🎯 전략 제어")
        trading_engine = components['trading_engine']
        strategy = components['strategy']
        
        symbol = config.trading.get("infinite_buying_strategy", {}).get("symbol", "SOXL")
        strategy_name = f"infinite_buying_{symbol}"
        
        strategy_status = trading_engine.get_strategy_status(strategy_name)
        
        if strategy_status and strategy_status["active"]:
            if st.button("⏹️ 전략 중지", key="stop_strategy"):
                trading_engine.stop_strategy(strategy_name)
                st.success("전략이 중지되었습니다")
                st.rerun()
        else:
            if st.button("▶️ 전략 시작", key="start_strategy"):
                trading_engine.start_strategy(strategy_name)
                st.success("전략이 시작되었습니다")
                st.rerun()

        # 익절 설정
        st.header("익절 설정")
        st.write(f"**최대 익절률**: {strategy.params['max_profit_rate']}%")
        st.write(f"**최소 익절률**: {strategy.params['min_profit_rate']}%")

def render_trading_history_table(components):
    """거래 내역 테이블 렌더링"""
    st.header("📊 거래 내역 분석")
    
    strategy = components['strategy']
    
    # 조회 기간 설정
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("날짜별 거래 내역 및 성과 분석")
    
    with col2:
        # 조회 기간 선택
        days_options = {
            "최근 7일": 7,
            "최근 30일": 30,
            "최근 60일": 60,
            "전략 시작일부터": None  # None이면 전략 시작일부터 조회
        }
        
        selected_period = st.selectbox(
            "조회 기간",
            options=list(days_options.keys()),
            index=1  # 기본값: 최근 30일
        )
        
        days = days_options[selected_period]
    
    # 테이블 새로고침 버튼
    if st.button("🔄 거래 내역 새로고침", key="refresh_trading_history"):
        st.info("거래 내역을 조회 중입니다...")
    
    try:
        # 거래 내역 테이블 가져오기
        if days is None:
            # 전략 시작일부터 조회 (기본 90일 제한)
            logger.info(f"🔧 UI에서 전달받은 days 값: None (기본 90일 적용)")
            df = strategy.get_trading_history_table(days=90)
            logger.info(f"거래내역 테이블 조회 완료 (전체 기간): {len(df)}행")
        else:
            logger.info(f"🔧 UI에서 전달받은 days 값: {days}")
            df = strategy.get_trading_history_table(days=days)
            logger.info(f"거래내역 테이블 조회 완료 ({days}일): {len(df)}행")
        
        if df.empty:
            st.info("선택한 기간에 거래 내역이 없습니다.")
            return
        
        # 테이블 크기 및 테스트 모드 표시
        test_mode_status = "🧪 테스트 모드" if strategy.trade_history.test_mode else "🔴 실제 모드"
        st.success(f"📊 총 {len(df)}행의 거래 내역이 조회되었습니다. ({test_mode_status})")
        
        # 디버깅 정보 표시
        st.info(f"🔧 디버깅: 조회일수={days}, 테스트모드={strategy.trade_history.test_mode}, 심볼={strategy.symbol}")
        
        # 테이블 표시
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("날짜", width="medium"),
                "Close": st.column_config.TextColumn("종가", width="small"),
                "평단가": st.column_config.TextColumn("평단가", width="small"),
                "Star가격": st.column_config.TextColumn("Star가격", width="small"),
                "수량": st.column_config.NumberColumn("수량", width="small"),
                "수량변동": st.column_config.TextColumn("수량변동", width="small"),
                "실현손익($)": st.column_config.TextColumn("실현손익($)", width="medium"),
                "누적손익($)": st.column_config.TextColumn("누적손익($)", width="medium"),
                "누적투자액($)": st.column_config.TextColumn("누적투자액($)", width="medium"),
                "당일투자액($)": st.column_config.TextColumn("당일투자액($)", width="medium"),
                "잔고수익률": st.column_config.TextColumn("잔고수익률", width="medium"),
            }
        )
        
        # 요약 통계
        st.subheader("📈 거래 요약 통계")
        
        # 전체 거래 건수와 총 투자금액 계산
        total_rows = len(df)
        
        # 수량변동에서 매수/매도 건수 계산
        buy_trades = len([row for _, row in df.iterrows() if row["수량변동"] and "+" in str(row["수량변동"])])
        sell_trades = len([row for _, row in df.iterrows() if row["수량변동"] and "-" in str(row["수량변동"])])
        
        # 최신 데이터 (첫 번째 행)
        if not df.empty:
            latest_row = df.iloc[0]
            current_quantity = latest_row["수량"] if latest_row["수량"] else 0
            
            # 누적 손익 파싱 (달러 금액)
            cumulative_profit_str = latest_row["누적손익($)"]
            cumulative_profit = 0.0
            if cumulative_profit_str and cumulative_profit_str != "":
                try:
                    cumulative_profit = float(cumulative_profit_str.replace("$", ""))
                except:
                    cumulative_profit = 0.0
            
            # 누적 투자액 파싱 (달러)
            cumulative_investment_str = latest_row["누적투자액($)"]
            cumulative_investment = 0.0
            if cumulative_investment_str and cumulative_investment_str != "":
                try:
                    cumulative_investment = float(cumulative_investment_str.replace("$", "").replace(",", ""))
                except:
                    cumulative_investment = 0.0
        
        # 통계 표시
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "거래 일수",
                f"{total_rows}일",
                help="거래가 발생한 총 일수"
            )
        
        with col2:
            st.metric(
                "매수/매도 건수",
                f"{buy_trades}/{sell_trades}",
                help="매수 건수 / 매도 건수"
            )
        
        with col3:
            if not df.empty:
                st.metric(
                    "현재 보유수량",
                    f"{current_quantity}주",
                    help="현재 보유 중인 주식 수량"
                )
        
        with col4:
            if not df.empty:
                profit_delta = f"{cumulative_profit:+.2f}" if cumulative_profit != 0 else None
                st.metric(
                    "누적 실현손익",
                    f"${cumulative_profit:.2f}",
                    delta=profit_delta,
                    help="전체 투자 기간 누적 실현손익 (달러)"
                )
        
        # 추가 통계 정보
        if not df.empty and cumulative_investment > 0:
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                total_investment_amount = strategy.params["total_investment"]
                actual_investment = (cumulative_investment / 100) * total_investment_amount
                st.info(f"💰 **실제 투자금액**: {actual_investment:,.0f}원 ({cumulative_investment:.1f}%)")
            
            with col2:
                if current_quantity > 0:
                    avg_price_str = latest_row["평단가"]
                    if avg_price_str and avg_price_str != "":
                        try:
                            avg_price = float(avg_price_str.replace("$", ""))
                            current_value = current_quantity * strategy.position["current_price"]
                            st.info(f"📊 **현재 평가금액**: ${current_value:,.0f} (평단가: ${avg_price:.2f})")
                        except:
                            pass
        
        # 데이터 다운로드 옵션
        st.markdown("---")
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 CSV 파일로 다운로드",
            data=csv,
            file_name=f"{strategy.symbol}_trading_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="거래 내역 테이블을 CSV 파일로 다운로드합니다"
        )
        
    except Exception as e:
        st.error(f"거래 내역 테이블 로딩 중 오류가 발생했습니다: {str(e)}")
        logger.error(f"거래 내역 테이블 렌더링 오류: {str(e)}")

def render_position_info(components):
    """포지션 정보 렌더링"""
    st.header("현재 포지션")
    
    strategy = components['strategy']
    status = strategy.get_status()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "보유수량",
            f"{status['position']['quantity']:,}주",
            delta=None
        )
    
    with col2:
        st.metric(
            "평균단가",
            f"${status['position']['avg_price']:.2f}",
            delta=None
        )
    
    with col3:
        st.metric(
            "현재가",
            f"${status['position']['current_price']:.2f}",
            delta=f"{status['profit_ratio']:.2f}%" if status['profit_ratio'] != 0 else None
        )
    
    with col4:
        total_value = status['position']['quantity'] * status['position']['current_price']
        st.metric(
            "평가금액",
            f"${total_value:,.0f}",
            delta=None
        )

def render_strategy_progress(components):
    """전략 진행 상황 렌더링"""
    st.header("전략 진행 상황")
    
    strategy = components['strategy']
    status = strategy.get_status()
    params = status['calculated_params']
    
    if params:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "현재회차 (T)",
                f"{params.get('current_round', 0)}회",
                delta=None
            )
            
        with col2:
            progress = params.get('progress_ratio', 0)
            st.metric(
                "진행비율",
                f"{progress:.1f}%",
                delta=None
            )
            st.progress(progress / 100)
            
        with col3:
            st.metric(
                "실투자비율",
                f"{params.get('actual_investment_ratio', 0):.1f}%",
                delta=None
            )

def render_order_info(components):
    """주문 정보 렌더링"""
    st.header("예약 주문")
    
    strategy = components['strategy']
    status = strategy.get_status()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("매수 주문")
        buy_orders = status['orders'].get('buy', [])
        if buy_orders:
            for order in buy_orders:
                st.write(f"- {order['type']}: ${order['price']:.2f} x {order['quantity']}주")
        else:
            st.info("예약된 매수 주문이 없습니다.")
    
    with col2:
        st.subheader("매도 주문")
        sell_orders = status['orders'].get('sell', [])
        if sell_orders:
            for order in sell_orders:
                st.write(f"- {order['type']}: ${order['price']:.2f} x {order['quantity']}주")
        else:
            st.info("예약된 매도 주문이 없습니다.")

def render_calculated_params(components):
    """계산된 파라메터 표시"""
    st.header("계산된 파라메터")
    
    strategy = components['strategy']
    params = strategy.calculated_params
    
    if params:
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Star가격**: ${params.get('star_price', 0):.2f}")
            st.write(f"**Star수량**: {params.get('star_quantity', 0)}주")
            st.write(f"**Star가격비율**: {params.get('star_price_ratio', 0):.2f}%")
        
        with col2:
            st.write(f"**익절가격**: ${params.get('profit_price', 0):.2f}")
            st.write(f"**익절비율**: {params.get('profit_ratio', 0):.2f}%")
            st.write(f"**평단매수수량**: {params.get('avg_buy_quantity', 0)}주")

def render_logs():
    """로그 표시"""
    st.header("시스템 로그")
    
    log_file = "logs/application.log"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]  # 최근 20줄
            log_text = "".join(lines)
            st.text_area("로그", value=log_text, height=200)
    else:
        st.info("로그 파일이 없습니다.")

def main():
    """메인 함수"""
    # 페이지 설정
    setup_page()
    
    # 애플리케이션 초기화
    components = initialize_application()
    
    if not components:
        st.error("애플리케이션 초기화에 실패했습니다.")
        st.stop()
        return
    
    # UI 렌더링
    render_header()
    render_sidebar(components)
    
    # 메인 컨텐츠
    render_position_info(components)
    st.markdown("---")
    
    render_strategy_progress(components)
    st.markdown("---")
    
    # 거래 내역 테이블 추가
    render_trading_history_table(components)
    st.markdown("---")
    
    render_order_info(components)
    st.markdown("---")
    
    render_calculated_params(components)
    st.markdown("---")
    
    render_logs()
    
    # 자동 새로고침 (5초마다)
    if st.button("새로고침"):
        st.rerun()

if __name__ == "__main__":
    main() 