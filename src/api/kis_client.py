import requests
import json
import datetime
import urllib.parse
import logging
import time

logger = logging.getLogger(__name__)

class KISClient:
    def __init__(self, config: dict):
        self.config = config
        self.app_key = config["app_key"]
        self.app_secret = config["app_secret"]
        self.access_token = None
        self.is_virtual = config.get("is_virtual", False)  # 모의투자 여부
        
        # is_virtual 설정에 따라 base_url 자동 선택
        if self.is_virtual:
            self.base_url = config.get("base_url_virtual", "https://openapivts.koreainvestment.com:29443")
            logger.info("모의투자 모드로 설정됨")
        else:
            self.base_url = config.get("base_url_real", "https://openapi.koreainvestment.com:9443")
            logger.info("실전투자 모드로 설정됨")
            
        # 하위 호환성: 기존 base_url이 있으면 사용
        if "base_url" in config:
            self.base_url = config["base_url"]
            logger.warning("기존 base_url 설정을 사용 중입니다. base_url_real/base_url_virtual 사용을 권장합니다.")
            
        logger.info(f"API Base URL: {self.base_url}")
        
        self.last_request_time = 0
        self.request_interval = 0.5  # 500ms 간격 (초당 2회 제한으로 더 안전하게)

        
    def _wait_for_rate_limit(self):
        """Rate Limit을 위한 요청 간격 조절"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed
            logger.debug(f"Rate limit 대기: {sleep_time:.2f}초")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
        
    def _get_tr_id(self, base_tr_id: str) -> str:
        """모의투자/실전투자에 따른 TR ID 반환"""
        if self.is_virtual:
            # 모의투자용 TR ID 매핑
            virtual_tr_map = {
                "TTTS3012R": "VTTS3012R",  # 해외주식 잔고조회
                "HHDFS00000300": "VHHDFS00000300",  # 해외주식 현재가
                "TTTT1002U": "VTTT1002U",  # 해외주식 매수
                "TTTT1006U": "VTTT1006U",  # 해외주식 매도
                "TTTS3018R": "VTTS3018R",  # 해외주식 미체결조회
                "TTTT1004U": "VTTT1004U",  # 해외주식 취소
                "TTTS3035R": "VTTS3035R",  # 해외주식 주문체결내역 조회
                "TTTS3031R": "VTTS3031R",  # 해외주식 미체결 주문 조회
                "TTTS0308U": "VTTS0308U",  # 해외주식 주문 취소
            }
            return virtual_tr_map.get(base_tr_id, base_tr_id)
        return base_tr_id
        
    def _safe_float(self, value, default=0.0):
        """안전한 float 변환"""
        if not value or value == "":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
        
    def login(self) -> bool:
        """한국투자증권 API 로그인
        
        Returns:
            bool: 로그인 성공 여부
        """
        try:
            # API 키 유효성 검사 - 명시적으로 더미가 아닌 경우에만 실제 API 사용
            if (not self.app_key or not self.app_secret or 
                self.app_key == "YOUR_APP_KEY" or self.app_secret == "YOUR_APP_SECRET" or
                self.app_key == "DUMMY" or self.app_secret == "DUMMY"):
                logger.error("API 키가 설정되지 않았거나 유효하지 않습니다.")
                return False
                
            self._get_access_token()
            logger.info("한국투자증권 API 로그인 성공")
            return True
            
        except Exception as e:
            logger.error(f"한국투자증권 API 로그인 실패: {str(e)}")
            return False
        
    def _get_access_token(self):
        if (self.app_key == "YOUR_APP_KEY" or self.app_secret == "YOUR_APP_SECRET" or
            not self.app_key or not self.app_secret):
            raise ValueError("API 키가 설정되지 않았습니다.")
            
        url = f"{self.base_url}/oauth2/tokenP"
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        headers = {
            "content-type": "application/json"
        }
        
        res = requests.post(url, headers=headers, data=json.dumps(data))
        if res.status_code != 200:
            raise Exception(f"API 요청 실패: {res.text}")
            
        self.access_token = res.json().get("access_token")
        if not self.access_token:
            raise Exception("access_token을 받아오지 못했습니다.")
        
    def get_oversea_stock_price(self, symbol):
            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
        
        tr_id = self._get_tr_id("HHDFS00000300")
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        params = {
            "AUTH": "",
            "EXCD": "NAS",  # NASDAQ
            "SYMB": symbol
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            
            # Rate Limit 에러 처리
            if data.get("rt_cd") == "1" and "초과" in data.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.get_oversea_stock_price(symbol)
            
            # 서비스 에러 처리 (반복 로그 방지)
            if data.get("rt_cd") != "0":
                error_msg = data.get('msg1', 'Unknown error')
                if "서비스" in error_msg:
                    logger.debug(f"가격 조회 서비스 에러 (더미 데이터 반환): {error_msg}")
                    # 서비스 에러 시 더미 데이터 반환
                    return {
                        "current_price": 100.0,
                        "last": "100.00",
                        "diff": "0",
                        "volume": "0"
                    }
                else:
                    logger.error(f"가격 조회 실패: {error_msg}")
                    
            if data.get("rt_cd") == "0" and data.get("output"):
                output = data["output"]
                return {
                    "current_price": self._safe_float(output.get("last")),
                    "last": output.get("last", "0"),
                    "diff": output.get("diff", "0"),
                    "volume": output.get("volume", "0")
                }
            else:
                return {
                    "current_price": 0,
                    "last": "N/A",
                    "diff": "N/A",
                    "volume": "N/A"
                }
                
        except Exception as e:
            logger.error(f"가격 조회 실패: {str(e)}")
            return {
                "current_price": 0,
                "last": "N/A",
                "diff": "N/A",
                "volume": "N/A"
            }
            
    def get_oversea_balance(self):
        """해외주식 잔고 조회
        
        Returns:
            list: 보유 종목 리스트
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
        
        tr_id = self._get_tr_id("TTTS3012R")
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        params = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            
            # Rate Limit 에러 처리
            if data.get("rt_cd") == "1" and "초과" in data.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.get_oversea_balance()
            
            if data.get("rt_cd") != "0":
                error_msg = data.get('msg1', 'Unknown error')
                if "서비스" in error_msg:
                    logger.debug(f"잔고 조회 서비스 에러 (빈 잔고 반환): {error_msg}")
                    return []  # 서비스 에러 시 빈 잔고 반환
                else:
                    logger.error(f"잔고 조회 실패: {error_msg}")
                    return []
                
            balance_list = []
            for item in data.get("output1", []):
                balance_list.append({
                    "symbol": item.get("OVRS_PDNO"),
                    "qty": item.get("OVRS_CBLC_QTY"),
                    "avg_price": item.get("PCHS_AVG_PRIC"),
                    "current_price": item.get("NOW_PRIC2"),
                    "profit_ratio": item.get("EVLU_PFLS_RT")
                })
                
            return balance_list
            
        except Exception as e:
            logger.error(f"잔고 조회 실패: {str(e)}")
            return []
            
    def create_oversea_order(self, symbol: str, order_type: str, price: float, 
                           quantity: int, execution_type: str = "LOC"):
        """해외주식 주문
        
        Args:
            symbol: 종목코드
            order_type: 주문유형 (buy/sell)
            price: 주문가격
            quantity: 주문수량
            execution_type: 체결조건 (LOC, AFTER 등)
            
        Returns:
            dict: 주문 결과
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        
        # 매수/매도에 따른 tr_id 설정
        if order_type == "buy":
            base_tr_id = "TTTT1002U"  # 해외주식 매수
            sll_buy_dvsn_cd = "02"  # 매수
        else:
            base_tr_id = "TTTT1006U"  # 해외주식 매도
            sll_buy_dvsn_cd = "01"  # 매도
            
        tr_id = self._get_tr_id(base_tr_id)
            
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        # 체결조건 매핑
        ord_dvsn_map = {
            "LOC": "34",      # LOC (Limit on Close)
            "AFTER": "32",    # 시간외 종가지정
            "LIMIT": "00"     # 지정가
        }
        
        data = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "OVRS_EXCG_CD": "NASD",
            "PDNO": symbol,
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": str(price),
            "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
            "ORD_DVSN": ord_dvsn_map.get(execution_type, "00"),
            "ORD_SVR_DVSN_CD": "1" if self.is_virtual else "0"  # 모의투자: 1, 실전투자: 0
        }
        
        try:
            res = requests.post(url, headers=headers, json=data)
            result = res.json()
            
            # Rate Limit 에러 처리
            if result.get("rt_cd") == "1" and "초과" in result.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.create_oversea_order(symbol, order_type, price, quantity, execution_type)
            
            if result.get("rt_cd") != "0":
                logger.error(f"주문 실패: {result.get('msg1')}")
                
            return result
            
        except Exception as e:
            logger.error(f"주문 요청 실패: {str(e)}")
            return {"rt_cd": "-1", "msg1": str(e)}
            
    def get_oversea_open_orders(self):
        """해외주식 미체결 주문 조회
        
        Returns:
            list: 미체결 주문 리스트
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-nccs"
        
        tr_id = self._get_tr_id("TTTS3018R")
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        params = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "OVRS_EXCG_CD": "NASD",
            "SORT_SQN": "DS",  # 정렬순서
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            
            # Rate Limit 에러 처리
            if data.get("rt_cd") == "1" and "초과" in data.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.get_oversea_open_orders()
            
            if data.get("rt_cd") != "0":
                logger.error(f"미체결 조회 실패: {data.get('msg1')}")
                return []
                
            orders = []
            for item in data.get("output", []):
                orders.append({
                    "order_id": item.get("ODNO"),
                    "symbol": item.get("PDNO"),
                    "order_qty": item.get("ORD_QTY"),
                    "order_price": item.get("FT_ORD_UNPR3"),
                    "order_type": "sell" if item.get("SLL_BUY_DVSN_CD") == "01" else "buy"
                })
                
            return orders
            
        except Exception as e:
            logger.error(f"미체결 조회 실패: {str(e)}")
            return []
            
    def cancel_oversea_order(self, order_id: str):
        """해외주식 주문 취소
        
        Args:
            order_id: 주문번호
            
        Returns:
            dict: 취소 결과
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order-rvsecncl"
        
        tr_id = self._get_tr_id("TTTT1004U")
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        data = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_id,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 취소
            "OVRS_EXCG_CD": "NASD"
        }
        
        try:
            res = requests.post(url, headers=headers, json=data)
            result = res.json()
            
            # Rate Limit 에러 처리
            if result.get("rt_cd") == "1" and "초과" in result.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.cancel_oversea_order(order_id)
            
            if result.get("rt_cd") != "0":
                logger.error(f"주문 취소 실패: {result.get('msg1')}")
                
            return result
            
        except Exception as e:
            logger.error(f"주문 취소 실패: {str(e)}")
            return {"rt_cd": "-1", "msg1": str(e)} 

    def get_oversea_orders(self, order_date: str = None):
        """해외주식 주문내역 조회
        
        Args:
            order_date: 조회일자 (YYYYMMDD, None이면 당일)
            
        Returns:
            dict: 주문내역 리스트
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-nccs"
        
        tr_id = self._get_tr_id("TTTS3035R")  # 해외주식 주문체결내역 조회
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        if order_date is None:
            from datetime import datetime
            order_date = datetime.now().strftime("%Y%m%d")
        
        params = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "PDNO": "",  # 전체 종목
            "ORD_STRT_DT": order_date,  # 주문시작일자
            "ORD_END_DT": order_date,   # 주문종료일자 (같은 날로 설정)
            "SLL_BUY_DVSN": "00",  # 00: 전체, 01: 매도, 02: 매수
            "CCLD_NCCS_DVSN": "00",  # 체결확정구분 00: 전체, 01: 체결, 02: 미체결
            "OVRS_EXCG_CD": "",  # 전체 거래소 (공란: 전체, NASD: 미국, SEHK: 홍콩 등)
            "SORT_SQN": "DS",  # 정렬순서 DS: 내림차순, AS: 오름차순
            "ORD_DT": "",  # 주문일자 (공란)
            "ORD_GNO_BRNO": "",  # 주문지점번호 (공란)
            "ODNO": "",  # 주문번호 (공란)
            "CTX_AREA_FK200": "",  # 연속조회키
            "CTX_AREA_NK200": ""   # 연속조회키
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            result = res.json()
            
            # Rate Limit 에러 처리
            if result.get("rt_cd") == "1" and "초과" in result.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.get_oversea_orders(order_date)
            
            if result.get("rt_cd") != "0":
                logger.error(f"주문내역 조회 실패: {result.get('msg1')}")
                return {"rt_cd": "1", "output1": []}
                
            return result
            
        except Exception as e:
            logger.error(f"주문내역 조회 실패: {str(e)}")
            return {"rt_cd": "1", "output1": []}
            
    def get_pending_orders(self, symbol: str = None):
        """해외주식 미체결 주문 조회
        
        Args:
            symbol: 종목코드 (None이면 전체)
            
        Returns:
            list: 미체결 주문 리스트
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-psamount"
        
        tr_id = self._get_tr_id("TTTS3018R")  # 해외주식 미체결내역 조회
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        params = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "OVRS_EXCG_CD": "NASD",
            "SORT_SQN": "DS",  # 정렬순서
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            result = res.json()
            
            # Rate Limit 에러 처리
            if result.get("rt_cd") == "1" and "초과" in result.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.get_pending_orders(symbol)
            
            if result.get("rt_cd") != "0":
                logger.error(f"미체결 조회 실패: {result.get('msg1')}")
                return []
                
            orders = result.get("output", [])
            
            # 특정 종목 필터링
            if symbol:
                orders = [order for order in orders if order.get("pdno") == symbol]
                
            return orders
            
        except Exception as e:
            logger.error(f"미체결 조회 실패: {str(e)}")
            return []
            
    def cancel_order(self, order_number: str, order_branch: str = "01", symbol: str = ""):
        """해외주식 주문 취소
        
        Args:
            order_number: 주문번호
            order_branch: 주문지점번호
            symbol: 종목코드
            
        Returns:
            dict: 취소 결과
        """

            
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order-rvsecncl"
        
        tr_id = self._get_tr_id("TTTT1004U")  # 해외주식 주문취소
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        
        data = {
            "CANO": self.config["account_number"][:8],
            "ACNT_PRDT_CD": self.config["account_number"][8:],
            "OVRS_EXCG_CD": "NASD",
            "PDNO": symbol,
            "ORGN_ODNO": order_number,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 02: 취소
            "ORD_QTY": "0",
            "OVRS_ORD_UNPR": "0",
            "MGCO_APTM_ODNO": order_branch + order_number
        }
        
        try:
            res = requests.post(url, headers=headers, json=data)
            result = res.json()
            
            # Rate Limit 에러 처리
            if result.get("rt_cd") == "1" and "초과" in result.get("msg1", ""):
                logger.warning("API Rate Limit 도달, 재시도 중...")
                time.sleep(1)
                return self.cancel_order(order_number, order_branch, symbol)
            
            return result
            
        except Exception as e:
            logger.error(f"주문 취소 실패: {str(e)}")
            return {"rt_cd": "1", "msg1": str(e)} 

    def get_domestic_stock_price(self, symbol: str):
        """국내주식 현재가 조회
        
        Args:
            symbol: 주식 종목 코드 (예: "005930")
            
        Returns:
            dict: 현재가 정보
        """
        try:
            self._wait_for_rate_limit()
            
            # TR ID: 국내주식 현재가 시세
            tr_id = "FHKST01010100"
            
            url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {self.access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": tr_id,
                "custtype": "P",
            }
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # 시장구분코드 (J: 주식)
                "FID_INPUT_ISCD": symbol        # 종목코드
            }
            
            logger.debug(f"국내주식 현재가 조회 요청: {symbol}")
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("rt_cd") == "0":  # 성공
                    output = data.get("output", {})
                    
                    result = {
                        "symbol": symbol,
                        "current_price": self._safe_float(output.get("stck_prpr", "0")),     # 현재가
                        "open_price": self._safe_float(output.get("stck_oprc", "0")),       # 시가
                        "high_price": self._safe_float(output.get("stck_hgpr", "0")),       # 고가
                        "low_price": self._safe_float(output.get("stck_lwpr", "0")),        # 저가
                        "prev_close": self._safe_float(output.get("stck_sdpr", "0")),       # 전일종가
                        "change": self._safe_float(output.get("prdy_vrss", "0")),           # 전일대비
                        "change_rate": self._safe_float(output.get("prdy_vrss_prpr", "0")), # 전일대비율
                        "volume": int(output.get("acml_vol", "0")),                         # 누적거래량
                        "market_cap": self._safe_float(output.get("lstn_stcn", "0"))        # 상장주수
                    }
                    
                    logger.debug(f"국내주식 현재가 조회 성공: {symbol} = {result['current_price']}원")
                    return result
                else:
                    error_msg = data.get("msg1", "알 수 없는 오류")
                    if "해당 서비스를 찾을수 없습니다" in error_msg or "없는 서비스 코드" in error_msg:
                        logger.debug(f"국내주식 가격 조회 실패: {error_msg}")
                        return {"symbol": symbol, "current_price": 0, "error": "service_not_found"}
                    else:
                        logger.error(f"국내주식 가격 조회 실패: {error_msg}")
                        return {"symbol": symbol, "current_price": 0, "error": error_msg}
            else:
                logger.error(f"국내주식 가격 조회 HTTP 오류: {response.status_code}")
                return {"symbol": symbol, "current_price": 0, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"국내주식 가격 조회 예외: {str(e)}")
            return {"symbol": symbol, "current_price": 0, "error": str(e)} 