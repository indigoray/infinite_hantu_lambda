from datetime import datetime
from src_rev.infrastructure.messaging.telegram_bot import TelegramBot
from src_rev.domain.models import CycleState

class BotService:
    """
    Application Layer의 텔레그램 서비스.
    인프라(TelegramBot)와 도메인 로직을 연결한다.
    """
    
    def __init__(self, bot: TelegramBot, state_repo):
        self.bot = bot
        self.state_repo = state_repo
        
        # 기본 명령어 등록
        self.bot.register_command("status", self.handle_status)
        self.bot.register_command("ping", self.handle_ping)

    async def handle_status(self, _):
        """현재 상태 조회 커맨드 처리"""
        state: CycleState = self.state_repo.load()
        if not state:
            return "⚠️ 저장된 전략 상태가 없습니다."
            
        return (
            f"📊 <b>전략 상태 보고 ({datetime.now().strftime('%H:%M:%S')})</b>\n\n"
            f"• 종목: {state.symbol}\n"
            f"• 진행 중: {'✅' if state.is_active else '⛔'}\n"
            f"• 오늘 매수: {'완료' if state.daily_buy_completed else '대기'}\n"
            f"• 누적 수익: ${state.accumulated_profit:,.2f}"
        )

    async def handle_ping(self, _):
        return "Pong! 🏓 봇이 정상 작동 중입니다."

    async def notify_order_execution(self, orders):
        """주문 체결 알림"""
        message = "🚀 <b>주문 실행 알림</b>\n\n"
        for order in orders:
            message += f"• {order.side} {order.quantity}주 @ {order.price:,.2f} ({order.order_type})\n"
        
        await self.bot.send_message(message)
        
    async def notify_error(self, error_msg: str):
        """에러 알림"""
        await self.bot.send_message(f"🚨 <b>오류 발생</b>\n\n{error_msg}")
        
    async def notify_info(self, msg: str):
        """일반 정보 알림"""
        await self.bot.send_message(f"ℹ️ <b>알림</b>\n\n{msg}")
