"""
무한매수 전략 시스템 레이아웃 템플릿
"""

import streamlit as st
from typing import Dict, Any, Optional

def setup_basic_layout():
    """기본 페이지 레이아웃 설정"""
    st.set_page_config(
        page_title="무한매수 전략 시스템",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://github.com/your-repo/issues',
            'Report a bug': "https://github.com/your-repo/issues",
            'About': """
            # 무한매수 전략 자동화 시스템
            
            한국투자증권 API를 이용한 SOXL 자동 거래 시스템입니다.
            
            ## 주요 기능
            - 무한매수 전략 자동 실행
            - 실시간 포지션 모니터링
            - 수익률 분석 및 차트
            - 텔레그램 알림
            
            ## 개발자
            라오어의 무한매수 전략
            """
        }
    )

def create_dashboard_layout():
    """대시보드 레이아웃"""
    # 헤더
    st.title("📈 무한매수 전략 대시보드")
    st.markdown("---")
    
    # 메트릭 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 수익률", "12.5%", "2.1%")
    with col2:
        st.metric("보유 포지션", "3", "-1")
    with col3:
        st.metric("일일 거래량", "1,234", "123")
    with col4:
        st.metric("계좌 잔고", "$50,000", "$2,500")
    
    # 메인 콘텐츠 영역
    col1, col2 = st.columns([2, 1])
    return col1, col2

def create_sidebar_layout():
    """사이드바 레이아웃"""
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        # 전략 설정
        st.subheader("전략 설정")
        strategy_enabled = st.checkbox("전략 활성화", value=True)
        auto_trading = st.checkbox("자동 거래", value=True)
        
        # 거래 설정
        st.subheader("거래 설정")
        buy_amount = st.number_input("매수 금액 ($)", min_value=100, value=1000, step=100)
        profit_target = st.slider("수익 목표 (%)", 1, 50, 10)
        stop_loss = st.slider("손절 기준 (%)", 1, 30, 15)
        
        # 알림 설정
        st.subheader("알림 설정")
        telegram_enabled = st.checkbox("텔레그램 알림", value=True)
        email_enabled = st.checkbox("이메일 알림", value=False)
        
        return {
            'strategy_enabled': strategy_enabled,
            'auto_trading': auto_trading,
            'buy_amount': buy_amount,
            'profit_target': profit_target,
            'stop_loss': stop_loss,
            'telegram_enabled': telegram_enabled,
            'email_enabled': email_enabled
        }

def create_trading_layout():
    """거래 화면 레이아웃"""
    st.header("💼 거래 관리")
    
    # 거래 상태
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("현재 포지션")
        # 포지션 정보
    with col2:
        st.subheader("거래 내역")
        # 거래 내역
    with col3:
        st.subheader("주문 관리")
        # 주문 관리
    
    # 차트 영역
    st.subheader("📊 차트 분석")
    chart_col1, chart_col2 = st.columns([3, 1])
    return chart_col1, chart_col2

def create_analysis_layout():
    """분석 화면 레이아웃"""
    st.header("📊 전략 분석")
    
    # 탭 레이아웃
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 수익률 분석", 
        "💰 포트폴리오", 
        "📊 백테스팅", 
        "⚙️ 설정"
    ])
    
    return tab1, tab2, tab3, tab4

def create_settings_layout():
    """설정 화면 레이아웃"""
    st.header("⚙️ 시스템 설정")
    
    # 설정 탭
    tab1, tab2, tab3 = st.tabs(["🔐 API 설정", "📊 거래 설정", "🔔 알림 설정"])
    
    with tab1:
        st.subheader("한국투자증권 API 설정")
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")
        account_number = st.text_input("계좌번호")
        
    with tab2:
        st.subheader("거래 전략 설정")
        symbol = st.selectbox("거래 종목", ["SOXL", "TQQQ", "SPXL"])
        strategy_type = st.selectbox("전략 유형", ["무한매수", "DCA", "모멘텀"])
        
    with tab3:
        st.subheader("알림 설정")
        telegram_token = st.text_input("텔레그램 봇 토큰", type="password")
        chat_id = st.text_input("채팅 ID")
        
    return {
        'api_key': api_key,
        'api_secret': api_secret,
        'account_number': account_number,
        'symbol': symbol,
        'strategy_type': strategy_type,
        'telegram_token': telegram_token,
        'chat_id': chat_id
    }

def create_mobile_friendly_layout():
    """모바일 친화적 레이아웃"""
    st.set_page_config(
        page_title="무한매수 전략",
        page_icon="📈",
        layout="centered",  # 모바일에서는 centered가 더 좋음
        initial_sidebar_state="collapsed"  # 모바일에서는 접힌 상태
    )
    
    # 모바일 최적화 CSS
    st.markdown("""
    <style>
    @media (max-width: 768px) {
        .stMetric {
            font-size: 0.8rem;
        }
        .stButton > button {
            width: 100%;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def create_professional_layout():
    """전문적인 대시보드 레이아웃"""
    # 커스텀 CSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .chart-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 헤더
    st.markdown('<div class="main-header"><h1>📈 무한매수 전략 시스템</h1></div>', unsafe_allow_html=True)
    
    # 메트릭 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("총 수익률", "12.5%", "2.1%")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("보유 포지션", "3", "-1")
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("일일 거래량", "1,234", "123")
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("계좌 잔고", "$50,000", "$2,500")
        st.markdown('</div>', unsafe_allow_html=True)

def get_layout_template(template_name: str) -> Dict[str, Any]:
    """레이아웃 템플릿 반환"""
    templates = {
        'basic': setup_basic_layout,
        'dashboard': create_dashboard_layout,
        'sidebar': create_sidebar_layout,
        'trading': create_trading_layout,
        'analysis': create_analysis_layout,
        'settings': create_settings_layout,
        'mobile': create_mobile_friendly_layout,
        'professional': create_professional_layout
    }
    
    return templates.get(template_name, setup_basic_layout) 