import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from src_rev.domain.models import InfiniteConfig, Symbol, Money
from src_rev.domain.common import Percentage

logger = logging.getLogger(__name__)

class ConfigLoader:
    """기존 config.yaml 파일을 로드하여 도메인 설정 객체로 변환"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._raw_config = {}
        
    def load(self) -> Tuple[InfiniteConfig, Dict[str, Any]]:
        """
        설정 파일을 읽어서 (InfiniteConfig, SystemConfig) 튜플 반환.
        SystemConfig는 API 키, 텔레그램 토큰 등을 포함한 딕셔너리.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._raw_config = yaml.safe_load(f)
                
            # 1. Domain Config 생성
            trading_conf = self._raw_config.get("trading", {}).get("infinite_buying_strategy", {})
            
            domain_config = InfiniteConfig(
                symbol=Symbol(trading_conf.get("symbol", "SOXL")),
                total_investment=Money(float(trading_conf.get("total_investment", 10000))),
                division_count=int(trading_conf.get("division_count", 40)),
                max_profit_rate=Percentage(float(trading_conf.get("max_profit_rate", 10.0))),
                min_profit_rate=Percentage(float(trading_conf.get("min_profit_rate", 5.0))),
                star_adjustment_rate=Percentage(float(trading_conf.get("star_adjustment_rate", 0.0)))
            )
            
            # 2. System Settings 추출
            system_config = {
                "telegram": self._raw_config.get("telegram", {}),
                "api": self._raw_config.get("api", {})
            }
            
            logger.info(f"Config loaded successfully from {self.config_path}")
            return domain_config, system_config
            
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            raise
