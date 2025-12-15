import logging
import threading
import time
import os
import ssl
import zipfile
import urllib.request
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Tuple, List
from src.utils.event_bus import EventBus, Event, EventType
from src.trading.market_calendar import market_calendar

logger = logging.getLogger(__name__)

class StockSubscriber:
    """실시간 주식 시세 구독자
    
    등록된 티커들의 가격을 1분마다 조회하여 로깅하고
    이벤트 버스로 가격 업데이트를 전파
    """
    
    def __init__(self, kis_client, event_bus: EventBus = None, monitoring_interval: int = 60):
        self.client = kis_client
        self.event_bus = event_bus
        self.subscribed_symbols: Dict[str, Dict] = {}  # {symbol: {market: str, last_price: float, last_update: datetime}}
        self.is_running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.start_time = None  # 시작 시간 기록
        self.symbol_loggers: Dict[str, logging.Logger] = {}  # 종목별 로거 저장
        self.monitoring_interval = monitoring_interval  # 모니터링 간격 (초 단위)
        
        # 종목 마스터 데이터 캐시
        self.kospi_master = None
        self.kosdaq_master = None
        self.stock_master_cache = {}  # {종목코드: 회사명} 캐시
        
        # price_logging 폴더 생성
        self.price_logging_dir = "price_logging"
        if not os.path.exists(self.price_logging_dir):
            os.makedirs(self.price_logging_dir)
            logger.info(f"📁 가격 로깅 폴더 생성: {self.price_logging_dir}")
        
        # 종목 마스터 데이터 초기화
        self._initialize_stock_master()
        
        # 마켓 캘린더 인스턴스 사용 (동적 공휴일/서머타임 처리)
        self.market_calendar = market_calendar
        
    def _initialize_stock_master(self):
        """종목 마스터 데이터 초기화"""
        try:
            # 캐시 파일 확인
            cache_dir = "stock_master_cache"
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                
            kospi_cache = os.path.join(cache_dir, "kospi_master.pkl")
            kosdaq_cache = os.path.join(cache_dir, "kosdaq_master.pkl")
            
            # 캐시 파일이 있으면 사용, 없으면 다운로드
            if os.path.exists(kospi_cache) and os.path.exists(kosdaq_cache):
                logger.info("📊 종목 마스터 캐시 로드 중...")
                self.kospi_master = pd.read_pickle(kospi_cache)
                self.kosdaq_master = pd.read_pickle(kosdaq_cache)
                logger.info("💡 최신 데이터가 필요하면 stock_master_cache 폴더를 삭제하세요")
            else:
                logger.info("📊 종목 마스터 데이터 다운로드 중...")
                self._download_stock_master(cache_dir)
                
            # 검색용 캐시 구성
            self._build_search_cache()
            logger.info(f"📊 종목 마스터 초기화 완료 (총 {len(self.stock_master_cache)}개 종목)")
            
        except Exception as e:
            logger.warning(f"⚠️ 종목 마스터 초기화 실패: {e}")
            logger.warning("종목명 변환 기능이 제한됩니다.")
            
    def _download_stock_master(self, cache_dir: str):
        """종목 마스터 데이터 다운로드"""
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            
            # KOSPI 마스터 다운로드
            logger.info("📥 KOSPI 마스터 다운로드 중...")
            urllib.request.urlretrieve(
                "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
                os.path.join(cache_dir, "kospi_code.zip")
            )
            
            # KOSDAQ 마스터 다운로드
            logger.info("📥 KOSDAQ 마스터 다운로드 중...")
            urllib.request.urlretrieve(
                "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
                os.path.join(cache_dir, "kosdaq_code.zip")
            )
            
            # 압축 해제 및 파싱
            self.kospi_master = self._parse_master_file(cache_dir, "kospi")
            self.kosdaq_master = self._parse_master_file(cache_dir, "kosdaq")
            
            # 캐시 저장
            self.kospi_master.to_pickle(os.path.join(cache_dir, "kospi_master.pkl"))
            self.kosdaq_master.to_pickle(os.path.join(cache_dir, "kosdaq_master.pkl"))
            
            # 임시 파일 정리
            for file in ["kospi_code.zip", "kosdaq_code.zip", "kospi_code.mst", "kosdaq_code.mst"]:
                file_path = os.path.join(cache_dir, file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
            logger.info("✅ 종목 마스터 다운로드 완료")
            
        except Exception as e:
            logger.error(f"❌ 종목 마스터 다운로드 실패: {e}")
            raise
            
    def _parse_master_file(self, cache_dir: str, market: str) -> pd.DataFrame:
        """마스터 파일 파싱"""
        zip_path = os.path.join(cache_dir, f"{market}_code.zip")
        mst_path = os.path.join(cache_dir, f"{market}_code.mst")
        
        # 압축 해제
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)
        
        # 파일 파싱
        stocks = []
        with open(mst_path, 'r', encoding='cp949') as f:
            for line in f:
                if len(line) < 50:  # 최소 길이 체크
                    continue
                    
                try:
                    # 한국투자증권 마스터 파일 형식에 따른 정확한 파싱
                    code = line[0:9].strip()  # 종목코드 (9자리에서 앞 6자리 추출)
                    if len(code) > 6:
                        code = code[:6]
                    
                    # 종목명은 21번째부터 시작하며 공백으로 끝남
                    name_start = 21
                    name_part = line[name_start:name_start+40].strip()  # 최대 40자까지만
                    name = name_part.split()[0] if name_part else ""  # 첫 번째 단어만 추출
                    
                    # 유효성 검사
                    if (code and name and len(code) == 6 and 
                        code.isdigit() and len(name) > 0 and len(name) <= 20):
                        stocks.append({'code': code, 'name': name, 'market': market.upper()})
                        
                except (IndexError, ValueError):
                    # 파싱 오류 시 건너뛰기
                    continue
        
        return pd.DataFrame(stocks)
    
    def _build_search_cache(self):
        """검색용 캐시 구성"""
        self.stock_master_cache = {}
        
        if self.kospi_master is not None:
            for _, row in self.kospi_master.iterrows():
                self.stock_master_cache[row['code']] = row['name']
                
        if self.kosdaq_master is not None:
            for _, row in self.kosdaq_master.iterrows():
                self.stock_master_cache[row['code']] = row['name']
    
    def search_stock(self, query: str) -> Tuple[str, str]:
        """종목 검색 (종목코드 또는 회사명으로 검색)
        
        Args:
            query: 검색어 (종목코드 또는 회사명)
            
        Returns:
            Tuple[str, str]: (종목코드, 회사명)
        """
        query = query.strip()
        
        # 1. 종목코드로 검색 (6자리 숫자)
        if query.isdigit() and len(query) == 6:
            if query in self.stock_master_cache:
                return query, self.stock_master_cache[query]
            else:
                return query, query  # 캐시에 없으면 그대로 반환
        
        # 2. 회사명으로 검색 (정확한 매칭 우선)
        for code, name in self.stock_master_cache.items():
            if query == name:  # 정확한 매칭
                return code, name
        
        # 3. 부분 매칭 검색 (대소문자 무시)
        query_lower = query.lower()
        for code, name in self.stock_master_cache.items():
            name_lower = name.lower()
            if (query_lower in name_lower or name_lower in query_lower or
                query in name or name in query):
                return code, name
        
        # 4. 특별한 경우 처리 (네이버 등)
        special_mapping = {
            "네이버": "035420",
            "naver": "035420",
            "삼성전자": "005930",
            "samsung": "005930"
        }
        
        query_key = query_lower if query_lower in special_mapping else query
        if query_key in special_mapping:
            code = special_mapping[query_key]
            if code in self.stock_master_cache:
                return code, self.stock_master_cache[code]
        
        # 5. 검색 실패 시 원본 반환
        return query, query
    
    def get_display_name(self, symbol: str, market: str) -> str:
        """표시용 이름 가져오기
        
        Args:
            symbol: 종목코드 또는 티커
            market: 시장 구분
            
        Returns:
            str: 표시용 이름 (한국 주식은 회사명, 해외 주식은 티커)
        """
        if market == "kr":
            # 한국 주식은 회사명 사용
            if symbol in self.stock_master_cache:
                return self.stock_master_cache[symbol]
            else:
                return symbol
        else:
            # 해외 주식은 티커 사용
            return symbol
            
    def _make_safe_filename(self, name: str) -> str:
        """파일명에 안전한 이름 생성
        
        Args:
            name: 원본 이름
            
        Returns:
            str: 파일명에 사용 가능한 안전한 이름
        """
        import re
        
        # 파일명에 사용할 수 없는 문자들 제거
        # Windows: < > : " | ? * \
        # Unix: /
        unsafe_chars = r'[<>:"|?*\\/]'
        safe_name = re.sub(unsafe_chars, '_', name)
        
        # 연속된 공백을 하나의 언더스코어로 변경
        safe_name = re.sub(r'\s+', '_', safe_name)
        
        # 앞뒤 공백 및 언더스코어 제거
        safe_name = safe_name.strip('_')
        
        # 파일명 길이 제한 (확장자 제외하고 최대 50자)
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        
        # 빈 문자열이면 기본값 사용
        if not safe_name:
            safe_name = "unknown"
            
        return safe_name
        
    def _create_symbol_logger(self, symbol: str, market: str) -> logging.Logger:
        """종목별 로거 생성
        
        Args:
            symbol: 티커 심볼
            market: 시장 구분
            
        Returns:
            logging.Logger: 종목별 로거
        """
        if self.start_time is None:
            self.start_time = datetime.now()
            
        # 표시용 이름 가져오기
        display_name = self.get_display_name(symbol, market)
        
        # 로그 파일명: 표시이름_시작시간.log (파일명에 안전한 문자만 사용)
        start_time_str = self.start_time.strftime("%Y%m%d_%H%M%S")
        safe_name = self._make_safe_filename(display_name)
        log_filename = f"{safe_name}_{start_time_str}.log"
        log_filepath = os.path.join(self.price_logging_dir, log_filename)
        
        # 종목별 로거 생성
        symbol_logger = logging.getLogger(f"price_{symbol}")
        symbol_logger.setLevel(logging.INFO)
        
        # 기존 핸들러가 있으면 제거 (중복 방지)
        for handler in symbol_logger.handlers[:]:
            symbol_logger.removeHandler(handler)
        
        # 파일 핸들러 생성
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        symbol_logger.addHandler(file_handler)
        
        # 로거가 부모 로거로 전파되지 않도록 설정
        symbol_logger.propagate = False
        
        logger.info(f"📝 종목별 로그 파일 생성: {log_filepath}")
        
        # 로그 파일 헤더 작성
        symbol_logger.info(f"=== {display_name}({symbol}) 가격 로깅 시작 ===")
        symbol_logger.info(f"시작 시간: {self.start_time}")
        symbol_logger.info(f"시장: {market.upper()}")
        symbol_logger.info(f"로그 형식: 시간 | 가격 | 변화량 | 변화율 | 상태")
        symbol_logger.info("=" * 50)
        
        return symbol_logger
        
    def subscribe(self, query: str, market: str = "us"):
        """심볼 구독 (종목코드, 회사명, 티커 모두 가능)
        
        Args:
            query: 검색어 (종목코드, 회사명, 티커 등)
            market: 시장 구분 ("us" 또는 "kr")
        """
        if market == "kr":
            # 한국 주식은 종목 검색 수행
            symbol, company_name = self.search_stock(query)
            display_name = company_name
        else:
            # 해외 주식은 티커 그대로 사용
            symbol = query.upper()
            display_name = symbol
        
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols[symbol] = {
                "market": market,
                "last_price": 0.0,
                "last_update": None,
                "error_count": 0,
                "display_name": display_name
            }
            
            # 종목별 로거 생성
            self.symbol_loggers[symbol] = self._create_symbol_logger(symbol, market)
            
            logger.info(f"📈 심볼 구독 시작: {display_name}({symbol}) {market.upper()} 시장")
        else:
            logger.info(f"📈 심볼 이미 구독 중: {display_name}({symbol})")
            
    def unsubscribe(self, symbol: str):
        """심볼 구독 해제"""
        if symbol in self.subscribed_symbols:
            display_name = self.subscribed_symbols[symbol].get("display_name", symbol)
            
            # 종목별 로거 정리
            if symbol in self.symbol_loggers:
                symbol_logger = self.symbol_loggers[symbol]
                symbol_logger.info("=== 구독 해제 - 로깅 종료 ===")
                
                # 핸들러 제거
                for handler in symbol_logger.handlers[:]:
                    handler.close()
                    symbol_logger.removeHandler(handler)
                
                del self.symbol_loggers[symbol]
            
            del self.subscribed_symbols[symbol]
            logger.info(f"📉 심볼 구독 해제: {display_name}({symbol})")
        else:
            logger.warning(f"📉 구독되지 않은 심볼: {symbol}")
            
    def start(self):
        """구독 시작"""
        if not self.is_running:
            self.start_time = datetime.now()  # 시작 시간 기록
            self.is_running = True
            self._stop_event.clear()
            
            # 시장 상태 정보 출력
            self.log_market_status()
            
            self._thread = threading.Thread(target=self._price_monitoring_loop, daemon=True)
            self._thread.start()
            logger.info("🚀 실시간 시세 구독 시작")
        else:
            logger.warning("실시간 시세 구독이 이미 실행 중입니다")
            
    def stop(self):
        """구독 중지"""
        if self.is_running:
            self.is_running = False
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=5)
            
            # 모든 종목별 로거 정리
            for symbol, symbol_logger in self.symbol_loggers.items():
                symbol_logger.info("=== 시스템 종료 - 로깅 종료 ===")
                for handler in symbol_logger.handlers[:]:
                    handler.close()
                    symbol_logger.removeHandler(handler)
            
            self.symbol_loggers.clear()
            logger.info("🛑 실시간 시세 구독 중지")
        else:
            logger.info("실시간 시세 구독이 이미 중지되어 있습니다")
    
    def _price_monitoring_loop(self):
        """가격 모니터링 루프"""
        logger.info(f"💡 가격 모니터링 루프 시작 (간격: {self.monitoring_interval}초)")
        
        while self.is_running and not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # 구독된 심볼들의 가격 조회
                for symbol, info in list(self.subscribed_symbols.items()):
                    try:
                        self._update_symbol_price(symbol, info, current_time)
                    except Exception as e:
                        info["error_count"] += 1
                        display_name = info.get("display_name", symbol)
                        logger.error(f"❌ {display_name}({symbol}) 가격 조회 실패 (에러 {info['error_count']}회): {str(e)}")
                        
                        # 종목별 로그에도 에러 기록
                        if symbol in self.symbol_loggers:
                            self.symbol_loggers[symbol].error(f"가격 조회 실패 (에러 {info['error_count']}회): {str(e)}")
                        
                        # 연속 에러가 5회 이상이면 경고
                        if info["error_count"] >= 5:
                            logger.warning(f"⚠️ {display_name}({symbol}) 연속 에러 5회 이상 - 장시간 또는 심볼 오류 확인 필요")
                            if symbol in self.symbol_loggers:
                                self.symbol_loggers[symbol].warning("연속 에러 5회 이상 - 장시간 또는 심볼 오류 확인 필요")
                            info["error_count"] = 0  # 카운터 리셋
                
                # 다음 실행까지 대기 (설정된 간격)
                if not self._stop_event.wait(self.monitoring_interval):
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"가격 모니터링 루프 오류: {str(e)}")
                if not self._stop_event.wait(10):  # 에러 발생시 10초 대기 후 재시도
                    continue
                else:
                    break
                    
        logger.info("💡 가격 모니터링 루프 종료")
    
    def _update_symbol_price(self, symbol: str, info: Dict, current_time: datetime):
        """개별 심볼의 가격 업데이트"""
        market = info["market"]
        display_name = info.get("display_name", symbol)
        symbol_logger = self.symbol_loggers.get(symbol)
        
        # 장시간 체크 (동적 공휴일/서머타임 처리)
        if not self._is_market_open(market, current_time):
            # 장이 열리지 않은 시간이면 DEBUG 레벨로 로깅 (스팸 방지)
            if info["last_update"] is None or (current_time - info["last_update"]).total_seconds() > 3600:  # 1시간마다만 로깅
                # 시장 상태 정보 조회
                market_status = self.market_calendar.get_market_status(market)
                
                status_msg = f"🌙 {display_name}({symbol}) ({market.upper()}) 장시간 외"
                if market == "us" and market_status.get("is_holiday"):
                    status_msg += " (공휴일)"
                elif market == "us" and market_status.get("is_early_close"):
                    status_msg += " (조기 마감일)"
                status_msg += " - 가격 조회 스킵"
                
                logger.debug(status_msg)
                if symbol_logger:
                    symbol_logger.info(status_msg)
                info["last_update"] = current_time
            return
        
        try:
            # 시장별 가격 조회
            if market == "us":
                price_data = self.client.get_oversea_stock_price(symbol)
                current_price = float(price_data.get("current_price", 0))
            elif market == "kr":
                # 한국 주식 가격 조회 (한국투자증권 API에서는 다른 메서드 사용)
                price_data = self.client.get_domestic_stock_price(symbol) if hasattr(self.client, 'get_domestic_stock_price') else {"current_price": 0}
                current_price = float(price_data.get("current_price", 0))
            else:
                logger.error(f"지원하지 않는 시장: {market}")
                return
            
            if current_price > 0:
                # 가격 변화 계산
                price_change = 0
                price_change_pct = 0
                if info["last_price"] > 0:
                    price_change = current_price - info["last_price"]
                    price_change_pct = (price_change / info["last_price"]) * 100
                
                # 가격 정보 업데이트
                info["last_price"] = current_price
                info["last_update"] = current_time
                info["error_count"] = 0  # 성공시 에러 카운터 리셋
                
                # 가격 변화 화살표
                if price_change > 0:
                    arrow = "📈"
                    status = "상승"
                elif price_change < 0:
                    arrow = "📉"
                    status = "하락"
                else:
                    arrow = "➡️"
                    status = "보합"
                
                # 종목별 로그 파일에 상세 정보 기록
                if symbol_logger:
                    symbol_logger.info(f"${current_price:.2f} | {price_change:+.2f} | {price_change_pct:+.2f}% | {status}")
                
                # 기존 로깅 (가격 변화가 있을 때만 INFO 레벨, 없으면 DEBUG 레벨)
                if abs(price_change_pct) > 0.01:  # 0.01% 이상 변화
                    logger.info(f"{arrow} {display_name}({symbol}) ({market.upper()}): ${current_price:.2f} "
                              f"({price_change:+.2f}, {price_change_pct:+.2f}%)")
                else:
                    logger.debug(f"➡️ {display_name}({symbol}) ({market.upper()}): ${current_price:.2f} (변화 없음)")
                
                # 이벤트 발행
                self._publish_price_update(symbol, current_price, price_change, price_change_pct, market)
                
            else:
                logger.warning(f"⚠️ {display_name}({symbol}) 가격 조회 결과가 0 또는 유효하지 않음")
                if symbol_logger:
                    symbol_logger.warning("가격 조회 결과가 0 또는 유효하지 않음")
                
        except Exception as e:
            raise e  # 상위에서 에러 카운팅 처리
    
    def _is_market_open(self, market: str, current_time: datetime) -> bool:
        """장이 열려있는지 확인 (동적 공휴일/서머타임 처리)
        
        Args:
            market: 시장 구분 ("us" 또는 "kr")
            current_time: 확인할 시간
            
        Returns:
            bool: 장 개장 여부
        """
        # 새로운 마켓 캘린더를 사용하여 동적으로 확인
        return self.market_calendar.is_market_open(market, current_time)
    
    def _publish_price_update(self, symbol: str, price: float, change: float, change_pct: float, market: str):
        """가격 업데이트 이벤트 발행"""
        if self.event_bus:
            try:
                self.event_bus.publish("price_update", {
                    "symbol": symbol,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "market": market,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"가격 업데이트 이벤트 발행 실패: {str(e)}")
    
    def get_subscribed_symbols(self) -> Dict[str, Dict]:
        """구독 중인 심볼 목록 반환"""
        return self.subscribed_symbols.copy()
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """특정 심볼의 정보 반환"""
        return self.subscribed_symbols.get(symbol, None)
    
    def is_symbol_subscribed(self, symbol: str) -> bool:
        """심볼이 구독 중인지 확인"""
        return symbol in self.subscribed_symbols
    
    def get_market_status_info(self, market: str = "us") -> Dict:
        """시장 상태 정보 조회
        
        Args:
            market: 시장 구분 ("us" 또는 "kr")
            
        Returns:
            Dict: 시장 상태 정보
        """
        return self.market_calendar.get_market_status(market)
    
    def get_upcoming_holidays(self, days_ahead: int = 30, market: str = "us") -> List[Dict]:
        """향후 공휴일 목록 조회
        
        Args:
            days_ahead: 조회할 앞으로의 일수
            market: 시장 구분 ("us" 또는 "kr")
            
        Returns:
            List[Dict]: 공휴일 정보 목록
        """
        return self.market_calendar.get_upcoming_holidays(days_ahead, market)
    
    def log_market_status(self):
        """현재 시장 상태를 로그에 출력"""
        us_status = self.get_market_status_info("us")
        kr_status = self.get_market_status_info("kr")
        
        logger.info("=== 시장 상태 정보 ===")
        logger.info(f"🇺🇸 미국 시장: {'🟢 OPEN' if us_status['is_open'] else '🔴 CLOSED'}")
        if us_status.get('is_holiday'):
            logger.info(f"   📅 공휴일: {us_status['current_time'][:10]}")
        if us_status.get('is_early_close'):
            logger.info(f"   ⏰ 조기 마감일")
            
        logger.info(f"🇰🇷 한국 시장: {'🟢 OPEN' if kr_status['is_open'] else '🔴 CLOSED'}")
        
        # 향후 공휴일 표시 (미국 & 한국)
        us_upcoming = self.get_upcoming_holidays(7, "us")  # 일주일 내 미국 공휴일
        kr_upcoming = self.get_upcoming_holidays(7, "kr")  # 일주일 내 한국 공휴일
        
        all_upcoming = us_upcoming + kr_upcoming
        if all_upcoming:
            logger.info("📅 향후 7일 내 공휴일:")
            for holiday in sorted(all_upcoming, key=lambda x: x['date'])[:5]:  # 최대 5개까지만 표시
                logger.info(f"   • {holiday['date']}: {holiday['name']} ({holiday['market']})")
        
        logger.info("====================") 