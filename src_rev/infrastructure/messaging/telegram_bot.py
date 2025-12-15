import logging
import asyncio
from typing import Optional, Callable, Any
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

class TelegramBot:
    """
    텔레그램 봇 인프라스트럭처.
    메시지 발송 및 명령어 수신을 담당.
    """
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.application = None
        self._command_handlers = {}
        
    async def initialize(self):
        """봇 애플리케이션 초기화"""
        if not self.token:
            logger.warning("Telegram token not provided. Bot will be disabled.")
            return

        self.application = ApplicationBuilder().token(self.token).build()
        logger.info("Telegram Bot initialized.")

    def register_command(self, command: str, handler: Callable):
        """명령어 핸들러 등록"""
        if self.application:
            # 래퍼 함수: 비동기 핸들러로 변환 및 context 주입
            async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                # 권한 확인 (chat_id)
                if str(update.effective_chat.id) != str(self.chat_id):
                    await update.message.reply_text("Unauthorized access.")
                    return
                
                logger.info(f"Command received: /{command}")
                response = await handler(update.message.text) if asyncio.iscoroutinefunction(handler) else handler(update.message.text)
                if response:
                    await update.message.reply_text(response)

            self.application.add_handler(CommandHandler(command, wrapped_handler))
            logger.info(f"Registered command handler: /{command}")

    async def start(self):
        """봇 시작 (Polling)"""
        if self.application:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Telegram Bot polling started.")

    async def stop(self):
        """봇 종료"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram Bot stopped.")

    async def send_message(self, text: str):
        """메시지 전송"""
        if not self.application:
            return
            
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send telegram message: {e}")
