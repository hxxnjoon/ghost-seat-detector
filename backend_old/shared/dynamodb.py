"""
DynamoDB 클라이언트 초기화 및 공통 헬퍼 함수.

Single Table Design (PK/SK 패턴):
- 좌석 메타데이터: PK=SEAT#{seat_id}, SK=METADATA
- 이벤트 로그: PK=EVENT#{seat_id}, SK=ISO 8601 타임스탬프
"""

import boto3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from shared.constants import SEATS_TABLE, SEAT_IDS

# DynamoDB 클라이언트 초기화
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(SEATS_TABLE)


def get_seat(seat_id: str) -> dict | None:
    """개별 좌석 메타데이터 조회.

    Args:
        seat_id: 좌석 ID (예: "A1")

    Returns:
        좌석 데이터 dict 또는 None (존재하지 않는 경우)
    """
    response = table.get_item(
        Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"}
    )
    return response.get("Item")


def batch_get_seats() -> list[dict]:
    """전체 좌석(A1~A3) 메타데이터 일괄 조회 (BatchGetItem).

    Returns:
        좌석 데이터 dict 리스트 (seat_id 기준 정렬)
    """
    keys = [{"PK": f"SEAT#{sid}", "SK": "METADATA"} for sid in SEAT_IDS]
    response = dynamodb.batch_get_item(
        RequestItems={
            SEATS_TABLE: {"Keys": keys}
        }
    )
    items = response.get("Responses", {}).get(SEATS_TABLE, [])
    # seat_id 기준 정렬하여 일관된 순서 보장
    items.sort(key=lambda x: x.get("seat_id", ""))
    return items


def update_seat(seat_id: str, updates: dict) -> dict:
    """좌석 메타데이터 업데이트 (UpdateItem).

    Args:
        seat_id: 좌석 ID (예: "A1")
        updates: 업데이트할 필드 dict (예: {"status": "RESERVED", "student_id": "20241234"})

    Returns:
        업데이트된 좌석 데이터 dict
    """
    # updated_at 자동 추가
    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now

    # UpdateExpression 동적 생성
    update_parts = []
    expr_names = {}
    expr_values = {}

    for i, (key, value) in enumerate(updates.items()):
        alias = f"#k{i}"
        val_alias = f":v{i}"
        update_parts.append(f"{alias} = {val_alias}")
        expr_names[alias] = key
        # DynamoDB는 float을 지원하지 않으므로 Decimal 변환
        if isinstance(value, float):
            value = Decimal(str(value))
        elif isinstance(value, int):
            value = Decimal(str(value))
        expr_values[val_alias] = value

    update_expression = "SET " + ", ".join(update_parts)

    response = table.update_item(
        Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )
    return response.get("Attributes", {})


def put_event(seat_id: str, event_type: str, event_detail: str) -> None:
    """이벤트 로그 저장.

    PK=EVENT#{seat_id}, SK=ISO 8601 타임스탬프.
    TTL은 24시간 후로 설정.

    Args:
        seat_id: 좌석 ID (예: "A1")
        event_type: 이벤트 타입 (예: "WARNING_SENT")
        event_detail: 이벤트 상세 내용 (예: "경고 1회 발송")
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    ttl = int((now + timedelta(hours=24)).timestamp())

    table.put_item(
        Item={
            "PK": f"EVENT#{seat_id}",
            "SK": timestamp,
            "seat_id": seat_id,
            "event_type": event_type,
            "event_detail": event_detail,
            "ttl": ttl,
        }
    )
