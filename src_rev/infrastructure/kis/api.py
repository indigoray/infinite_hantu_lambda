import logging
import time
import requests
from typing import List, Optional, Dict

from .auth import KisAuth
from ...domain.models import Position, Order, OrderType, OrderSide
from ...domain.common import Symbol, Money, Quantity

logger = logging.getLogger(__name__)

class KisApi:
    """KIS API Client Implementation"""
    
    def __init__(self, auth: KisAuth, account_number: str):
        self.auth = auth
        self.account_number = account_number
        self.cano = account_number[:8]
        self.acnt_prdt_cd = account_number[8:]
        
    def get_market_price(self, symbol: Symbol) -> Money:
        """현재가 조회 (해외주식)"""
        url = f"{self.auth.get_base_url()}/uapi/overseas-price/v1/quotations/price"
        
        # TR ID: HHDFS00000300 (실전), VHHDFS00000300 (모의)
        tr_id = "VHHDFS00000300" if self.auth.is_virtual else "HHDFS00000300"
        
        try:
            headers = self._get_headers(tr_id)
            params = {
                "AUTH": "",
                "EXCD": "NAS",  # 일단 NASDAQ 하드코딩 (추후 확장)
                "SYMB": symbol
            }
            
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            
            if data["rt_cd"] != "0":
                logger.error(f"Price check failed: {data['msg1']}")
                return Money(0.0)
                
            last_price = float(data["output"]["last"])
            return Money(last_price)
            
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return Money(0.0)

    def get_position(self, symbol: Symbol) -> Position:
        """잔고 조회 및 Position 객체 반환"""
        url = f"{self.auth.get_base_url()}/uapi/overseas-stock/v1/trading/inquire-balance"
        tr_id = "VTTS3012R" if self.auth.is_virtual else "TTTS3012R"
        
        try:
            headers = self._get_headers(tr_id)
            params = {
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }
            
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            
            if data["rt_cd"] != "0":
                logger.error(f"Balance check failed: {data['msg1']}")
                # 에러 시 빈 포지션 반환 (안전가드)
                return Position(symbol, Quantity(0), Money(0.0))
                
            # 해당 심볼 찾기
            output = data.get("output1", [])
            for item in output:
                if item["OVRS_PDNO"] == symbol:
                    qty = int(float(item["OVRS_CBLC_QTY"]))
                    avg_price = float(item["PCHS_AVG_PRIC"])
                    
                    # 현재가도 같이 조회해서 업데이트
                    current_price = float(item.get("NOW_PRIC2", 0.0))
                    
                    # 현재가가 0이면 별도 API로 조회
                    if current_price == 0:
                        current_price = self.get_market_price(symbol)
                    
                    return Position(
                        symbol=Symbol(symbol),
                        quantity=Quantity(qty),
                        avg_price=Money(avg_price),
                        current_price=Money(current_price)
                    )
            
            # 보유 주식 없음
            current_price = self.get_market_price(symbol)
            return Position(symbol, Quantity(0), Money(0.0), Money(current_price))

        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return Position(symbol, Quantity(0), Money(0.0))

    def place_order(self, order: Order) -> bool:
        """주문 실행"""
        url = f"{self.auth.get_base_url()}/uapi/overseas-stock/v1/trading/order"
        
        # TR ID 설정
        if order.side == OrderSide.BUY:
            tr_id = "VTTT1002U" if self.auth.is_virtual else "TTTT1002U"
            sll_buy_dvsn_cd = "02"
        else:
            tr_id = "VTTT1006U" if self.auth.is_virtual else "TTTT1006U"
            sll_buy_dvsn_cd = "01"
            
        # 주문 유형 매핑 (LOC, AFTER, LIMIT)
        ord_dvsn_map = {
            OrderType.LOC: "34",
            OrderType.AFTER_MARKET: "32",
            OrderType.LIMIT: "00",
            OrderType.MARKET: "00" # 해외주식 시장가는 보통 없거나 00으로 처리
        }
        
        try:
            headers = self._get_headers(tr_id)
            body = {
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "OVRS_EXCG_CD": "NASD",
                "PDNO": order.symbol,
                "ORD_QTY": str(order.quantity),
                "OVRS_ORD_UNPR": str(order.price),
                "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
                "ORD_DVSN": ord_dvsn_map.get(order.order_type, "00"),
                "ORD_SVR_DVSN_CD": "0" # "1" for server auto, but stick to standard
            }
            
            res = requests.post(url, headers=headers, json=body)
            data = res.json()
            
            if data["rt_cd"] != "0":
                logger.error(f"Order failed: {data['msg1']} ({data['msg_cd']})")
                return False
                
            logger.info(f"Order Success: {data['msg1']} (Order No: {data['output']['ODNO']})")
            return True
            
        except Exception as e:
            logger.error(f"Order exception: {e}")
            return False

    def _get_headers(self, tr_id: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.auth.get_token()}",
            "appkey": self.auth.app_key,
            "appsecret": self.auth.app_secret,
            "tr_id": tr_id
        }
