# 요구사항 정의서: 도서관 좌석 유령 예약 감지 시스템 (Ghost Seat Detector)

## 소개

대학 도서관에서 좌석을 예약만 하고 실제로 사용하지 않거나, 짐만 놓고 장시간 자리를 비우는 "유령 예약" 문제를 해결하기 위한 시스템이다. 휴대폰 카메라를 활용한 스냅샷 촬영과 AI 이미지 분석을 통해 좌석 점유 상태를 자동으로 판단하고, 경고 및 자동 반납 처리를 수행한다. 미예약 좌석의 무단 점유도 감지하여 관리자에게 알린다.

---

## 용어 정의 (Glossary)

- **Ghost_Seat_Detector**: 도서관 좌석 유령 예약 감지 시스템 전체를 지칭
- **ghostSeatDetector**: 모든 백엔드 로직을 처리하는 단일 Lambda 함수
- **Student_Page**: 학생이 좌석을 예약하고 현황을 확인하는 프론트엔드 페이지 (/)
- **Admin_Page**: 관리자가 전체 좌석 상태 확인 + 카메라 모니터링을 수행하는 프론트엔드 페이지 (/admin)
- **Seats_Table**: DynamoDB의 좌석 정보 단일 테이블 (Single Table Design)
- **Snapshot**: Admin_Page 카메라에서 촬영한 좌석 3개가 포함된 이미지 (base64 인코딩)
- **Seat_Label**: 각 좌석에 부착된 물리적 번호표 (1, 2, 3)
- **Absence_Count**: 사람 미감지 연속 횟수 (기본 최대 7회, 데모용 5회)
- **Warning_Count**: 학생에게 발송된 경고 횟수 (최대 2회)
- **AVAILABLE / RESERVED / OCCUPIED / ABSENT_WITH_STUFF / ABSENT_EMPTY / WARNING_SENT / AUTO_RETURNED**: 좌석 상태값

---

## 좌석 식별 방식

번호표 1→A1, 2→A2, 3→A3. AI가 번호표를 인식하여 좌석 구분.

## 사람 감지 기준

좌석에 앉아있는 자세만 person_present = true. 통행인, 서있는 사람은 false.

---

## 시스템 구조

### 페이지: 2개
- `/` — Student_Page, `/admin` — Admin_Page

### Lambda 함수: 1개 (ghostSeatDetector)
- GET /seats, GET /seats/{seat_id}, GET /events → 조회
- POST /seats/{seat_id}/reserve, POST /seats/{seat_id}/cancel → 예약/취소
- POST /snapshot → Bedrock 분석 + 상태 전이 + Slack 알림

### 호출 흐름
```
Admin_Page → POST /snapshot → ghostSeatDetector 내부:
  1. Bedrock 1회 호출 → 3좌석 분석
  2. 상태 전이 함수 직접 호출 (boto3 invoke 불필요)
  3. DynamoDB 업데이트 + Slack 알림 + 이벤트 로그
```

### 좌석: A1, A2, A3 (번호표 1/2/3)

---

## 기능 요구사항

### Req 1: 좌석 예약
- AVAILABLE 좌석 선택 → RESERVED 변경, 학생 정보 저장 (1인 1좌석 검증 없음)

### Req 2: 좌석 예약 취소
- 본인 좌석 취소 → AVAILABLE 변경, 학생 정보 제거
- 타인 좌석 취소 → 거부 (403)

### Req 3: 좌석 현황 조회
- GET /seats → 3좌석 상태/예약자/경고 반환
- 상태별 색상: AVAILABLE(초록), RESERVED(노랑), OCCUPIED(파랑), ABSENT_*/WARNING_SENT(주황), AUTO_RETURNED(빨강)

### Req 4: 카메라 스냅샷
- Admin_Page에서 getUserMedia → 5초 간격 자동 촬영 → base64 → POST /snapshot

### Req 5: AI 이미지 분석
- Bedrock Claude Haiku 1회 호출로 3좌석 동시 분석 (번호표 기반)
- 분석 완료 → 번호표→좌석 매핑 → 상태 전이 직접 실행
- Bedrock 실패 → 에러 로그 + 500 응답

### Req 6: 부재 모니터링 및 상태 전이
- 사람 감지 → OCCUPIED, absence_count=0
- 사람 미감지 → absence_count 증가
- 임계값 미만 → ABSENT_WITH_STUFF 또는 ABSENT_EMPTY
- 임계값 + 짐 없음 → AVAILABLE (자동 반납)
- 임계값 + 짐 있음 + warning=0 → WARNING_SENT, warning=1, absence_count=0, Slack 경고
- 임계값 + 짐 있음 + warning=1 → AVAILABLE (자동 반납), Slack 관리자 호출

### Req 7: 무단 점유 감지
- AVAILABLE 좌석에 사람/짐 감지 → Slack 관리자 알림
- 둘 다 미감지 → 무시

### Req 8: Slack 알림
- 학생 경고: "⚠️ 좌석 {seat_id}에서 장시간 이탈이 감지되었습니다."
- 관리자 호출: "🚨 좌석 {seat_id} 경고 2회 누적. 자동 반납 처리됨."
- 무단 점유: "👀 좌석 {seat_id}(미예약)에서 사람/짐이 감지되었습니다."
- Slack 실패 → 로그만, 좌석 상태 무영향

### Req 9: Student_Page
- 학번+이름 입력 로그인, 좌석 색상 카드, 예약/취소 버튼, 경고 배너, 5초 폴링

### Req 10: Admin_Page
- 좌석 카드 대시보드, 카메라 시작/중지, 스냅샷 자동 전송, 이벤트 로그, 5초 폴링

### Req 11: 환경변수
- SNAPSHOT_INTERVAL_SECONDS (기본 300, 데모 5), ABSENCE_THRESHOLD (기본 7, 데모 5)

### Req 12: 에러 처리
- Bedrock 타임아웃 30초, DynamoDB 실패→500, Slack 실패→로그만, 개별 좌석 실패→해당만 건너뜀

---

## DynamoDB 테이블: `ghost-seat-detector-seats` (Single Table, GSI 없음)

| PK | SK | 용도 |
|----|----|------|
| SEAT#A1 | METADATA | 좌석 상태 |
| EVENT#A1 | ISO 8601 | 이벤트 로그 |

속성: seat_id, seat_label, status, student_id, student_name, absence_count, warning_count, has_stuff, updated_at, event_type, event_detail, ttl

---

## API 명세 (모두 ghostSeatDetector Lambda)

| Method | Path | 설명 |
|--------|------|------|
| GET | /seats | 전체 좌석 조회 |
| GET | /seats/{seat_id} | 개별 좌석 조회 |
| GET | /events | 이벤트 로그 (limit 파라미터) |
| POST | /seats/{seat_id}/reserve | 예약 |
| POST | /seats/{seat_id}/cancel | 취소 |
| POST | /snapshot | 스냅샷 분석 |

CORS: Access-Control-Allow-Origin: *, Methods: GET/POST/OPTIONS, Headers: Content-Type

---

## Lambda 상세: ghostSeatDetector

| 항목 | 내용 |
|------|------|
| 타임아웃 | 90초 |
| 권한 | AmazonBedrockFullAccess, AmazonDynamoDBFullAccess |
| 환경변수 | SEATS_TABLE, ABSENCE_THRESHOLD, SLACK_STUDENT_WEBHOOK, SLACK_ADMIN_WEBHOOK |
