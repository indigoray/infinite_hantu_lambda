import pytest
from src.api import kis_client


def test_create_client():
    try:
        client = kis_client.KISClient()  # 가정: KISClient 클래스가 있음
        assert client is not None, "KISClient 인스턴스가 생성되지 않음"
    except Exception as e:
        pytest.fail(f"KISClient 생성 중 예외 발생: {e}") 