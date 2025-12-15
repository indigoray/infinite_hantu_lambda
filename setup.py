from setuptools import setup, find_packages

setup(
    name="infinite_hantu",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "streamlit==1.41.0",
        "plotly==5.18.0",
        "pyyaml==6.0.1",
        "requests==2.31.0",
        "websockets==12.0",
        "pandas==2.2.0",
        "numpy==1.26.3",
    ],
    entry_points={
        'console_scripts': [
            'infinite-hantu=src.ui.app:main',  # 메인 UI 실행
            'infinite-daemon=src.strategy.infinite_buying:run_daemon',  # 데몬 실행
        ],
    }
) 