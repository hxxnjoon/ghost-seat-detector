---
inclusion: fileMatch
fileMatchPattern: "**/*dynamo*"
---

# DynamoDB Single Table Design 가이드

## 테이블 정보
- 테이블명: `ghost-seat-detector-seats`
- Partition Key: `PK` (String)
- Sort Key: `SK` (String)
- GSI: 없음 (좌석 3개이므로 불필요)

## 엔티티 패턴

### 좌석 메타데이터
- PK: `SEAT#{seat_id}` (예: `SEAT#A1`)
- SK: `METADATA`
- 속성: seat_id, seat_label, status, student_id, student_name, absence_count, warning_count, has_stuff, updated_at

### 이벤트 로그
- PK: `EVENT#{seat_id}` (예: `EVENT#A1`)
- SK: ISO 8601 타임스탬프 (예: `2026-03-23T10:30:00Z`)
- 속성: seat_id, event_type, event_detail, created_at, ttl

## 접근 패턴
- 개별 좌석 조회: `GetItem(PK=SEAT#A1, SK=METADATA)`
- 전체 좌석 조회: `BatchGetItem` (3개 키)
- 1인 1좌석 검증: `BatchGetItem` 후 student_id 필터
- 이벤트 저장: `PutItem(PK=EVENT#A1, SK=timestamp)`
- 이벤트 조회: `Query(PK=EVENT#A1, ScanIndexForward=False)`
- 전체 이벤트: 3좌석 Query 후 병합 정렬

## 주의사항
- updated_at은 모든 상태 변경 시 갱신
- 이벤트 로그 TTL: 24시간 (86400초)
- 빈 문자열("")은 DynamoDB에서 허용됨 (student_id, student_name 초기값)
- 상태 변경 시 반드시 이벤트 로그도 함께 저장
