"""
ghostSeatDetector — 도서관 좌석 유령 예약 감지 시스템 통합 Lambda

모든 백엔드 로직을 단일 파일에 포함한다.
AWS 콘솔 인라인 에디터에 바로 붙여넣어 사용할 수 있다.
"""

import json
import os
import logging
import base64
import re
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.config import Config

# ---------------------------------------------------------------------------
# 로깅
# ---------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# 환경변수
# ---------------------------------------------------------------------------
SEATS_TABLE: str = os.environ.get("SEATS_TABLE", "ghost-seat-detector-seats")
ABSENCE_THRESHOLD: int = int(os.environ.get("ABSENCE_THRESHOLD", "5"))
SLACK_STUDENT_WEBHOOK: str = os.environ.get("SLACK_STUDENT_WEBHOOK", "")
SLACK_ADMIN_WEBHOOK: str = os.environ.get("SLACK_ADMIN_WEBHOOK", "")

# ---------------------------------------------------------------------------
# AWS 클라이언트
# ---------------------------------------------------------------------------
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(SEATS_TABLE)

bedrock_config = Config(read_timeout=30, connect_timeout=5, retries={"max_attempts": 1})
bedrock_runtime = boto3.client("bedrock-runtime", config=bedrock_config)

BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
SEAT_IDS: list[str] = ["A1", "A2", "A3"]
LABEL_TO_SEAT: dict[str, str] = {"1": "A1", "2": "A2", "3": "A3"}

CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

EVENT_TTL_SECONDS: int = 60 * 60 * 24 * 7  # 7일


# ===================================================================
# 헬퍼: 응답 빌더
# ===================================================================

