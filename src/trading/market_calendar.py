import logging
import requests
from datetime import datetime, time, date, timedelta
import pytz
from typing import Dict, Optional, List
import holidays

logger = logging.getLogger(__name__)

class MarketCalendar:
    """시장 캘린더 관리 클래스
    
    실시간으로 미국 증시의 개장시간, 공휴일, 서머타임 등을 확인
    """
    
    def __init__(self):
        self.eastern_tz = pytz.timezone('US/Eastern')
        self.nyse_holidays = holidays.NYSE()
        
        # 기본 거래시간 (EST 기준)
        self.default_market_hours = {
            "us": {
                "regular": {"start": "09:30", "end": "16:00"},  # 정규장
                "pre": {"start": "04:00", "end": "09:30"},      # 프리마켓
                "after": {"start": "16:00", "end": "20:00"}     # 애프터마켓
            },
            "kr": {
                "regular": {"start": "09:00", "end": "15:30"},  # 정규장
                "pre": {"start": "08:00", "end": "09:00"},      # 동시호가
                "after": {"start": "15:30", "end": "16:00"}     # 시간외거래
            }
        }
        
        # 조기 마감일 (1:00 PM EST 마감)
        self.early_close_dates = {
            2025: [
                date(2025, 7, 3),   # July 3rd (before Independence Day)
                date(2025, 11, 28), # Day after Thanksgiving
                date(2025, 12, 24), # Christmas Eve
            ]
        }
        
    def is_market_holiday(self, check_date: Optional[date] = None, market: str = "us") -> bool:
        """시장 공휴일 여부 확인
        
        Args:
            check_date: 확인할 날짜 (None이면 오늘)
            market: 시장 구분 ("us" 또는 "kr")
            
        Returns:
            bool: 공휴일 여부
        """
        if check_date is None:
            if market == "us":
                check_date = datetime.now(self.eastern_tz).date()
            else:
                check_date = datetime.now().date()
        
        if market == "us":
            # NYSE 공휴일 확인
            return check_date in self.nyse_holidays
        elif market == "kr":
            # 한국 공휴일 확인 (holidays 라이브러리 사용)
            try:
                import holidays
                kr_holidays = holidays.KR()
                return check_date in kr_holidays
            except ImportError:
                # holidays 라이브러리가 없으면 기본 한국 공휴일만 확인
                return self._is_basic_kr_holiday(check_date)
        
        return False
    
    def _is_basic_kr_holiday(self, check_date: date) -> bool:
        """기본 한국 공휴일 확인 (holidays 라이브러리 없을 때 백업)
        
        Args:
            check_date: 확인할 날짜
            
        Returns:
            bool: 기본 공휴일 여부
        """
        # 기본 고정 공휴일만 확인 (음력 공휴일은 제외)
        year = check_date.year
        month = check_date.month
        day = check_date.day
        
        basic_holidays = [
            (1, 1),   # 신정
            (3, 1),   # 삼일절  
            (5, 5),   # 어린이날
            (6, 6),   # 현충일
            (8, 15),  # 광복절
            (10, 3),  # 개천절
            (10, 9),  # 한글날
            (12, 25), # 크리스마스
        ]
        
        return (month, day) in basic_holidays
    
    def _get_kr_holiday_name(self, check_date: date) -> str:
        """한국 공휴일 이름 조회
        
        Args:
            check_date: 확인할 날짜
            
        Returns:
            str: 공휴일 이름
        """
        try:
            import holidays
            kr_holidays = holidays.KR()
            return kr_holidays.get(check_date, "Holiday")
        except ImportError:
            # holidays 라이브러리가 없으면 기본 이름 사용
            month = check_date.month
            day = check_date.day
            
            basic_holiday_names = {
                (1, 1): "신정",
                (3, 1): "삼일절",
                (5, 5): "어린이날",
                (6, 6): "현충일", 
                (8, 15): "광복절",
                (10, 3): "개천절",
                (10, 9): "한글날",
                (12, 25): "크리스마스",
            }
            
            return basic_holiday_names.get((month, day), "공휴일")
    
    def is_early_close_day(self, check_date: Optional[date] = None) -> bool:
        """조기 마감일 여부 확인
        
        Args:
            check_date: 확인할 날짜 (None이면 오늘)
            
        Returns:
            bool: 조기 마감일 여부
        """
        if check_date is None:
            check_date = datetime.now(self.eastern_tz).date()
            
        year = check_date.year
        if year in self.early_close_dates:
            return check_date in self.early_close_dates[year]
        return False
    
    def get_market_hours(self, market: str = "us", check_date: Optional[date] = None) -> Dict[str, Dict[str, str]]:
        """시장별 거래시간 조회
        
        Args:
            market: 시장 구분 ("us" 또는 "kr")
            check_date: 확인할 날짜 (None이면 오늘)
            
        Returns:
            Dict: 거래시간 정보
        """
        if market not in self.default_market_hours:
            return {}
            
        market_hours = self.default_market_hours[market].copy()
        
        # 미국 시장이고 조기 마감일인 경우
        if market == "us" and self.is_early_close_day(check_date):
            market_hours["regular"]["end"] = "13:00"  # 1:00 PM EST 조기 마감
            logger.info(f"조기 마감일 적용: {check_date} - 1:00 PM EST 마감")
            
        return market_hours
    
    def is_market_open(self, market: str = "us", current_time: Optional[datetime] = None) -> bool:
        """현재 시장 개장 여부 확인
        
        Args:
            market: 시장 구분 ("us" 또는 "kr")
            current_time: 확인할 시간 (None이면 현재 시간)
            
        Returns:
            bool: 시장 개장 여부
        """
        if current_time is None:
            if market == "us":
                current_time = datetime.now(self.eastern_tz)
            else:
                current_time = datetime.now()
        
        current_date = current_time.date()
        
        # 공휴일 확인
        if self.is_market_holiday(current_date, market):
            return False
            
        # 주말 확인
        if current_time.weekday() >= 5:  # 토, 일
            return False
            
        # 거래시간 확인
        market_hours = self.get_market_hours(market, current_date)
        current_time_str = current_time.strftime("%H:%M")
        
        for session_type, times in market_hours.items():
            start_time = times["start"]
            end_time = times["end"]
            
            # 다음날로 넘어가는 경우 처리 (프리마켓 등)
            if start_time > end_time:
                if current_time_str >= start_time or current_time_str <= end_time:
                    return True
            else:
                if start_time <= current_time_str <= end_time:
                    return True
                    
        return False
    
    def get_market_status(self, market: str = "us") -> Dict[str, any]:
        """시장 상태 종합 정보
        
        Args:
            market: 시장 구분
            
        Returns:
            Dict: 시장 상태 정보
        """
        if market == "us":
            current_time = datetime.now(self.eastern_tz)
        else:
            current_time = datetime.now()
            
        current_date = current_time.date()
        
        status = {
            "market": market.upper(),
            "current_time": current_time.isoformat(),
            "is_open": self.is_market_open(market, current_time),
            "is_holiday": False,
            "is_early_close": False,
            "next_session": None,
            "market_hours": self.get_market_hours(market, current_date)
        }
        
        if market == "us":
            status["is_holiday"] = self.is_market_holiday(current_date, "us")
            status["is_early_close"] = self.is_early_close_day(current_date)
        elif market == "kr":
            status["is_holiday"] = self.is_market_holiday(current_date, "kr")
            status["is_early_close"] = False  # 한국은 조기 마감 없음
            
        return status
    
    def get_trading_calendar_api(self, mic: str = "XNYS") -> Optional[Dict]:
        """Trading Calendar API를 통한 실시간 정보 조회
        
        Args:
            mic: Market Identifier Code (예: XNYS, XNAS)
            
        Returns:
            Dict: API 응답 정보 또는 None
        """
        try:
            # 무료 Trading Calendar API 사용
            url = f"https://api.tradingcalendar.io/v1/markets"
            params = {"mic": mic}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Trading Calendar API 호출 실패: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Trading Calendar API 요청 오류: {e}")
            return None
    
    def get_upcoming_holidays(self, days_ahead: int = 30, market: str = "us") -> List[Dict]:
        """향후 공휴일 목록 조회
        
        Args:
            days_ahead: 조회할 앞으로의 일수
            market: 시장 구분 ("us" 또는 "kr")
            
        Returns:
            List[Dict]: 공휴일 정보 목록
        """
        upcoming_holidays = []
        
        if market == "us":
            today = datetime.now(self.eastern_tz).date()
        else:
            today = datetime.now().date()
        
        for i in range(days_ahead):
            check_date = today + timedelta(days=i)
            
            if self.is_market_holiday(check_date, market):
                # 공휴일 이름 가져오기
                if market == "us":
                    holiday_name = self.nyse_holidays.get(check_date, "Holiday")
                    is_early_close = self.is_early_close_day(check_date - timedelta(days=1))
                else:  # kr
                    holiday_name = self._get_kr_holiday_name(check_date)
                    is_early_close = False  # 한국은 조기 마감 없음
                
                upcoming_holidays.append({
                    "date": check_date.isoformat(),
                    "name": holiday_name,
                    "is_early_close": is_early_close,
                    "market": market.upper()
                })
                
        return upcoming_holidays

# 전역 인스턴스
market_calendar = MarketCalendar() 