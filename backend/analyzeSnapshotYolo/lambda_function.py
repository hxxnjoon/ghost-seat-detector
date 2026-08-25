import json
import os
import boto3
import logging
from datetime import datetime, timezone
from decimal import Decimal

import onnxruntime as ort

import yolo_infer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
seats_table = dynamodb.Table(os.environ['SEATS_TABLE'])
notifications_table = dynamodb.Table(os.environ['NOTIFICATIONS_TABLE'])

# 콜드 스타트 시 1회 로드, 이후 웜 인보크에서 재사용
_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model', 'yolov8n.onnx')
_session = ort.InferenceSession(_MODEL_PATH, providers=['CPUExecutionProvider'])

ABSENCE_THRESHOLD = int(os.environ.get('ABSENCE_THRESHOLD', '5'))
SEAT_IDS = ['A1', 'A2', 'A3']

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return response(200, '')

    try:
        body = json.loads(event.get('body', '{}'))
        image_base64 = body.get('image')

        if not image_base64:
            return response(400, {'error': 'image 필수'})

        ai_result = analyze_image(image_base64)
        logger.info(f"AI 분석 결과: {ai_result}")

        results = []
        for label, seat_data in ai_result.items():
            seat_id = f"A{label}"
            if seat_id not in SEAT_IDS:
                continue

            seat = seats_table.get_item(Key={'seat_id': seat_id}).get('Item')
            if not seat:
                continue

            result = process_seat(seat, seat_data)
            results.append(result)

        return response(200, {'results': results})

    except Exception as e:
        logger.error(f"에러: {str(e)}")
        return response(500, {'error': str(e)})

def analyze_image(image_base64):
    """YOLOv8n(ONNX, CPU) 로컬 추론으로 좌석별 person/stuff 유무를 판단한다.

    Bedrock과 달리 의미론적 추론이 없으므로, 의자 탐지 기반(왼쪽→오른쪽) 좌석
    존 매핑 + 바운딩박스 겹침으로 판정한다. 자세한 알고리즘은 yolo_infer.py 참고.
    """
    return yolo_infer.analyze(_session, image_base64)

def process_seat(seat, ai_data):
    seat_id = seat['seat_id']
    current_status = seat['status']
    person = ai_data.get('person_present', False)
    stuff = ai_data.get('stuff_present', False)
    absence_count = int(seat.get('absence_count', 0))
    warning_count = int(seat.get('warning_count', 0))
    now = datetime.now(timezone.utc).isoformat()

    new_status = current_status
    action = 'NONE'
    notification_msg = None
    notification_target = None

    if current_status == 'AVAILABLE':
        if person or stuff:
            action = 'NOTIFY_UNAUTHORIZED'
            notification_msg = f'좌석 {seat_id}(미예약)에서 사람 또는 짐이 감지되었습니다.'
            notification_target = 'ADMIN'
        else:
            action = 'IGNORE'

    elif current_status in ('RESERVED', 'OCCUPIED', 'ABSENT_WITH_STUFF', 'ABSENT_EMPTY', 'WARNING_SENT'):
        if person:
            new_status = 'OCCUPIED'
            absence_count = 0
            action = 'OCCUPIED'
        else:
            absence_count += 1

            if absence_count < ABSENCE_THRESHOLD:
                new_status = 'ABSENT_WITH_STUFF' if stuff else 'ABSENT_EMPTY'
                action = 'COUNTING'
            else:
                if not stuff:
                    new_status = 'AVAILABLE'
                    absence_count = 0
                    warning_count = 0
                    action = 'AUTO_RETURNED'
                    notification_msg = f'좌석 {seat_id}이 자동 반납되었습니다.'
                    notification_target = seat.get('student_id')
                elif warning_count == 0:
                    new_status = 'WARNING_SENT'
                    warning_count = 1
                    absence_count = 0
                    action = 'SEND_WARNING'
                    notification_msg = f'⚠️ 좌석 {seat_id}에서 장시간 이탈이 감지되었습니다. 복귀해주세요.'
                    notification_target = seat.get('student_id')
                else:
                    new_status = 'AVAILABLE'
                    absence_count = 0
                    warning_count = 0
                    action = 'AUTO_RETURN_WITH_ADMIN'
                    notification_msg = f'🚨 좌석 {seat_id} 경고 2회 누적. 자동 반납 처리됨.'
                    notification_target = 'ADMIN'
                    send_notification(seat.get('student_id'), seat_id, 'AUTO_RETURNED',
                                     f'좌석 {seat_id}이 자동 반납되었습니다.')

    update_expr = 'SET #s = :status, absence_count = :ac, warning_count = :wc, has_stuff = :stuff, updated_at = :now'
    expr_values = {
        ':status': new_status,
        ':ac': absence_count,
        ':wc': warning_count,
        ':stuff': stuff,
        ':now': now
    }

    if new_status == 'AVAILABLE' and action in ('AUTO_RETURNED', 'AUTO_RETURN_WITH_ADMIN'):
        update_expr += ', student_id = :empty, student_name = :empty'
        expr_values[':empty'] = ''

    seats_table.update_item(
        Key={'seat_id': seat_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues=expr_values
    )

    if notification_msg and notification_target:
        send_notification(notification_target, seat_id, action, notification_msg)

    return {
        'seat_id': seat_id,
        'person': person,
        'stuff': stuff,
        'previous_status': current_status,
        'new_status': new_status,
        'action': action,
        'absence_count': absence_count
    }

def send_notification(target_id, seat_id, noti_type, message):
    if not target_id:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        notifications_table.put_item(Item={
            'student_id': target_id,
            'created_at': now,
            'type': noti_type,
            'message': message,
            'seat_id': seat_id
        })
    except Exception as e:
        logger.error(f"알림 저장 실패: {e}")

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, cls=DecimalEncoder) if isinstance(body, dict) else body
    }
