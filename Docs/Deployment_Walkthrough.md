# Cloud Run 배포 가이드 (Deployment Walkthrough)

## 개요 (Overview)
텔레그램 봇을 Google Cloud Run(Serverless)에 성공적으로 배포했습니다. 이 봇은 다중 거래 전략(SOXL, TQQQ)을 지원하며 웹훅을 통해 통신합니다.

## 구성 상세 (Configuration Details)
- **리전 (Region)**: `asia-northeast3` (서울)
- **런타임 (Runtime)**: Python 3.11
- **진입점 (Entry Point)**: `telegram_webhook` (`main.py`에 정의됨)
- **메모리 (Memory)**: 512MB (OOM 방지를 위해 256MB에서 증설)
- **환경 변수 (Environment Variables)**:
  - `FUNCTION_TARGET`: `telegram_webhook` (실행할 함수 이름을 명시적으로 지정)

## 주요 수정 사항 (Key Fixes Required)
배포 과정에서 다음과 같은 중요한 수정이 있었습니다:

1.  **진입점 감지 (`functions-framework`)**:
    - `requirements.txt`에 `functions-framework` 라이브러리를 추가했습니다.
    - `src_tele_lambda/Procfile`을 생성하고 `web: functions-framework --target=telegram_webhook` 명령을 명시하여 빌드백이 올바른 실행 명령을 사용하도록 강제했습니다.

2.  **설정 파일 문법 (Configuration Syntax)**:
    - `config.yaml` 파일의 문법을 Flow Style(JSON 형태)에서 표준 YAML Block Style로 수정했습니다.
    - `main.py`에서 기대하는 키 이름에 맞춰 `token`을 `bot_token`으로 변경했습니다.

## 검증 (Verification)
- **빌드**: GitHub Push를 통해 Cloud Build가 성공적으로 수행되었습니다.
- **통신**: 텔레그램 웹훅이 정상적으로 연결되었습니다.
- **봇 응답**: 봇이 `/start` 명령에 올바르게 응답하며 로직(계좌 조회, 사이클 보고)을 수행합니다.

## 사용법 (Usage)
텔레그램 봇 창에서 `/start`를 입력하면 메뉴가 보입니다:
1. **계좌 조회**: 실시간 잔고 및 평가금액 확인
2. **사이클 상황보고**: 무한매수 사이클 진행 상태 확인
3. **오늘의 주문예약**: 오늘 실행될 LOC 매수/매도 주문 미리보기

## 가상 시뮬레이션 모드 (Mock Mode)
실제 매매 없이 봇의 동작을 테스트하고 싶다면 Mock 모드를 사용하세요.

1.  `config/config.yaml` 에서 `mock_mode: true`로 설정합니다.
2.  배포 후 봇은 고정된 가상 데이터(SOXL 840주 등)를 기반으로 동작합니다.
3.  "오늘의 주문예약" 메뉴 하단에 **[주문 실행하기]** 버튼이 나타나며, 클릭 시 가상 주문이 체결됩니다.
