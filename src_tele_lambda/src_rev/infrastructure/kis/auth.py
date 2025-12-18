import logging
import time
import json
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KisAuth:
    """KIS API 인증 및 토큰 관리"""
    
    def __init__(self, key: str, secret: str, is_virtual: bool = True):
        self.app_key = key
        self.app_secret = secret
        self.is_virtual = is_virtual
        self.base_url = (
            "https://openapivts.koreainvestment.com:29443" 
            if is_virtual else 
            "https://openapi.koreainvestment.com:9443"
        )
        self.access_token = None
        self.token_expiry = 0
        
    def get_token(self) -> str:
        """유효한 액세스 토큰 반환 (만료 시 갱신)"""
        if not self.access_token or time.time() > self.token_expiry:
            self._refresh_token()
        return self.access_token
        
    def _refresh_token(self):
        """토큰 발급 요청"""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = requests.post(url, headers=headers, json=body)
            # res.raise_for_status() # 4xx, 5xx 에러 시 예외 발생
            
            data = res.json()
            if "access_token" not in data:
                raise ValueError(f"Token response invalid: {data}")
                
            self.access_token = data["access_token"]
            # 토큰 유효기간 (보통 24시간이나 안전하게 23시간으로 설정)
            self.token_expiry = time.time() + 82800 
            
            logger.info(f"KIS Access Token refreshed. Expiry: {self.token_expiry}")
            
        except Exception as e:
            logger.error(f"Failed to refresh KIS token: {e}")
            raise

    def get_base_url(self) -> str:
        return self.base_url