class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimal → int/float 변환용 JSON 인코더."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _response(status_code: int, body: Any) -> dict:
    """CORS 헤더가 포함된 API Gateway 응답을 생성한다."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalEncoder, ensure_ascii=False),
    }


def _now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()


# ===================================================================
# 이벤트 로그 저장
# ===================================================================

def _save_event(seat_id: str, event_type: str, event_detail: str) -> None:
    """DynamoDB에 이벤트 로그를 기록한다."""
    now = _now_iso()
    ttl = int(datetime.now(timezone.utc).timestamp()) + EVENT_TTL_SECONDS
    try:
        table.put_item(Item={
            "PK": f"EVENT#{seat_id}",
            "SK": now,
            "seat_id": seat_id,
            "event_type": event_type,
            "event_detail": event_detail,
            "updated_at": now,
            "ttl": ttl,
        })
    except Exception:
        logger.exception("이벤트 로그 저장 실패: seat_id=%s", seat_id)


# ===================================================================
# Slack 알림
# ===================================================================

def send_slack_notification(webhook_url: str, message: str) -> None:
    """Slack Incoming Webhook으로 메시지를 전송한다. 실패 시 로그만 기록한다."""
    if not webhook_url:
        logger.warning("Slack webhook URL이 설정되지 않음 — 알림 건너뜀")
        return
    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("Slack 알림 전송 성공: %s", resp.status)
    except Exception:
        logger.exception("Slack 알림 전송 실패")


# ===================================================================
# 상태 전이 함수
# ===================================================================

def determine_transition(
    current_status: str,
    person_detected: bool,
    stuff_detected: bool,
    absence_count: int,
    warning_count: int,
    threshold: int,
) -> dict:
    """현재 좌석 상태와 감지 결과를 기반으로 다음 상태 전이를 결정한다."""
    # AVAILABLE 상태
    if current_status == "AVAILABLE":
        if person_detected or stuff_detected:
            return {"action": "NOTIFY_UNAUTHORIZED", "new_status": "AVAILABLE"}
        return {"action": "IGNORE", "new_status": "AVAILABLE"}

    # 예약 상태(RESERVED, OCCUPIED, ABSENT_*, WARNING_SENT) + 사람 감지
    if person_detected:
        return {"action": "SET_OCCUPIED", "new_status": "OCCUPIED", "absence_count": 0}

    # 사람 미감지 → absence_count 증가
    new_absence = absence_count + 1

    if new_absence < threshold:
        new_status = "ABSENT_WITH_STUFF" if stuff_detected else "ABSENT_EMPTY"
        return {
            "action": "INCREMENT_ABSENCE",
            "new_status": new_status,
            "absence_count": new_absence,
        }

    # 임계값 도달
    if not stuff_detected:
        return {"action": "AUTO_RETURN", "new_status": "AVAILABLE"}

    # 짐 있음 + 임계값 도달
    if warning_count == 0:
        return {
            "action": "SEND_WARNING",
            "new_status": "WARNING_SENT",
            "warning_count": 1,
            "absence_count": 0,
        }
    else:
        return {"action": "AUTO_RETURN_WITH_ADMIN", "new_status": "AVAILABLE"}


# ===================================================================
# GET /seats — 전체 좌석 조회 (BatchGetItem)
# ===================================================================

def handle_get_seats() -> dict:
    """3개 좌석의 현재 상태를 일괄 조회한다."""
    try:
        keys = [{"PK": f"SEAT#{sid}", "SK": "METADATA"} for sid in SEAT_IDS]
        resp = dynamodb.batch_get_item(RequestItems={SEATS_TABLE: {"Keys": keys}})
        items = resp.get("Responses", {}).get(SEATS_TABLE, [])
        seats = []
        for item in items:
            seats.append({
                "seat_id": item.get("seat_id"),
                "seat_label": item.get("seat_label"),
                "status": item.get("status"),
                "student_id": item.get("student_id", ""),
                "student_name": item.get("student_name", ""),
                "absence_count": item.get("absence_count", 0),
                "warning_count": item.get("warning_count", 0),
                "has_stuff": item.get("has_stuff", False),
                "updated_at": item.get("updated_at", ""),
            })
        seats.sort(key=lambda s: s["seat_id"])
        return _response(200, seats)
    except Exception:
        logger.exception("전체 좌석 조회 실패")
        return _response(500, {"error": "좌석 조회에 실패했습니다."})


# ===================================================================
# GET /seats/{seat_id} — 개별 좌석 조회 (GetItem)
# ===================================================================

def handle_get_seat(seat_id: str) -> dict:
    """단일 좌석의 현재 상태를 조회한다."""
    if seat_id not in SEAT_IDS:
        return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})
    try:
        resp = table.get_item(Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})
        seat = {
            "seat_id": item.get("seat_id"),
            "seat_label": item.get("seat_label"),
            "status": item.get("status"),
            "student_id": item.get("student_id", ""),
            "student_name": item.get("student_name", ""),
            "absence_count": item.get("absence_count", 0),
            "warning_count": item.get("warning_count", 0),
            "has_stuff": item.get("has_stuff", False),
            "updated_at": item.get("updated_at", ""),
        }
        return _response(200, seat)
    except Exception:
        logger.exception("좌석 조회 실패: seat_id=%s", seat_id)
        return _response(500, {"error": "좌석 조회에 실패했습니다."})


# ===================================================================
# GET /events — 이벤트 로그 조회 (Query × 3, 시간순 병합)
# ===================================================================

def handle_get_events(limit: int = 20) -> dict:
    """3개 좌석의 이벤트 로그를 시간 역순으로 병합하여 반환한다."""
    try:
        all_events: list[dict] = []
        for sid in SEAT_IDS:
            resp = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"EVENT#{sid}"),
                ScanIndexForward=False,
                Limit=limit,
            )
            for item in resp.get("Items", []):
                all_events.append({
                    "seat_id": item.get("seat_id"),
                    "event_type": item.get("event_type"),
                    "event_detail": item.get("event_detail"),
                    "updated_at": item.get("updated_at", item.get("SK", "")),
                })
        # 시간 역순 정렬 후 limit 적용
        all_events.sort(key=lambda e: e["updated_at"], reverse=True)
        return _response(200, all_events[:limit])
    except Exception:
        logger.exception("이벤트 로그 조회 실패")
        return _response(500, {"error": "이벤트 로그 조회에 실패했습니다."})


# ===================================================================
# POST /seats/{seat_id}/reserve — 좌석 예약
# ===================================================================

def handle_reserve(seat_id: str, body: dict) -> dict:
    """AVAILABLE 좌석을 RESERVED로 변경하고 학생 정보를 저장한다."""
    if seat_id not in SEAT_IDS:
        return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})

    student_id = body.get("student_id", "").strip()
    student_name = body.get("student_name", "").strip()
    if not student_id or not student_name:
        return _response(400, {"error": "student_id와 student_name은 필수입니다."})

    try:
        resp = table.get_item(Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})

        if item.get("status") != "AVAILABLE":
            return _response(409, {"error": f"좌석 {seat_id}은(는) 이미 예약되어 있습니다."})

        now = _now_iso()
        table.update_item(
            Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"},
            UpdateExpression=(
                "SET #st = :status, student_id = :sid, student_name = :sname, "
                "absence_count = :zero, warning_count = :zero, has_stuff = :false_val, "
                "updated_at = :now"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "RESERVED",
                ":sid": student_id,
                ":sname": student_name,
                ":zero": 0,
                ":false_val": False,
                ":now": now,
            },
        )
        _save_event(seat_id, "RESERVE", f"{student_name}({student_id})이(가) 예약")
        return _response(200, {"message": f"좌석 {seat_id} 예약 완료", "seat_id": seat_id, "status": "RESERVED"})
    except Exception:
        logger.exception("예약 처리 실패: seat_id=%s", seat_id)
        return _response(500, {"error": "예약 처리에 실패했습니다."})


# ===================================================================
# POST /seats/{seat_id}/cancel — 좌석 취소
# ===================================================================

def handle_cancel(seat_id: str, body: dict) -> dict:
    """본인 좌석을 취소하여 AVAILABLE로 변경한다."""
    if seat_id not in SEAT_IDS:
        return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})

    student_id = body.get("student_id", "").strip()
    if not student_id:
        return _response(400, {"error": "student_id는 필수입니다."})

    try:
        resp = table.get_item(Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": f"좌석 {seat_id}을(를) 찾을 수 없습니다."})

        if item.get("status") == "AVAILABLE":
            return _response(409, {"error": f"좌석 {seat_id}은(는) 예약되어 있지 않습니다."})

        if item.get("student_id") != student_id:
            return _response(403, {"error": "본인의 좌석만 취소할 수 있습니다."})

        now = _now_iso()
        table.update_item(
            Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"},
            UpdateExpression=(
                "SET #st = :status, student_id = :empty, student_name = :empty, "
                "absence_count = :zero, warning_count = :zero, has_stuff = :false_val, "
                "updated_at = :now"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "AVAILABLE",
                ":empty": "",
                ":zero": 0,
                ":false_val": False,
                ":now": now,
            },
        )
        _save_event(seat_id, "CANCEL", f"{student_id}이(가) 취소")
        return _response(200, {"message": f"좌석 {seat_id} 취소 완료", "seat_id": seat_id, "status": "AVAILABLE"})
    except Exception:
        logger.exception("취소 처리 실패: seat_id=%s", seat_id)
        return _response(500, {"error": "취소 처리에 실패했습니다."})


# ===================================================================
# POST /snapshot — 스냅샷 분석 + 상태 전이 + Slack 알림
# ===================================================================

BEDROCK_PROMPT: str = """이 이미지에는 번호표(1, 2, 3)가 부착된 도서관 좌석 3개가 있습니다.
각 좌석에 대해 다음을 분석해주세요:
1. person_present: 해당 좌석에 앉아있는 사람이 있는지 (true/false). 통행인이나 서있는 사람은 false입니다.
2. stuff_present: 좌석 위나 주변에 짐(가방, 책, 노트북 등)이 있는지 (true/false)

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
{"1": {"person_present": true/false, "stuff_present": true/false}, "2": {"person_present": true/false, "stuff_present": true/false}, "3": {"person_present": true/false, "stuff_present": true/false}}"""


def _decode_base64_image(image_base64: str) -> tuple[bytes, str]:
    """base64 이미지를 디코딩하고 미디어 타입을 반환한다."""
    media_type = "image/jpeg"
    raw = image_base64
    if "," in raw:
        header, raw = raw.split(",", 1)
        match = re.search(r"data:(image/\w+)", header)
        if match:
            media_type = match.group(1)
    return base64.b64decode(raw), media_type


def _call_bedrock(image_bytes: bytes, media_type: str) -> dict:
    """Bedrock Claude Haiku에 이미지를 전송하고 3좌석 분석 결과를 반환한다."""
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode("utf-8"),
                        },
                    },
                    {"type": "text", "text": BEDROCK_PROMPT},
                ],
            }
        ],
    }
    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(request_body),
    )
    response_body = json.loads(response["body"].read())
    text = response_body["content"][0]["text"]
    # JSON 부분만 추출 (앞뒤 텍스트 제거)
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        raise ValueError(f"Bedrock 응답에서 JSON을 찾을 수 없음: {text[:200]}")
    return json.loads(json_match.group())


def _apply_transition(seat_id: str, analysis: dict) -> dict:
    """단일 좌석에 대해 상태 전이를 적용하고 DynamoDB를 업데이트한다."""
    person_detected = analysis.get("person_present", False)
    stuff_detected = analysis.get("stuff_present", False)

    # 현재 좌석 상태 조회
    resp = table.get_item(Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"})
    item = resp.get("Item")
    if not item:
        logger.error("좌석 데이터 없음: %s", seat_id)
        return {"error": f"좌석 {seat_id} 데이터 없음"}

    current_status = item.get("status", "AVAILABLE")
    absence_count = int(item.get("absence_count", 0))
    warning_count = int(item.get("warning_count", 0))

    transition = determine_transition(
        current_status=current_status,
        person_detected=person_detected,
        stuff_detected=stuff_detected,
        absence_count=absence_count,
        warning_count=warning_count,
        threshold=ABSENCE_THRESHOLD,
    )

    action = transition["action"]
    new_status = transition["new_status"]
    new_absence = transition.get("absence_count", absence_count)
    new_warning = transition.get("warning_count", warning_count)

    # IGNORE인 경우 업데이트 불필요
    if action == "IGNORE":
        return {
            "person_detected": person_detected,
            "stuff_detected": stuff_detected,
            "status": current_status,
            "absence_count": absence_count,
            "warning_count": warning_count,
            "action": action,
        }

    now = _now_iso()

    # DynamoDB 업데이트
    table.update_item(
        Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"},
        UpdateExpression=(
            "SET #st = :status, absence_count = :ac, warning_count = :wc, "
            "has_stuff = :stuff, updated_at = :now"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":status": new_status,
            ":ac": new_absence,
            ":wc": new_warning,
            ":stuff": stuff_detected,
            ":now": now,
        },
    )

    # AUTO_RETURN / AUTO_RETURN_WITH_ADMIN 시 학생 정보 제거
    if action in ("AUTO_RETURN", "AUTO_RETURN_WITH_ADMIN"):
        table.update_item(
            Key={"PK": f"SEAT#{seat_id}", "SK": "METADATA"},
            UpdateExpression="SET student_id = :empty, student_name = :empty",
            ExpressionAttributeValues={":empty": ""},
        )

    # Slack 알림
    if action == "SEND_WARNING":
        send_slack_notification(
            SLACK_STUDENT_WEBHOOK,
            f"⚠️ 좌석 {seat_id}에서 장시간 이탈이 감지되었습니다. 복귀해주세요.",
        )
    elif action == "AUTO_RETURN_WITH_ADMIN":
        send_slack_notification(
            SLACK_ADMIN_WEBHOOK,
            f"🚨 좌석 {seat_id} 경고 2회 누적. 자동 반납 처리됨.",
        )
    elif action == "NOTIFY_UNAUTHORIZED":
        send_slack_notification(
            SLACK_ADMIN_WEBHOOK,
            f"👀 좌석 {seat_id}(미예약)에서 사람/짐이 감지되었습니다.",
        )

    # 이벤트 로그
    _save_event(seat_id, action, f"person={person_detected}, stuff={stuff_detected}, {current_status}→{new_status}")

    return {
        "person_detected": person_detected,
        "stuff_detected": stuff_detected,
        "status": new_status,
        "absence_count": new_absence,
        "warning_count": new_warning,
        "action": action,
    }


def handle_snapshot(body: dict) -> dict:
    """스냅샷 이미지를 분석하고 3좌석의 상태를 전이한다."""
    image_base64 = body.get("image_base64", "")
    if not image_base64:
        return _response(400, {"error": "image_base64는 필수입니다."})

    # 1. 이미지 디코딩
    try:
        image_bytes, media_type = _decode_base64_image(image_base64)
    except Exception:
        logger.exception("이미지 디코딩 실패")
        return _response(400, {"error": "이미지 디코딩에 실패했습니다."})

    # 2. Bedrock 호출
    try:
        bedrock_result = _call_bedrock(image_bytes, media_type)
        logger.info("Bedrock 분석 결과: %s", bedrock_result)
    except Exception:
        logger.exception("Bedrock 호출 실패")
        return _response(500, {"error": "AI 분석에 실패했습니다."})

    # 3. 각 좌석에 대해 상태 전이 적용
    results: dict[str, Any] = {}
    for label, seat_id in LABEL_TO_SEAT.items():
        if label not in bedrock_result:
            logger.warning("Bedrock 응답에 번호표 %s 누락 — 좌석 %s 건너뜀", label, seat_id)
            results[seat_id] = {"error": f"번호표 {label} 분석 결과 누락"}
            continue
        try:
            seat_result = _apply_transition(seat_id, bedrock_result[label])
            results[seat_id] = seat_result
        except Exception:
            logger.exception("좌석 %s 상태 전이 실패", seat_id)
            results[seat_id] = {"error": f"좌석 {seat_id} 처리 실패"}

    return _response(200, results)


# ===================================================================
# Lambda 핸들러 (라우팅)
# ===================================================================

def lambda_handler(event: dict, context: Any) -> dict:
    """API Gateway 프록시 통합 핸들러. HTTP method + path로 라우팅한다."""
    logger.info("요청: %s %s", event.get("httpMethod"), event.get("path"))

    method: str = event.get("httpMethod", "")
    path: str = event.get("path", "")

    # OPTIONS — CORS preflight
    if method == "OPTIONS":
        return _response(200, {"message": "CORS preflight"})

    # Body 파싱
    body: dict = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            return _response(400, {"error": "잘못된 요청 본문입니다."})

    # Query parameters
    params = event.get("queryStringParameters") or {}

    try:
        # GET /seats
        if method == "GET" and path == "/seats":
            return handle_get_seats()

        # GET /seats/{seat_id}
        if method == "GET" and re.match(r"^/seats/[A-Za-z0-9]+$", path):
            seat_id = path.split("/")[-1].upper()
            return handle_get_seat(seat_id)

        # GET /events
        if method == "GET" and path == "/events":
            limit = int(params.get("limit", "20"))
            return handle_get_events(limit)

        # POST /seats/{seat_id}/reserve
        if method == "POST" and path.endswith("/reserve"):
            parts = path.split("/")
            seat_id = parts[-2].upper() if len(parts) >= 3 else ""
            return handle_reserve(seat_id, body)

        # POST /seats/{seat_id}/cancel
        if method == "POST" and path.endswith("/cancel"):
            parts = path.split("/")
            seat_id = parts[-2].upper() if len(parts) >= 3 else ""
            return handle_cancel(seat_id, body)

        # POST /snapshot
        if method == "POST" and path == "/snapshot":
            return handle_snapshot(body)

        # 매칭되지 않는 경로
        return _response(404, {"error": f"경로를 찾을 수 없습니다: {method} {path}"})

    except Exception:
        logger.exception("처리되지 않은 오류: %s %s", method, path)
        return _response(500, {"error": "내부 서버 오류가 발생했습니다."})
