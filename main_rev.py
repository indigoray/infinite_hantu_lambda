import asyncio
import logging
import signal
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.append(str(ROOT_DIR))

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src_rev.infrastructure.persistence.json_repo import StateRepository
from src_rev.infrastructure.messaging.telegram_bot import TelegramBot
from src_rev.infrastructure.config_loader import ConfigLoader
from src_rev.infrastructure.kis.auth import KisAuth
from src_rev.infrastructure.kis.api import KisApi
from src_rev.application.bot_service import BotService
from src_rev.application.trading_engine import TradingEngine

async def main():
    """메인 엔트리 포인트"""
    
    # 1. 설정 로드 (config/config.yaml 사용)
    config_path = ROOT_DIR / "config" / "config.yaml"
    loader = ConfigLoader(str(config_path))
    domain_config, system_config = loader.load()
    
    logger.info(f"Loaded Config: Symbol={domain_config.symbol}, Inv=${domain_config.total_investment}")
    
    # 2. 인프라 초기화
    # 상태 저장소
    repo = StateRepository(str(ROOT_DIR / "states" / "revised_state.json"))
    
    # 텔레그램 봇
    telegram_conf = system_config.get("telegram", {})
    token = telegram_conf.get("token")
    chat_id = telegram_conf.get("chat_id")
    
    # KIS API
    api_conf = system_config.get("api", {})
    kis_auth = KisAuth(
        key=api_conf.get("app_key"),
        secret=api_conf.get("app_secret"),
        is_virtual=api_conf.get("is_virtual", True)
    )
    kis_api = KisApi(kis_auth, api_conf.get("account_number"))
    
    if not token:
        logger.warning("Telegram token not found in config.yaml")
    
    bot = TelegramBot(token, chat_id)
    await bot.initialize()
    
    # 3. 애플리케이션 서비스 조립
    bot_service = BotService(bot, repo)
    # TradingEngine에 KIS API (Provider & Executor) 주입
    engine = TradingEngine(
        domain_config, 
        repo, 
        bot_service, 
        market_provider=kis_api, 
        order_executor=kis_api
    )
    
    # 4. 봇 시작 (Polling)
    # 봇 폴링은 별도 태스크로 실행
    bot_task = asyncio.create_task(bot.start())
    
    # 5. 엔진 시작
    try:
        await engine.start()
    except asyncio.CancelledError:
        logger.info("Application cancelled")
    finally:
        await bot.stop()
        bot_task.cancel() # 태스크 캔슬

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
