---
inclusion: always
---

# Ghost Seat Detector - 프로젝트 개요

## 프로젝트
도서관 좌석 유령 예약 감지 시스템. 카메라 1대로 번호표(1,2,3)가 부착된 3개 좌석을 동시에 촬영하고, Amazon Bedrock Claude Haiku로 AI 분석하여 유령 예약을 자동 감지·경고·반납 처리한다.

## 기술 스택
- 프론트엔드: React + JavaScript + Vite, Amplify Hosting
- 백엔드: Python 3.12 Lambda × 1개 (통합), API Gateway (REST, 프록시 통합)
- AI: Amazon Bedrock Claude Haiku (이미지 분석)
- DB: DynamoDB Single Table Design (테이블명: `ghost-seat-detector-seats`, GSI 없음)
- 알림: Slack Incoming Webhook
- 인프라: AWS 콘솔 수동 생성 (CDK/SAM 미사용)
- 인증: 없음 (학번+이름 단순 입력)
- 이미지: base64 직접 전송 (S3 미사용)

## 프로젝트 구조
```
backend/
  lambda_function.py          # 단일 Lambda (모든 백엔드 로직)
frontend/
  src/
    pages/StudentPage.jsx, AdminPage.jsx
    api.js, constants.js, utils.js
```

## Lambda 함수 1개 (ghostSeatDetector)
- `GET /seats` → 전체 좌석 조회
- `GET /seats/{seat_id}` → 개별 좌석 조회
- `GET /events` → 이벤트 로그 조회
- `POST /seats/{seat_id}/reserve` → 예약
- `POST /seats/{seat_id}/cancel` → 취소
- `POST /snapshot` → Bedrock 분석 + 상태 전이 + Slack 알림

## 페이지 2개
- `/` — Student_Page (학번+이름 로그인, 예약/취소, 경고 배너)
- `/admin` — Admin_Page (좌석 대시보드 + 카메라 모니터링 + 이벤트 로그)

## 좌석 3개
A1(번호표 1), A2(번호표 2), A3(번호표 3)

## 핵심 설계 결정
- Lambda 1개 통합 — boto3 invoke 불필요, AWS 콘솔 세팅 간소화
- 카메라 1대 → Bedrock 1회 호출로 3좌석 동시 분석
- "앉아있는 자세"만 사람 감지로 인정
- 번호표 기반 좌석 식별
- 5초 폴링으로 실시간 갱신
- 1인 1좌석 검증 없음 (단순 예약)
- 자동 테스트 없음 (수동 테스트)

## 스펙 문서 위치
- 요구사항: #[[file:.kiro/specs/ghost-seat-detector/requirements.md]]
- 설계: #[[file:.kiro/specs/ghost-seat-detector/design.md]]
- 태스크: #[[file:.kiro/specs/ghost-seat-detector/tasks.md]]
