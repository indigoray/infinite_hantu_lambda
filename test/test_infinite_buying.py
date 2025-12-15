import pytest
from src.strategy import infinite_buying


def test_infinite_buying_initialization():
    try:
        # 가정: infinite_buying 모듈에 InfiniteBuyingStrategy 클래스가 존재함
        strategy = infinite_buying.InfiniteBuyingStrategy(
            name='TestStrategy',
            description='전략 초기화 테스트',
            period='1분',
            ticker='SOXL',
            params={},
            account='TestAccount',
            funds=1000
        )
        assert strategy is not None, 'InfiniteBuyingStrategy 인스턴스 생성 실패'
    except Exception as e:
        pytest.fail(f'InfiniteBuyingStrategy 초기화 중 예외 발생: {e}') 