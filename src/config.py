import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional

class Config:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_path = self.base_dir / "config" / "config.yaml"
        self.load_config()

    def load_config(self):
        """설정 파일 로드"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
            
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        # 주요 설정 섹션들을 객체 속성으로 설정
        self.api = self.config.get("api", {})
        self.telegram = self.config.get("telegram", {})
        self.trading = self.config.get("trading", {})
        
        # 하위 호환성을 위한 설정
        self._setup_backward_compatibility()
        
    def _setup_backward_compatibility(self):
        """하위 호환성을 위한 설정"""
        # 기존 base_url이 있으면 사용
        if "base_url" in self.api and not self.api.get("base_url_real"):
            self.api["base_url_real"] = self.api["base_url"]
            
        # 기존 trading 설정을 infinite_buying_strategy로 마이그레이션 (하위 호환성)
        if "infinite_buying_strategy" not in self.trading:
            self.trading["infinite_buying_strategy"] = {
                "symbol": self.trading.get("symbol", "SOXL"),
                "total_investment": self.trading.get("initial_investment", 1000000),
                "division_count": 40,
                "max_profit_rate": 12,
                "min_profit_rate": 8,
                "star_adjustment_rate": 0
            }
        
        # 기존 일반 거래 설정 제거 (전략별 설정으로 대체됨)
        if "symbol" in self.trading and "infinite_buying_strategy" in self.trading:
            # 기존 symbol 설정이 infinite_buying_strategy에 이미 있으면 제거
            if "symbol" in self.trading:
                del self.trading["symbol"]
            if "initial_investment" in self.trading:
                del self.trading["initial_investment"]
            if "dca_amount" in self.trading:
                del self.trading["dca_amount"]
            if "profit_target" in self.trading:
                del self.trading["profit_target"]
            if "interval" in self.trading:
                del self.trading["interval"]
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회 (점 표기법 지원)"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_api_config(self) -> Dict[str, Any]:
        """API 설정 반환"""
        return self.api
    
    def get_telegram_config(self) -> Dict[str, Any]:
        """텔레그램 설정 반환"""
        return self.telegram
    
    def get_trading_config(self) -> Dict[str, Any]:
        """거래 설정 반환"""
        return self.trading
    
    def get_infinite_buying_config(self) -> Dict[str, Any]:
        """무한매수 전략 설정 반환"""
        return self.trading.get("infinite_buying_strategy", {})
    
    def is_virtual_trading(self) -> bool:
        """모의투자 여부 확인"""
        return self.api.get("is_virtual", True)
    
    def get_api_url(self) -> str:
        """현재 모드에 따른 API URL 반환"""
        if self.is_virtual_trading():
            return self.api.get("base_url_virtual", "https://openapivts.koreainvestment.com:29443")
        else:
            return self.api.get("base_url_real", "https://openapi.koreainvestment.com:9443")
    
    def validate_config(self) -> bool:
        """설정 파일 유효성 검증"""
        required_fields = [
            "api.app_key",
            "api.app_secret", 
            "api.account_number",
            "trading.infinite_buying_strategy.symbol",
            "trading.infinite_buying_strategy.total_investment"
        ]
        
        for field in required_fields:
            if self.get(field) is None:
                raise ValueError(f"필수 설정이 누락되었습니다: {field}")
        
        return True
    
    def save_config(self):
        """설정 파일 저장"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    def update_config(self, updates: Dict[str, Any]):
        """설정 업데이트"""
        def deep_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        
        self.config = deep_update(self.config, updates)
        self.load_config()  # 설정 다시 로드
        