#!/usr/bin/env python3
"""
StockSubscriber 종목별 로깅 기능 테스트 (종목 검색 기능 포함)
"""

import sys
import os
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.stock_subscriber import StockSubscriber
from unittest.mock import Mock
import random

def test_stock_subscriber_logging():
    """StockSubscriber 종목별 로깅 및 종목 검색 테스트"""
    
    # Mock KIS Client 생성 - 한국 주식과 미국 주식용
    mock_client = Mock()
    
    # 삼성전자 가격 시뮬레이션 (70,000원 기준으로 변동)
    samsung_base_price = 70000
    def mock_samsung_price():
        # ±1% 범위에서 랜덤 변동
        variation = random.uniform(-0.01, 0.01)
        return samsung_base_price * (1 + variation)
    
    # 네이버 가격 시뮬레이션 (180,000원 기준으로 변동)
    naver_base_price = 180000
    def mock_naver_price():
        # ±1.5% 범위에서 랜덤 변동
        variation = random.uniform(-0.015, 0.015)
        return naver_base_price * (1 + variation)
    
    # 미국 주식 가격 시뮬레이션
    us_base_price = 45.67
    def mock_us_price():
        # ±0.5% 범위에서 랜덤 변동
        variation = random.uniform(-0.005, 0.005)
        return us_base_price * (1 + variation)
    
    # Mock 메서드 설정
    def mock_domestic_price(symbol):
        if symbol == "005930":  # 삼성전자
            return {"current_price": mock_samsung_price()}
        elif symbol == "035420":  # 네이버
            return {"current_price": mock_naver_price()}
        else:
            return {"current_price": 0}
    
    mock_client.get_domestic_stock_price = Mock(side_effect=mock_domestic_price)
    mock_client.get_oversea_stock_price = Mock(side_effect=lambda symbol: {
        "current_price": mock_us_price()
    })
    
    # StockSubscriber 생성 (1초 간격으로 설정)
    subscriber = StockSubscriber(mock_client, monitoring_interval=1)
    
    print("=== StockSubscriber 종목 검색 및 로깅 테스트 (1초 간격) ===")
    print(f"시작 시간: {datetime.now()}")
    
    # 종목 마스터 초기화 상태 확인
    if subscriber.stock_master_cache:
        print(f"📊 종목 마스터 로드 완료: {len(subscriber.stock_master_cache)}개 종목")
        
        # 몇 개 종목 예시 출력
        sample_stocks = list(subscriber.stock_master_cache.items())[:5]
        print("   예시 종목:")
        for code, name in sample_stocks:
            print(f"     {code}: {name}")
    else:
        print("⚠️ 종목 마스터를 사용할 수 없어 종목코드로만 동작합니다")
    
    print("\n🔍 종목 검색 테스트:")
    
    # 다양한 방식으로 종목 구독 테스트
    test_queries = [
        ("005930", "kr"),      # 삼성전자 - 종목코드로
        ("삼성전자", "kr"),      # 삼성전자 - 회사명으로 (마스터 데이터가 있는 경우)
        ("035420", "kr"),      # 네이버 - 종목코드로
        ("네이버", "kr"),        # 네이버 - 회사명으로 (마스터 데이터가 있는 경우)
        ("SOXL", "us"),        # SOXL (미국)
        ("QQQ", "us")          # QQQ (미국)
    ]
    
    subscribed_symbols = []
    
    for query, market in test_queries:
        try:
            if market == "kr":
                # 검색 결과 미리 확인
                symbol, company_name = subscriber.search_stock(query)
                print(f"   🔍 '{query}' → {company_name}({symbol})")
            
            subscriber.subscribe(query, market)
            subscribed_symbols.append((query, market))
            
        except Exception as e:
            print(f"   ❌ '{query}' 구독 실패: {e}")
    
    print("\n📁 기존 로그 파일들:")
    if os.path.exists("price_logging"):
        for file in sorted(os.listdir("price_logging")):
            if file.endswith(".log"):
                print(f"   📄 {file}")
    
    # 실시간 모니터링 시작
    print(f"\n🚀 실시간 모니터링 시작 (10초간 1초 간격으로 실행)")
    print("📊 모니터링 대상 (회사명으로 표시):")
    for symbol, info in subscriber.subscribed_symbols.items():
        display_name = info.get("display_name", symbol)
        market = info.get("market", "unknown")
        print(f"   {'🇰🇷' if market == 'kr' else '🇺🇸'} {display_name}({symbol})")
    
    subscriber.start()
    
    # 10초 동안 실행
    print("\n⏱️  모니터링 중...")
    for i in range(10):
        print(f"   {i+1}초 경과...")
        time.sleep(1)
    
    # 모니터링 중지
    print("\n🛑 모니터링 중지")
    subscriber.stop()
    
    # 결과 확인 - 새로 생성된 파일만 확인
    print("\n📊 로깅 결과 확인:")
    if os.path.exists("price_logging"):
        current_time_str = datetime.now().strftime("%Y%m%d_%H%M")
        recent_files = []
        
        for file in sorted(os.listdir("price_logging")):
            if file.endswith(".log") and current_time_str[:11] in file:
                recent_files.append(file)
        
        print(f"📝 최근 생성된 로그 파일들 ({len(recent_files)}개):")
        for file in recent_files:
            file_path = os.path.join("price_logging", file)
            file_size = os.path.getsize(file_path)
            
            print(f"\n   📄 {file}")
            print(f"      📁 파일 크기: {file_size} bytes")
            
            # 파일 내용 분석
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"      📋 총 {len(lines)}줄")
                    
                    # 실제 가격 데이터 계산 (헤더 5줄 + 종료 메시지 1줄 제외)
                    price_data_count = max(0, len(lines) - 6)
                    if price_data_count > 0:
                        print(f"      💰 실제 가격 데이터: {price_data_count}개")
                        
                        # 가격 데이터가 있는 첫 번째와 마지막 로그 출력
                        print("      📈 가격 변동 샘플:")
                        count = 0
                        for line in lines:
                            if "|" in line and "$" in line and "===" not in line and "로그 형식" not in line:
                                print(f"         {line.strip()}")
                                count += 1
                                if count >= 2:  # 처음 2개만 표시
                                    break
                        
                        if price_data_count > 2:
                            print("         ...")
                            # 마지막 가격 데이터 찾기
                            for line in reversed(lines):
                                if "|" in line and "$" in line and "===" not in line and "로그 형식" not in line:
                                    print(f"         {line.strip()}")
                                    break
                    else:
                        print("      🌙 장시간 외 또는 데이터 없음")
                        
            except Exception as e:
                print(f"      ❌ 파일 읽기 오류: {e}")
    
    print("\n✅ 테스트 완료!")
    print("\n📋 확인 사항:")
    print("1. 종목 마스터 데이터 로드 및 검색 기능 동작 여부")
    print("2. 회사명으로 로그 파일이 생성되었는지 확인 (예: 삼성전자_날짜.log)")
    print("3. 종목코드와 회사명 모두로 구독이 가능한지 확인")
    print("4. 로그 내용에 회사명이 표시되는지 확인")
    print("5. 한국 주식은 회사명, 해외 주식은 티커로 구분 표시되는지 확인")

if __name__ == "__main__":
    test_stock_subscriber_logging() 