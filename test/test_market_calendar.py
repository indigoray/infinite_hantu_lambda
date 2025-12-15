#!/usr/bin/env python3
"""
마켓 캘린더 기능 테스트 스크립트

사용법:
python test_market_calendar.py
"""

import sys
import os
from datetime import datetime, date

# 프로젝트 루트 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.market_calendar import market_calendar

def test_market_calendar():
    """마켓 캘린더 기능 테스트"""
    print("🔍 마켓 캘린더 기능 테스트\n")
    
    # 1. 현재 시장 상태 확인
    print("=" * 50)
    print("📊 현재 시장 상태")
    print("=" * 50)
    
    us_status = market_calendar.get_market_status("us")
    kr_status = market_calendar.get_market_status("kr")
    
    print(f"🇺🇸 미국 시장:")
    print(f"   상태: {'🟢 OPEN' if us_status['is_open'] else '🔴 CLOSED'}")
    print(f"   현재 시간: {us_status['current_time']}")
    print(f"   공휴일 여부: {'예' if us_status['is_holiday'] else '아니오'}")
    print(f"   조기 마감일 여부: {'예' if us_status['is_early_close'] else '아니오'}")
    print()
    
    print(f"🇰🇷 한국 시장:")
    print(f"   상태: {'🟢 OPEN' if kr_status['is_open'] else '🔴 CLOSED'}")
    print(f"   현재 시간: {kr_status['current_time']}")
    print()
    
    # 2. 거래시간 정보
    print("=" * 50)
    print("⏰ 거래시간 정보")
    print("=" * 50)
    
    us_hours = market_calendar.get_market_hours("us")
    print("🇺🇸 미국 시장 거래시간 (EST):")
    for session, times in us_hours.items():
        print(f"   {session}: {times['start']} - {times['end']}")
    print()
    
    kr_hours = market_calendar.get_market_hours("kr")
    print("🇰🇷 한국 시장 거래시간 (KST):")
    for session, times in kr_hours.items():
        print(f"   {session}: {times['start']} - {times['end']}")
    print()
    
    # 3. 향후 공휴일 확인
    print("=" * 50)
    print("📅 향후 공휴일 (30일 내)")
    print("=" * 50)
    
    # 미국 공휴일
    print("🇺🇸 미국 공휴일:")
    us_upcoming_holidays = market_calendar.get_upcoming_holidays(30, "us")
    if us_upcoming_holidays:
        for holiday in us_upcoming_holidays:
            print(f"   📅 {holiday['date']}: {holiday['name']}")
            if holiday['is_early_close']:
                print("      ⏰ 전날 조기 마감")
    else:
        print("   향후 30일 내 미국 공휴일이 없습니다.")
    print()
    
    # 한국 공휴일
    print("🇰🇷 한국 공휴일:")
    kr_upcoming_holidays = market_calendar.get_upcoming_holidays(30, "kr")
    if kr_upcoming_holidays:
        for holiday in kr_upcoming_holidays:
            print(f"   📅 {holiday['date']}: {holiday['name']}")
    else:
        print("   향후 30일 내 한국 공휴일이 없습니다.")
    print()
    
    # 4. 특정 날짜 테스트
    print("=" * 50)
    print("🧪 특정 날짜 테스트")
    print("=" * 50)
    
    # 미국 시장 테스트
    print("🇺🇸 미국 시장:")
    us_test_dates = [
        date(2025, 1, 1),   # 신정
        date(2025, 7, 4),   # 독립기념일
        date(2025, 12, 25), # 크리스마스
        date(2025, 7, 3),   # 조기 마감일 전날
    ]
    
    for test_date in us_test_dates:
        is_holiday = market_calendar.is_market_holiday(test_date, "us")
        is_early_close = market_calendar.is_early_close_day(test_date)
        
        status = []
        if is_holiday:
            status.append("공휴일")
        if is_early_close:
            status.append("조기 마감일")
        if not status:
            status.append("정규 거래일")
            
        print(f"   {test_date}: {', '.join(status)}")
    print()
    
    # 한국 시장 테스트
    print("🇰🇷 한국 시장:")
    kr_test_dates = [
        date(2025, 1, 1),   # 신정
        date(2025, 3, 1),   # 삼일절
        date(2025, 5, 5),   # 어린이날
        date(2025, 8, 15),  # 광복절
        date(2025, 10, 3),  # 개천절
        date(2025, 12, 25), # 크리스마스
    ]
    
    for test_date in kr_test_dates:
        is_holiday = market_calendar.is_market_holiday(test_date, "kr")
        
        status = "공휴일" if is_holiday else "정규 거래일"
        print(f"   {test_date}: {status}")
    print()
    
    # 5. Trading Calendar API 테스트 (선택사항)
    print("=" * 50)
    print("🌐 Trading Calendar API 테스트")
    print("=" * 50)
    
    # 미국 거래소 (NYSE) 테스트
    print("🇺🇸 NYSE (XNYS) API 테스트:")
    try:
        us_api_data = market_calendar.get_trading_calendar_api("XNYS")
        if us_api_data:
            print("   ✅ NYSE API 연결 성공")
            print(f"   데이터 미리보기: {str(us_api_data)[:100]}...")
        else:
            print("   ❌ NYSE API 응답 없음")
    except Exception as e:
        print(f"   ⚠️ NYSE API 오류: {e}")
    print()
    
    # 한국 거래소 (KRX) 테스트
    print("🇰🇷 KRX (XKRX) API 테스트:")
    try:
        kr_api_data = market_calendar.get_trading_calendar_api("XKRX")
        if kr_api_data:
            print("   ✅ KRX API 연결 성공")
            print(f"   데이터 미리보기: {str(kr_api_data)[:100]}...")
        else:
            print("   ❌ KRX API 응답 없음")
    except Exception as e:
        print(f"   ⚠️ KRX API 오류: {e}")
    print()
    
    print("🎉 마켓 캘린더 테스트 완료!")

if __name__ == "__main__":
    test_market_calendar() 