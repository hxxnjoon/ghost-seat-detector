---
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# Python 백엔드 코딩 가이드

## Lambda 함수 구조
- 각 Lambda는 `backend/lambdas/{함수명}/lambda_function.py`에 위치
- 공통 모듈은 `backend/shared/`에 위치 (constants.py, dynamodb.py, response.py)
- 핸들러 함수명: `lambda_handler(event, context)`

## 코딩 규칙
- Python 3.12 기준
- 타입 힌트 사용 (typing 모듈)
- docstring은 한국어로 작성
- 환경변수는 `os.environ.get('KEY', 'default')` 패턴 사용
- 로깅: `import logging; logger = logging.getLogger(); logger.setLevel(logging.INFO)`

## DynamoDB 접근
- boto3 resource 대신 `boto3.resource('dynamodb')` 사용
- 테이블명: 환경변수 `SEATS_TABLE` (기본값: `ghost-seat-detector-seats`)
- PK/SK 패턴: `SEAT#A1` + `METADATA`, `EVENT#A1` + ISO 8601 타임스탬프

## 에러 처리
- 모든 Lambda 핸들러는 try/except로 감싸기
- 에러 시 logger.error() 후 적절한 HTTP 상태 코드 반환
- Slack 실패는 좌석 상태에 영향 없음 (비차단)

## 응답 형식
- 모든 응답에 CORS 헤더 포함
- `response.py`의 헬퍼 함수 사용: `success_response(body)`, `error_response(status, message)`

## 테스트
- pytest + hypothesis 사용
- 테스트 파일: `backend/tests/` 디렉토리
- 속성 기반 테스트: `@given()` 데코레이터, 최소 100회 반복
- 태그 형식: `Feature: ghost-seat-detector, Property {N}: {설명}`
