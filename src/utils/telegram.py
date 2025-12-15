import logging
import requests
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TelegramHandler:
    """텔레그램 메시지 전송 핸들러 (기본 기능만)
    
    주문 승인 기능은 telegram_handler.py로 이동됨
    """
    
    def __init__(self, config: dict):
        """텔레그램 핸들러 초기화
        
        Args:
            config: 텔레그램 설정 (token, chat_id 포함)
        """
        self.enabled = config.get("enabled", False)
        self.token = config.get("token")
        self.chat_id = config.get("chat_id")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        if self.enabled and (not self.token or not self.chat_id):
            logger.error("텔레그램 설정이 올바르지 않습니다.")
            self.enabled = False
            
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """텔레그램 메시지 전송
        
        Args:
            text: 전송할 메시지
            parse_mode: 메시지 파싱 모드 (HTML, Markdown)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.enabled:
            logger.debug(f"텔레그램 비활성화 상태: {text}")
            return False
            
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.debug(f"텔레그램 메시지 전송 성공: {text[:50]}...")
                return True
            else:
                logger.error(f"텔레그램 메시지 전송 실패: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 오류: {str(e)}")
            return False
            
    def send_error(self, title: str, error: str):
        """오류 메시지 전송
        
        Args:
            title: 오류 제목
            error: 오류 내용
        """
        message = f"❌ <b>{title}</b>\n\n{error}"
        self.send_message(message)
        
    def send_trade_alert(self, action: str, symbol: str, quantity: int, price: float):
        """거래 알림 전송
        
        Args:
            action: 거래 유형 (BUY/SELL)
            symbol: 종목 코드
            quantity: 수량
            price: 가격
        """
        emoji = "🟢" if action == "BUY" else "🔴"
        message = f"{emoji} <b>{action}</b> {symbol}\n"
        message += f"수량: {quantity}주\n"
        message += f"가격: ${price:.2f}"
        
        self.send_message(message)
        
    def send_strategy_status(self, strategy_name: str, status: dict):
        """전략 상태 전송
        
        Args:
            strategy_name: 전략 이름
            status: 상태 정보 딕셔너리
        """
        message = f"📊 <b>{strategy_name} 상태</b>\n\n"
        
        # 포지션 정보
        position = status.get('position', {})
        if position.get('quantity', 0) > 0:
            message += f"보유: {position['quantity']}주 @ ${position['avg_price']:.2f}\n"
            message += f"현재가: ${position['current_price']:.2f}\n"
            
            profit_loss = (position['current_price'] - position['avg_price']) * position['quantity']
            profit_loss_pct = ((position['current_price'] / position['avg_price']) - 1) * 100
            
            emoji = "🟢" if profit_loss >= 0 else "🔴"
            message += f"{emoji} 손익: ${profit_loss:,.2f} ({profit_loss_pct:+.2f}%)\n\n"
        
        # 거래 통계
        stats = status.get('stats', {})
        if stats:
            message += f"총 거래: {stats.get('total_trades', 0)}회\n"
            message += f"총 손익: ${stats.get('total_pnl', 0):,.2f}\n"
            
        self.send_message(message) 