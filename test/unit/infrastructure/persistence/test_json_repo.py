import sys
from pathlib import Path
import os
import pytest
from datetime import date

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from src_rev.domain.models import CycleState
from src_rev.domain.common import Symbol, Money
from src_rev.infrastructure.persistence.json_repo import StateRepository

@pytest.fixture
def repo(tmp_path):
    file_path = tmp_path / "state.json"
    return StateRepository(str(file_path))

def test_save_and_load(repo):
    """상태 저장 및 로드 테스트"""
    # Given
    state = CycleState(
        cycle_id="cycle_123",
        symbol=Symbol("SOXL"),
        start_date=date(2023, 1, 1),
        is_active=True,
        accumulated_profit=Money(100.0),
        daily_buy_completed=True
    )
    
    # When
    repo.save(state)
    loaded_state = repo.load()
    
    # Then
    assert loaded_state is not None
    assert loaded_state.cycle_id == "cycle_123"
    assert loaded_state.symbol == "SOXL"
    assert loaded_state.daily_buy_completed is True
    assert loaded_state.accumulated_profit == 100.0

def test_load_non_existent_file(repo):
    """파일이 없으면 None 반환"""
    assert repo.load() is None
