import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, Mock

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from src_rev.application.bot_service import BotService
from src_rev.domain.models import CycleState
from src_rev.domain.common import Money, Symbol
from datetime import date

@pytest.mark.asyncio
async def test_bot_status_command():
    """BotService 상태 조회 명령어 테스트"""
    
    # Mock Objects
    mock_bot = Mock()
    mock_repo = Mock()
    
    # Fake State
    fake_state = CycleState(
        cycle_id="test_cycle",
        symbol=Symbol("SOXL"),
        start_date=date(2023, 1, 1),
        is_active=True,
        accumulated_profit=Money(50.0),
        daily_buy_completed=True
    )
    mock_repo.load.return_value = fake_state
    
    # Initialize Service
    service = BotService(mock_bot, mock_repo)
    
    # Test handle_status
    response = await service.handle_status(None)
    
    # Verify Response contains key info
    assert "SOXL" in response
    assert "진행 중: ✅" in response
    assert "오늘 매수: 완료" in response
    assert "50.00" in response

@pytest.mark.asyncio
async def test_bot_status_no_state():
    """상태 파일 없을 때 처리"""
    mock_bot = Mock()
    mock_repo = Mock()
    mock_repo.load.return_value = None
    
    service = BotService(mock_bot, mock_repo)
    response = await service.handle_status(None)
    
    assert "저장된 전략 상태가 없습니다" in response
