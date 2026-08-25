# 구현 계획: 도서관 좌석 유령 예약 감지 시스템 (Ghost Seat Detector)

## 개요

백엔드(Python 3.12 Lambda 1개) → 프론트엔드(React + JavaScript, Vite) 순서로 구현한다. Lambda는 단일 파일(`lambda_function.py`)로 작성하며, API Gateway의 HTTP method와 path를 보고 내부에서 라우팅한다. shared 모듈 없이 모든 코드를 한 파일에 직접 포함한다. AWS 콘솔 인라인 에디터에 바로 붙여넣을 수 있도록 한다. 테스트는 수동으로 진행한다.

## Tasks

- [x] 1. 통합 Lambda 함수 구현 (단일 파일)
  - [x] 1.1 lambda_function.py 작성
    - `backend/lambda_function.py`에 모든 백엔드 로직을 단일 파일로 작성
    - 파일 내 직접 정의: DynamoDB 클라이언트, Bedrock 클라이언트, 테이블명(환경변수), CORS 헤더, 상수(SEAT_IDS, LABEL_TO_SEAT 등)
    - **라우팅 구조** (lambda_handler에서 HTTP method + path로 분기):
      - `GET /seats` → 전체 좌석 조회 (BatchGetItem)
      - `GET /seats/{seat_id}` → 개별 좌석 조회 (GetItem)
      - `GET /events` → 이벤트 로그 조회 (Query × 3, 시간순 병합, limit 파라미터 기본값 20)
      - `POST /seats/{seat_id}/reserve` → 예약 (AVAILABLE 확인 → RESERVED 변경, 학생 정보 저장, 이벤트 로그 기록. 1인 1좌석 검증 없음)
      - `POST /seats/{seat_id}/cancel` → 취소 (student_id 일치 확인 → AVAILABLE 변경, 학생 정보 제거, absence_count/warning_count 초기화, 이벤트 로그 기록)
      - `POST /snapshot` → 스냅샷 분석 + 상태 전이 + Slack 알림 (전부 이 안에서 처리)
    - **스냅샷 분석 로직** (POST /snapshot 내부):
      - base64 이미지 디코딩 (data URI prefix 제거)
      - Bedrock Claude Haiku에 이미지 + 프롬프트 전송 (1회 호출로 3좌석 동시 분석)
      - Bedrock 응답 파싱 → 번호표(1,2,3) → 좌석 ID(A1,A2,A3) 매핑
      - 각 좌석에 대해 상태 전이 함수(`determine_transition`) 직접 호출 (boto3 invoke 불필요)
      - DynamoDB 업데이트 + 필요시 Slack 알림 + 이벤트 로그 저장
      - 개별 좌석 처리 실패 시 해당 좌석만 에러 표시, 나머지 정상 처리
      - Bedrock 호출 실패 시 에러 로그 기록, 500 응답 반환
    - **상태 전이 함수** (`determine_transition`을 같은 파일 내에 정의):
      - AVAILABLE 상태: 사람/짐 감지 시 NOTIFY_UNAUTHORIZED, 미감지 시 IGNORE
      - 예약 상태 + 사람 감지: OCCUPIED 전환, absence_count 0 초기화
      - 예약 상태 + 사람 미감지 + 임계값 미만: absence_count 증가, 짐 유무에 따라 ABSENT_WITH_STUFF/ABSENT_EMPTY
      - 임계값 도달 + 짐 없음: AUTO_RETURN (AVAILABLE 전환)
      - 임계값 도달 + 짐 있음 + warning_count=0: SEND_WARNING (WARNING_SENT 전환)
      - 임계값 도달 + 짐 있음 + warning_count≥1: AUTO_RETURN_WITH_ADMIN (AVAILABLE 전환)
    - **Slack 알림 함수** (`send_slack_notification`을 같은 파일 내에 정의):
      - urllib.request로 Slack Incoming Webhook POST 요청
      - 학생 경고(`⚠️`), 관리자 호출(`🚨`), 무단 점유(`👀`)
      - 실패 시 로그 기록, 좌석 상태 변경에 영향 없음
    - **에러 응답**: 409(이미 예약됨), 403(타인 취소), 404(좌석 없음), 500(Bedrock/DynamoDB 실패)
    - **환경변수**: `SEATS_TABLE`, `ABSENCE_THRESHOLD`, `SLACK_STUDENT_WEBHOOK`, `SLACK_ADMIN_WEBHOOK`
    - 모든 응답에 CORS 헤더 포함
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 5.1~5.4, 6.1~6.6, 7.1, 7.2, 8.1~8.4, 11.1, 11.2, 12.1~12.4_
  - **수동 체크포인트**: AWS 콘솔에서 Lambda 생성 후 테스트 이벤트로 각 라우트 확인 (GET /seats, POST reserve/cancel, POST /snapshot)

