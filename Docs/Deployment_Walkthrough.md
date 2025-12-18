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

## 주요 알고리즘 변경사항
- **정밀한 T값**: 회차 계산 시 소수점 단위(예: 8.9회차)까지 계산하여 보여줍니다.
- **전반전/후반전 매수 로직 강화**:
  - **전반전(T≤20)**: Star 매수 + 평단 매수.
  - **후반전(T>20)**: Star 매수 전액 + 평단 매수 없음.
- **거미줄 매수(Additional Buy)**:
  - 공식: `1일매수금 / (Star수량 + 평단매수수량 + i)` 가격에 1주씩 LOC 매수.
  - 평단가 대비 최대 **-12%** 구간까지 촘촘하게 추가 매수 주문을 생성합니다. (메시지 길이 제한 고려)
  - **대이격 대응**: 평단가가 현재가보다 **2% 이상** 높을 경우, 주문 수를 줄이기 위해 구간별로 수량을 합칩니다.
    - 현재가 +2% 이상 구간: **4주**씩 묶음 주문
    - 현재가 +2% 이하 구간: **2주**씩 묶음 주문
    - (그 외 평범한 구간은 1주씩 주문)
- **Star 매도**: `Star가격 + 0.01`로 LOC 매도 주문을 내어 현금을 확보합니다.
