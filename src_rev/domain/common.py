from decimal import Decimal
from typing import NewType, Union

# 타입 안전성을 위한 Value Types
Symbol = NewType("Symbol", str)  # 예: "SOXL"
Money = NewType("Money", float) # 원화/달러
Quantity = NewType("Quantity", int)
Percentage = NewType("Percentage", float) # 10.5% -> 10.5

def to_decimal(value: Union[float, int, str]) -> Decimal:
    """금융 계산을 위한 Decimal 변환 헬퍼"""
    return Decimal(str(value))
