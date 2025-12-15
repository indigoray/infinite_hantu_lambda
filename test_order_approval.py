#!/usr/bin/env python3
"""
주문 승인 시스템 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.utils.telegram import TelegramHandler
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_order_approval():
    """주문 승인 시스템 테스트"""
    print("🔐 주문 승인 시스템 테스트 시작")
    
    # 설정 로드
    try:
        config = Config()
        telegram_config = config.get_telegram_config()
        
        if not telegram_config.get("enabled", False):
            print("❌ 텔레그램이 비활성화되어 있습니다.")
            print("config.yaml에서 telegram.enabled: true로 설정하세요.")
            return False
            
        print(f"✅ 텔레그램 설정 로드 완료")
        print(f"   - 토큰: {telegram_config['token'][:20]}...")
        print(f"   - 채팅 ID: {telegram_config['chat_id']}")
        
    except Exception as e:
        print(f"❌ 설정 로드 실패: {e}")
        return False
    
    # 텔레그램 핸들러 초기화
    try:
        telegram = TelegramHandler(telegram_config)
        print("✅ 텔레그램 핸들러 초기화 완료")
        
        # 폴링 모드로 강제 시작 (웹훅 대신)
        telegram._start_polling()
        print("✅ 폴링 모드 시작됨")
        
    except Exception as e:
        print(f"❌ 텔레그램 핸들러 초기화 실패: {e}")
        return False
    
    # 테스트 주문 생성
    test_orders = [
        {
            "action": "BUY",
            "symbol": "SOXL",
            "quantity": 100,
            "price": 25.50,
            "order_type": "MARKET"
        },
        {
            "action": "BUY", 
            "symbol": "SOXL",
            "quantity": 50,
            "price": 24.80,
            "order_type": "LIMIT"
        }
    ]
    
    # 승인 콜백 함수
    def approval_callback(approved: bool, orders: list):
        if approved:
            print("✅ 주문이 승인되었습니다!")
            print("실행할 주문들:")
            for i, order in enumerate(orders, 1):
                print(f"  {i}. {order['action']} {order['symbol']} {order['quantity']}주 @ ${order['price']}")
        else:
            print("❌ 주문이 거부되었습니다.")
    
    # 주문 승인 요청
    print("\n📤 주문 승인 요청 전송 중...")
    order_id = telegram.request_order_approval(test_orders, approval_callback, timeout=60)
    
    if order_id:
        print(f"✅ 승인 요청 전송 완료 (주문 ID: {order_id})")
        print("📱 텔레그램에서 승인/거부 버튼을 눌러주세요.")
        print("⏰ 60초 후 자동으로 타임아웃됩니다.")
        print("🔄 폴링 모드로 응답을 확인 중...")
        
        # 대기
        try:
            time.sleep(65)  # 타임아웃 + 5초 여유
        except KeyboardInterrupt:
            print("\n⏹ 테스트 중단됨")
        
    else:
        print("❌ 승인 요청 전송 실패")
        return False
    
    # 정리
    try:
        telegram.stop()
        print("✅ 텔레그램 핸들러 정리 완료")
    except Exception as e:
        print(f"⚠️ 정리 중 오류: {e}")
    
    return True

def test_simple_message():
    """간단한 메시지 전송 테스트"""
    print("\n📤 간단한 메시지 전송 테스트")
    
    try:
        config = Config()
        telegram = TelegramHandler(config.get_telegram_config())
        
        success = telegram.send_message("🧪 주문 승인 시스템 테스트 메시지입니다.")
        
        if success:
            print("✅ 메시지 전송 성공")
            return True
        else:
            print("❌ 메시지 전송 실패")
            return False
            
    except Exception as e:
        print(f"❌ 메시지 전송 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🔐 주문 승인 시스템 테스트")
    print("=" * 50)
    
    # 1. 간단한 메시지 테스트
    if not test_simple_message():
        print("\n❌ 기본 메시지 전송이 실패했습니다.")
        print("텔레그램 설정을 확인해주세요.")
        sys.exit(1)
    
    # 2. 주문 승인 시스템 테스트
    print("\n" + "=" * 50)
    print("🔐 주문 승인 시스템 테스트")
    print("=" * 50)
    
    if test_order_approval():
        print("\n✅ 모든 테스트가 완료되었습니다!")
    else:
        print("\n❌ 테스트 중 오류가 발생했습니다.")
        sys.exit(1) 