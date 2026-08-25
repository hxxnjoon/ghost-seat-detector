import json
import os
import boto3
from datetime import datetime, timezone
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
seats_table = dynamodb.Table(os.environ['SEATS_TABLE'])
notifications_table = dynamodb.Table(os.environ['NOTIFICATIONS_TABLE'])

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
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': ''}

    try:
        path = event.get('path', '')
        method = event.get('httpMethod', '')
        body = json.loads(event.get('body', '{}'))

        action = body.get('action', 'reserve')

        if action == 'reserve':
            return handle_reserve(body)
        elif action == 'cancel':
            return handle_cancel(body)
        else:
            return response(400, {'error': 'Invalid request'})

    except Exception as e:
        return response(500, {'error': str(e)})

def handle_reserve(body):
    seat_id = body.get('seat_id')
    student_id = body.get('student_id')
    student_name = body.get('student_name')

    if not all([seat_id, student_id, student_name]):
        return response(400, {'error': 'seat_id, student_id, student_name 필수'})

    # 현재 좌석 상태 확인
    seat = seats_table.get_item(Key={'seat_id': seat_id}).get('Item')
    if not seat:
        return response(404, {'error': '좌석 없음'})
    if seat['status'] != 'AVAILABLE':
        return response(409, {'error': '이미 예약된 좌석'})

    # 예약 처리
    now = datetime.now(timezone.utc).isoformat()
    seats_table.update_item(
        Key={'seat_id': seat_id},
        UpdateExpression='SET #s = :status, student_id = :sid, student_name = :sname, updated_at = :now',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':status': 'RESERVED',
            ':sid': student_id,
            ':sname': student_name,
            ':now': now
        }
    )

    return response(200, {'message': f'{seat_id} 예약 완료', 'seat_id': seat_id})

def handle_cancel(body):
    seat_id = body.get('seat_id')
    student_id = body.get('student_id')

    if not all([seat_id, student_id]):
        return response(400, {'error': 'seat_id, student_id 필수'})

    seat = seats_table.get_item(Key={'seat_id': seat_id}).get('Item')
    if not seat:
        return response(404, {'error': '좌석 없음'})
    if seat.get('student_id') != student_id:
        return response(403, {'error': '본인 예약만 취소 가능'})

    # 취소 처리 - 모든 값 초기화
    now = datetime.now(timezone.utc).isoformat()
    seats_table.update_item(
        Key={'seat_id': seat_id},
        UpdateExpression='SET #s = :status, student_id = :empty, student_name = :empty, absence_count = :zero, warning_count = :zero, has_stuff = :false, updated_at = :now',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':status': 'AVAILABLE',
            ':empty': '',
            ':zero': 0,
            ':false': False,
            ':now': now
        }
    )

    return response(200, {'message': f'{seat_id} 취소 완료'})

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, cls=DecimalEncoder)
    }