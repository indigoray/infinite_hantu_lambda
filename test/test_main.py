import pytest
import main


def test_main_import():
    assert main is not None, "메인 모듈 로드 실패" 