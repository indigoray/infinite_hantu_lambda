import streamlit as st
import time
import sys
from pathlib import Path
import os

# 프로젝트 루트 경로 추가
ROOT_DIR = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(ROOT_DIR))

from src_rev.infrastructure.persistence.json_repo import StateRepository
from src_rev.presentation.view_models import DashboardViewModel

# Page Config
st.set_page_config(
    page_title="Infinite Hantu Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일링
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .status-active { color: #00FF00; font-weight: bold; }
    .status-inactive { color: #FF4444; font-weight: bold; }
    .big-font { font-size: 24px !important; }
</style>
""", unsafe_allow_html=True)

def load_data():
    """상태 파일 로드"""
    repo_path = ROOT_DIR / "states" / "revised_state.json"
    repo = StateRepository(str(repo_path))
    return repo.load()

def main():
    st.title("Infinite Hantu Revised 🚀")
    st.markdown("---")

    # 1. 데이터 로드
    state = load_data()
    vm = DashboardViewModel.format_state(state)
    
    # 2. 상단 상태 요약 (Metrics)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("종목 (Symbol)", vm["symbol"])
    
    with col2:
        st.metric("누적 수익 (Profit)", vm["profit"])
        
    with col3:
        st.metric("최근 실행", vm["last_run"])
        
    with col4:
        st.metric("오늘 상태", vm["today_action"])

    # 3. 상세 상태 패널
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("📊 현재 사이클 상태")
        with st.container():
            st.markdown(f"""
            - **상태**: {vm['status_text']}
            - **사이클 ID**: `{vm['cycle_id']}`
            - **시작일**: {vm['start_date']}
            """)
            
            # 진행률 바 (예시)
            # st.progress(50)
            
    with col_right:
        st.subheader("⚙️ 시스템 제어")
        st.info("💡 봇 제어는 텔레그램을 이용해주세요.")
        
        if st.button("🔄 새로고침"):
            st.rerun()
            
    # 4. 자동 새로고침 (옵션)
    if st.checkbox("실시간 새로고침 (10초)", value=True):
        time.sleep(10)
        st.rerun()

if __name__ == "__main__":
    main()
