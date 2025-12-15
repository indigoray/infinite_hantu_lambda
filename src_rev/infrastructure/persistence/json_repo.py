import json
import os
from datetime import date, datetime
from typing import Optional
from ...domain.models import CycleState
from ...domain.common import Money, Symbol

class StateRepository:
    """JSON 파일 기반의 상태 저장소"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_directory()

    def _ensure_directory(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def save(self, state: CycleState):
        """상태를 JSON 파일로 저장"""
        data = {
            "cycle_id": state.cycle_id,
            "symbol": state.symbol,
            "start_date": state.start_date.isoformat(),
            "is_active": state.is_active,
            "end_date": state.end_date.isoformat() if state.end_date else None,
            "accumulated_profit": float(state.accumulated_profit),
            "last_execution_date": state.last_execution_date.isoformat() if state.last_execution_date else None,
            "daily_buy_completed": state.daily_buy_completed,
            "daily_sell_completed": state.daily_sell_completed
        }
        
        # 원자적 쓰기 (Atomic Write)
        temp_path = f"{self.file_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_path, self.file_path)

    def load(self) -> Optional[CycleState]:
        """JSON 파일에서 상태 로드"""
        if not os.path.exists(self.file_path):
            return None
            
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return CycleState(
                cycle_id=data["cycle_id"],
                symbol=Symbol(data["symbol"]),
                start_date=date.fromisoformat(data["start_date"]),
                is_active=data["is_active"],
                end_date=date.fromisoformat(data["end_date"]) if data["end_date"] else None,
                accumulated_profit=Money(data["accumulated_profit"]),
                last_execution_date=date.fromisoformat(data["last_execution_date"]) if data.get("last_execution_date") else None,
                daily_buy_completed=data.get("daily_buy_completed", False),
                daily_sell_completed=data.get("daily_sell_completed", False)
            )
        except Exception as e:
            # 파일이 깨졌거나 형식이 다르면 로드 실패
            print(f"Error loading state: {e}")
            return None
