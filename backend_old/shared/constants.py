"""
공통 상수 및 환경변수 로딩 모듈.

좌석 ID, 번호표→좌석 매핑, 상태 상수, DynamoDB 테이블명 등을 정의한다.
"""

import os

# 좌석 ID 목록
SEAT_IDS = ["A1", "A2", "A3"]

# 번호표 → 좌석 ID 매핑 (AI가 인식하는 번호표 → 시스템 좌석 ID)
LABEL_TO_SEAT = {"1": "A1", "2": "A2", "3": "A3"}

# 좌석 ID → 번호표 매핑 (역방향)
SEAT_TO_LABEL = {"A1": "1", "A2": "2", "A3": "3"}

# 좌석 상태 상수
AVAILABLE = "AVAILABLE"
RESERVED = "RESERVED"
OCCUPIED = "OCCUPIED"
ABSENT_WITH_STUFF = "ABSENT_WITH_STUFF"
ABSENT_EMPTY = "ABSENT_EMPTY"
WARNING_SENT = "WARNING_SENT"
AUTO_RETURNED = "AUTO_RETURNED"

# 예약된 상태 목록 (사람 감지/미감지 로직이 적용되는 상태들)
RESERVED_STATUSES = [RESERVED, OCCUPIED, ABSENT_WITH_STUFF, ABSENT_EMPTY, WARNING_SENT]

# DynamoDB 테이블명 (환경변수에서 로드)
SEATS_TABLE = os.environ.get("SEATS_TABLE", "ghost-seat-detector-seats")

# 부재 판단 임계값 (환경변수에서 로드, 기본값 7, 데모용 5)
ABSENCE_THRESHOLD = int(os.environ.get("ABSENCE_THRESHOLD", "7"))
