import pytest
from src.ui import app


def test_app_import():
    assert app is not None, "Streamlit UI 모듈이 로드되지 않음"


def test_app_launch():
    # 가정: app 모듈에 run_app 함수가 정의되어 있다면 이를 호출하여 초기화 테스트
    if hasattr(app, 'run_app'):
        try:
            # run_app이 blocking 없이 초기화를 완료한다고 가정
            app.run_app()
        except Exception as e:
            pytest.fail(f"Streamlit UI 실행 중 예외 발생: {e}")
    else:
        pytest.skip("run_app 함수가 정의되지 않음") 