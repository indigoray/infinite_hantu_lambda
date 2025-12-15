from typing import Optional, Dict, Any
from datetime import datetime, date

from ...domain.models import CycleState
from ...domain.common import Money, Symbol

class DashboardViewModel:
    """CycleState를 UI 표시용 데이터로 변환"""
    
    @staticmethod
    def format_state(state: Optional[CycleState]) -> Dict[str, Any]:
        if not state:
            return {
                "is_active": False,
                "status_text": "🛑 중지됨 (데이터 없음)",
                "symbol": "-",
                "profit": "$0.00",
                "last_run": "-",
                "today_action": "대기 중"
            }
            
        # 상태 텍스트
        status = "🟢 실행 중" if state.is_active else "⏸ 일시 정지"
        
        # 오늘 매매 여부
        today = date.today()
        today_action = "대기 중"
        if state.last_execution_date == today:
            if state.daily_buy_completed:
                today_action = "✅ 오늘 매수 완료"
            elif state.daily_sell_completed:
                 today_action = "💰 오늘 매도 완료"
        
        return {
            "is_active": state.is_active,
            "status_text": status,
            "symbol": str(state.symbol),
            "profit": f"${float(state.accumulated_profit):,.2f}",
            "last_run": str(state.last_execution_date) if state.last_execution_date else "실행 기록 없음",
            "today_action": today_action,
            "cycle_id": state.cycle_id,
            "start_date": str(state.start_date)
        }