- [x] 2. 체크포인트 - 백엔드 수동 검증
  - AWS 콘솔에서 Lambda가 동작하는지 수동 확인
  - API Gateway에서 모든 라우트를 단일 Lambda에 연결 (프록시 통합)
  - Postman/curl로 전체 API 엔드포인트 테스트
  - DynamoDB에 초기 데이터(A1, A2, A3) 수동 입력 확인

- [x] 3. 프론트엔드 프로젝트 초기화
  - [x] 3.1 Vite + React (JavaScript) 프로젝트 생성
    - `frontend/` 디렉토리에 Vite + React 프로젝트 생성 (JavaScript, TypeScript 미사용)
    - `src/api.js`에 fetch 기반 API 호출 함수 구현 (getSeats, reserveSeat, cancelSeat, postSnapshot, getEvents)
    - `src/constants.js`에 API_BASE_URL(환경변수), 폴링 간격, 상태-색상 매핑 함수(`getStatusColor`) 정의
    - `src/utils.js`에 `getButtonType`, `shouldShowWarning` 함수 구현
    - 환경변수 설정 파일(`.env.example`) 생성: `VITE_API_BASE_URL`, `VITE_SNAPSHOT_INTERVAL`
    - react-router-dom 설치
    - _Requirements: 3.2, 9.3, 9.4, 10.3_

- [x] 4. Student_Page 구현
  - [x] 4.1 Student_Page 컴포넌트 구현
    - `src/pages/StudentPage.jsx` 구현
    - 학번 + 이름 입력 폼 (로그인 전 화면)
    - 로그인 후: 좌석 3개를 상태별 색상 카드로 표시
    - 각 좌석에 예약/취소 버튼 조건부 렌더링
    - 본인 좌석 warning_count > 0 시 상단 빨간 배너 표시
    - 5초 폴링으로 좌석 현황 자동 갱신 (useEffect + setInterval)
    - API 호출 실패 시 에러 메시지 표시
    - _Requirements: 9.1~9.5_
  - **수동 체크포인트**: 브라우저에서 로그인 → 예약 → 취소 플로우 확인

- [x] 5. Admin_Page 구현
  - [x] 5.1 Admin_Page 컴포넌트 구현
    - `src/pages/AdminPage.jsx` 구현
    - 좌석 대시보드: 3좌석 카드형 레이아웃 (seat_id, status, student_id/student_name, warning_count)
    - 상태별 색상 구분 적용
    - 카메라 영역: 시작/중지 버튼, getUserMedia로 실시간 미리보기
    - 카메라 시작 시 설정 간격(기본 5초)으로 자동 스냅샷 촬영 → canvas 캡처 → base64 → POST /snapshot
    - 최근 분석 결과 표시
    - 이벤트 로그 섹션: GET /events로 최근 이벤트 시간순 표시
    - 5초 폴링으로 좌석 현황 + 이벤트 로그 자동 갱신
    - 카메라 접근 거부/불가 시 에러 메시지 표시
    - _Requirements: 10.1~10.7, 4.1~4.3_
  - **수동 체크포인트**: 브라우저에서 카메라 시작 → 스냅샷 전송 → 대시보드 갱신 확인

- [x] 6. 라우팅 및 앱 통합
  - [x] 6.1 React Router 설정
    - `src/App.jsx`에 React Router 설정: `/` → StudentPage, `/admin` → AdminPage
    - `src/main.jsx` 엔트리포인트 설정
    - _Requirements: 9.1, 10.1_

- [ ] 7. 최종 체크포인트 - 전체 시스템 수동 검증
  - 프론트엔드 → API Gateway → Lambda → DynamoDB 전체 플로우 수동 테스트
  - Student_Page: 로그인 → 예약 → 좌석 상태 확인 → 취소
  - Admin_Page: 카메라 시작 → 스냅샷 분석 → 대시보드 갱신 → 이벤트 로그 확인
  - 부재 감지 → 경고 → 자동 반납 시나리오 수동 확인

## 참고사항

- Lambda 1개, 단일 파일(`lambda_function.py`)로 모든 백엔드 로직 포함 — AWS 콘솔 인라인 에디터에 바로 붙여넣기 가능
- Lambda 간 boto3 invoke 호출 불필요 — POST /snapshot 내부에서 상태 전이 함수를 직접 호출
- API Gateway에서 Lambda 프록시 통합 1개만 설정하면 됨
- shared 모듈 미사용 — 모든 코드를 단일 파일에 직접 포함
- 자동 테스트 없음 — 모든 검증은 수동으로 진행 (AWS 콘솔 테스트 이벤트, Postman, 브라우저)
- 1인 1좌석 검증 없음 — 단순 예약만 구현
- 인프라(DynamoDB 테이블, API Gateway, Lambda 생성)는 AWS 콘솔에서 수동으로 설정
