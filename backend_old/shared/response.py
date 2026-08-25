"""
API Gateway 응답 헬퍼 함수.

모든 응답에 CORS 헤더를 포함한다:
- Access-Control-Allow-Origin: *
- Access-Control-Allow-Methods: GET, POST, OPTIONS
- Access-Control-Allow-Headers: Content-Type
"""

import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimal 타입을 JSON 직렬화하기 위한 인코더."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def success_response(body: dict | list, status_code: int = 200) -> dict:
    """성공 응답 생성.

    Args:
        body: 응답 본문 (dict 또는 list)
        status_code: HTTP 상태 코드 (기본값 200)

    Returns:
        API Gateway 응답 형식 dict
    """
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalEncoder, ensure_ascii=False),
    }


def error_response(message: str, status_code: int) -> dict:
    """에러 응답 생성.

    Args:
        message: 에러 메시지
        status_code: HTTP 상태 코드 (400, 403, 404, 409, 500 등)

    Returns:
        API Gateway 응답 형식 dict
    """
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}, ensure_ascii=False),
    }
