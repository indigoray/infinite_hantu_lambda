import logging
import logging.handlers
from pathlib import Path
import os
from datetime import datetime

def setup_logger():
    """애플리케이션 전체 로깅 설정"""
    
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 로그 파일명 설정 (날짜별)
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"app_{today}.log"
    
    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러 설정 (일별 로그 파일)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Streamlit UI 전용 로그 파일 설정
    streamlit_log = log_dir / "streamlit_ui.log"
    streamlit_handler = logging.FileHandler(streamlit_log, encoding='utf-8')
    streamlit_handler.setLevel(logging.INFO)
    streamlit_handler.setFormatter(file_formatter)
    
    # 전략 실행 로그 파일 설정
    strategy_log = log_dir / "strategy.log"
    strategy_handler = logging.FileHandler(strategy_log, encoding='utf-8')
    strategy_handler.setLevel(logging.INFO)
    strategy_handler.setFormatter(file_formatter)
    
    # 기존 핸들러 제거 후 새로운 핸들러 추가
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Streamlit UI 로거 설정
    streamlit_logger = logging.getLogger('streamlit')
    streamlit_logger.handlers.clear()
    streamlit_logger.addHandler(streamlit_handler)
    
    # 전략 로거 설정
    strategy_logger = logging.getLogger('strategy')
    strategy_logger.handlers.clear()
    strategy_logger.addHandler(strategy_handler)
    
    logger.info("Logger setup completed") 