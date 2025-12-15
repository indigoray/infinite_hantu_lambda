#!/usr/bin/env python3
"""
거래내역 테이블 테스트 스크립트

Usage:
    python test_trade_history.py
"""

import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트 디렉터리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.strategy.trade_history import TradeHistory
from src.config import Config


def test_trade_history_table():
    """거래내역 테이블 테스트"""
    print("🧪 거래내역 테이블 테스트 시작")
    
    # 가상 설정 생성
    mock_params = {
        "total_investment": 1000000,  # 100만원
        "division_count": 40,
        "max_profit_rate": 12,
        "min_profit_rate": 8,
        "star_adjustment_rate": 0
    }
    
    # TradeHistory 인스턴스 생성 (테스트 모드)
    trade_history = TradeHistory(
        kis_client=None,  # 테스트 모드에서는 불필요
        symbol="SOXL",
        strategy_params=mock_params,
        test_mode=True  # 테스트 모드 활성화
    )
    
    # 30일간의 거래내역 테이블 생성
    print("\n📊 30일간 거래내역 테이블 생성 중...")
    start_date = (datetime.now() - timedelta(days=30)).date()
    
    df = trade_history.get_trading_history_table(days=30)
    
    if df.empty:
        print("❌ 테이블 생성 실패 - 데이터가 없습니다.")
        return False
    
    print(f"✅ 테이블 생성 성공! 총 {len(df)}행의 데이터")
    print("\n📋 거래내역 테이블 (상위 10행):")
    print("=" * 120)
    print(df.head(10).to_string(index=False))
    print("=" * 120)
    
    # 테이블 컬럼 확인
    expected_columns = [
        "Date", "Close", "평단가", "Star가격", "수량", 
        "수량변동", "실현손익($)", "누적손익($)", 
        "누적투자액($)", "당일투자액($)", "잔고수익률"
    ]
    
    print(f"\n🔍 컬럼 확인:")
    for col in expected_columns:
        if col in df.columns:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} (누락)")
    
    print(f"\n실제 컬럼: {list(df.columns)}")
    
    # 실제 데이터 샘플 표시
    if not df.empty:
        print(f"\n📈 최신 데이터 (마지막 5행):")
        print(df.tail(5).to_string(index=False))
        
        # 누적손익 확인
        if "누적손익($)" in df.columns:
            profit_data = df[df["누적손익($)"] != ""]
            if not profit_data.empty:
                latest_profit = profit_data["누적손익($)"].iloc[-1]
                print(f"\n💰 최종 누적손익: {latest_profit}")
                
        # 누적투자액 확인 (달러 기준)
        if "누적투자액($)" in df.columns:
            investment_data = df[df["누적투자액($)"] != ""]
            if not investment_data.empty:
                latest_investment = investment_data["누적투자액($)"].iloc[-1]
                print(f"📊 최종 누적투자액: {latest_investment}")
    
    return True


def test_with_config():
    """설정 파일을 이용한 테스트"""
    print("\n🔧 설정 파일 기반 테스트")
    
    try:
        # 설정 로드
        config = Config()
        strategy_config = config.trading.get("infinite_buying_strategy", {})
        
        print(f"설정된 테스트 모드: {strategy_config.get('trade_history_test_mode', False)}")
        print(f"설정된 심볼: {strategy_config.get('symbol', 'SOXL')}")
        print(f"설정된 총투자금: {strategy_config.get('total_investment', 1000000):,}원")
        
        return True
        
    except Exception as e:
        print(f"❌ 설정 파일 테스트 실패: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TradeHistory 테스트 스크립트")
    print("=" * 60)
    
    # 기본 테이블 테스트
    success1 = test_trade_history_table()
    
    print("\n" + "=" * 60)
    
    # 설정 파일 테스트
    success2 = test_with_config()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✅ 모든 테스트 통과!")
    else:
        print("❌ 일부 테스트 실패")
    print("=" * 60) 