import logging
import time
import threading
import requests
import json
from datetime import datetime
from typing import Dict, Callable
from dataclasses import dataclass
from telegram import Bot
from telegram.error import TelegramError
from src.utils.event_bus import EventBus, Event, EventType
from rx import operators as ops
from rx.scheduler import ThreadPoolScheduler
from concurrent.futures import ThreadPoolExecutor
import asyncio
import httpx

logger = logging.getLogger(__name__)

@dataclass
class OrderApproval:
    """주문 승인 대기 정보"""
    order_id: str
    orders: list
    callback: Callable
    timeout: int = 300
    approved: bool = None
    message_id: int = None

class telegram_handler:
    def __init__(self, token: str, chat_id: str, event_bus: EventBus):
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.event_bus = event_bus
        self.scheduler = ThreadPoolScheduler(1)  # 단일 워커 스레드 사용
        
        # 주문 승인 관련
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.pending_approvals: Dict[str, OrderApproval] = {}
        self.webhook_running = False
        self.webhook_thread = None
        
        self._setup_event_handlers()
        self._start_approval_polling()
        
    def _setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        # TRADE_UPDATE 이벤트 구독
        self.event_bus.subscribe(
            EventType.TRADE_UPDATE,
            lambda event: self._handle_event(event, self._process_trade_update)
        )
        
        # ERROR 이벤트 구독
        self.event_bus.subscribe(
            EventType.ERROR,
            lambda event: self._handle_event(event, self._process_error)
        )
        
        # 주문 승인 요청 이벤트 구독
        self.event_bus.subscribe(
            EventType.ORDER_APPROVAL_REQUEST.value,
            lambda event: self._handle_event(event, self._process_approval_request)
        )
        
    def _handle_event(self, event: Event, processor):
        """이벤트 처리 공통 로직"""
        try:
            processor(event)
        except Exception as e:
            logger.error(f"이벤트 처리 중 에러 발생: {str(e)}")
            
    def _process_trade_update(self, event: Event):
        """거래 업데이트 이벤트 처리"""
        if event.action in ["engine_start", "greet"]:
            self.send_message_sync(event.data["message"])
            
    def _process_error(self, event: Event):
        """에러 이벤트 처리"""
        self.send_error_sync(event.data["message"])
            
    def send_message_sync(self, message: str) -> bool:
        """동기식 메시지 전송 - httpx 사용"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            with httpx.Client() as client:
                response = client.post(url, json=data, timeout=10.0)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {str(e)}")
            return False
            
    def send_error_sync(self, error_message: str) -> bool:
        """동기식 에러 메시지 전송"""
        message = f"🚨 에러 발생!\n\n{error_message}"
        return self.send_message_sync(message)
            
    def send_trade_signal_sync(self, signal_type: str, symbol: str, price: float, quantity: float) -> bool:
        """동기식 거래 신호 전송"""
        emoji = "🔵" if signal_type == "매수" else "🔴"
        message = f"{emoji} {signal_type} 신호\n\n종목: {symbol}\n가격: ${price:,.2f}\n수량: {quantity:,.2f}"
        return self.send_message_sync(message)
    
    def _process_approval_request(self, event: Event):
        """주문 승인 요청 이벤트 처리"""
        logger.info(f"🎯 주문 승인 요청 이벤트 수신: {event.source} -> {event.action}")
        
        orders = event.data.get("orders", [])
        callback_id = event.data.get("callback_id")
        timeout = event.data.get("timeout", 300)
        
        logger.info(f"📋 주문 수: {len(orders)}, 콜백ID: {callback_id}, 타임아웃: {timeout}초")
        
        order_id = self._request_order_approval_sync(orders, callback_id, timeout)
        if order_id:
            logger.info(f"✅ 주문 승인 요청 처리됨: {order_id}")
        else:
            logger.error("❌ 주문 승인 요청 처리 실패")
    
    def _request_order_approval_sync(self, orders: list, callback_id: str, timeout: int = 300) -> str:
        """동기식 주문 승인 요청"""
        # 주문 ID 생성
        order_id = str(int(time.time()))
        
        # 승인 요청 메시지 생성
        message = self._create_approval_message(orders, order_id)
        
        # 인라인 키보드 생성
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ 승인", "callback_data": f"order_{order_id}_yes"},
                    {"text": "❌ 거부", "callback_data": f"order_{order_id}_no"}
                ]
            ]
        }
        
        # 메시지 전송
        if self._send_message_with_keyboard_sync(message, keyboard):
            # 승인 정보 저장 (콜백 함수 대신 callback_id 저장)
            approval = OrderApproval(order_id, orders, callback_id, timeout)
            self.pending_approvals[order_id] = approval
            
            # 타임아웃 처리
            threading.Timer(timeout, self._handle_timeout, args=[order_id]).start()
            
            logger.info(f"주문 승인 요청 전송됨: {order_id}")
            return order_id
        else:
            logger.error("주문 승인 요청 전송 실패")
            return None
    
    def _create_approval_message(self, orders: list, order_id: str) -> str:
        """승인 요청 메시지 생성"""
        message = f"🔐 <b>주문 승인 요청</b>\n\n"
        message += f"주문 ID: <code>{order_id}</code>\n"
        message += f"요청 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        total_amount = 0
        for i, order in enumerate(orders, 1):
            action = order.get('action', 'UNKNOWN')
            symbol = order.get('symbol', 'UNKNOWN')
            quantity = order.get('quantity', 0)
            price = order.get('price', 0)
            order_type = order.get('order_type', 'MARKET')
            
            amount = quantity * price
            total_amount += amount
            
            emoji = "🟢" if action == "BUY" else "🔴"
            message += f"{i}. {emoji} <b>{action}</b> {symbol}\n"
            message += f"   수량: {quantity}주\n"
            message += f"   가격: ${price:.2f}\n"
            message += f"   주문타입: {order_type}\n"
            message += f"   금액: ${amount:,.2f}\n\n"
        
        message += f"💰 <b>총 예상 금액: ${total_amount:,.2f}</b>\n\n"
        message += "위 주문을 승인하시겠습니까?"
        
        return message
    
    def _send_message_with_keyboard_sync(self, message: str, keyboard: dict) -> bool:
        """동기식 인라인 키보드 메시지 전송"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard)
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.debug(f"인라인 키보드 메시지 전송 성공")
                return True
            else:
                logger.error(f"인라인 키보드 메시지 전송 실패: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"인라인 키보드 메시지 전송 오류: {str(e)}")
            return False
    
    def _handle_timeout(self, order_id: str):
        """승인 타임아웃 처리"""
        if order_id in self.pending_approvals:
            approval = self.pending_approvals[order_id]
            
            logger.info(f"주문 승인 타임아웃: {order_id}")
            self.send_message_sync(f"⏰ 주문 {order_id}: 승인 시간 초과로 자동 취소되었습니다.")
            
            # EventBus로 타임아웃 응답 전송
            self.event_bus.dispatch(Event(
                type=EventType.ORDER_APPROVAL_RESPONSE.value,
                source="telegram_handler",
                action="timeout",
                data={
                    "callback_id": approval.callback,
                    "approved": False,
                    "orders": approval.orders,
                    "order_id": order_id
                }
            ))
            
            del self.pending_approvals[order_id]
    
    def _start_approval_polling(self):
        """주문 승인 폴링 시작"""
        def polling_loop():
            offset = 0
            logger.info("주문 승인 폴링 시작됨")
            
            while self.webhook_running:
                try:
                    url = f"{self.base_url}/getUpdates"
                    params = {'offset': offset, 'timeout': 3}
                    
                    response = requests.get(url, params=params, timeout=8)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('ok'):
                            updates = data.get('result', [])
                            
                            for update in updates:
                                update_id = update['update_id']
                                
                                if 'callback_query' in update:
                                    callback_query = update['callback_query']
                                    self._process_callback_sync(callback_query)
                                
                                offset = update_id + 1
                                
                except requests.exceptions.Timeout:
                    pass  # 정상적인 타임아웃
                except Exception as e:
                    logger.error(f"폴링 오류: {e}")
                    time.sleep(2)
                    
                time.sleep(0.2)
            
            logger.info("주문 승인 폴링 종료됨")
        
        self.webhook_running = True
        self.webhook_thread = threading.Thread(target=polling_loop, daemon=True)
        self.webhook_thread.start()
    
    def _process_callback_sync(self, callback_query):
        """콜백 쿼리 동기 처리"""
        try:
            callback_data = callback_query.get('data', '')
            callback_id = callback_query.get('id', '')
            
            if callback_data.startswith('order_'):
                parts = callback_data.split('_')
                if len(parts) == 3:
                    action, order_id, decision = parts
                    
                    if order_id in self.pending_approvals:
                        approval = self.pending_approvals[order_id]
                        approved = (decision == 'yes')
                        
                        status = "✅ 승인됨" if approved else "❌ 거부됨"
                        self.send_message_sync(f"주문 {order_id}: {status}")
                        
                        # EventBus로 승인 응답 전송
                        self.event_bus.dispatch(Event(
                            type=EventType.ORDER_APPROVAL_RESPONSE.value,
                            source="telegram_handler",
                            action="approved" if approved else "rejected",
                            data={
                                "callback_id": approval.callback,
                                "approved": approved,
                                "orders": approval.orders,
                                "order_id": order_id
                            }
                        ))
                        
                        del self.pending_approvals[order_id]
            
            # 콜백 쿼리 응답
            try:
                response = requests.post(f"{self.base_url}/answerCallbackQuery", 
                                      data={'callback_query_id': callback_id}, timeout=5)
            except Exception as e:
                logger.error(f"콜백 쿼리 응답 오류: {e}")
                
        except Exception as e:
            logger.error(f"콜백 처리 오류: {e}")
            
    def stop_approval_polling(self):
        """주문 승인 폴링 중지"""
        if self.webhook_running:
            self.webhook_running = False
            if self.webhook_thread:
                self.webhook_thread.join(timeout=5)
            logger.info("주문 승인 폴링 중지됨")
            
    def send_portfolio_update_sync(self, symbol: str, avg_price: float, current_price: float, 
                                 quantity: float, profit_loss: float) -> bool:
        """동기식 포트폴리오 업데이트 전송"""
        profit_loss_pct = (current_price - avg_price) / avg_price * 100
        emoji = "📈" if profit_loss >= 0 else "📉"
        
        message = (
            f"{emoji} 포트폴리오 업데이트\n\n"
            f"종목: {symbol}\n"
            f"평균단가: ${avg_price:,.2f}\n"
            f"현재가격: ${current_price:,.2f}\n"
            f"보유수량: {quantity:,.2f}\n"
            f"손익: ${profit_loss:,.2f} ({profit_loss_pct:,.2f}%)"
        )
        return self.send_message_sync(message)

    def greet(self) -> None:
        """봇 시작 메시지 전송"""
        message = (
            "🤖 Infinite Hantu가 시작되었습니다!\n\n"
            "💡 무한매수 전략이 준비되었습니다.\n"
            "📊 실시간 업데이트를 받으실 수 있습니다.\n"
            "⚠️ 중요 알림은 즉시 전달됩니다."
        )
        self.event_bus.dispatch(Event(
            type=EventType.TRADE_UPDATE,
            source="telegram",
            action="greet",
            data={"message": message}
        ))

def setup_telegram(config: dict, event_bus: EventBus) -> telegram_handler:
    """텔레그램 핸들러 설정"""
    token = config['token']
    chat_id = config['chat_id']
    return telegram_handler(token, chat_id, event_bus) 