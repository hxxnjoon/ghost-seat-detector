import json
import os
import boto3
from decimal import Decimal

# DynamoDB 연결
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['SEATS_TABLE'])

# 좌석 ID 목록
SEAT_IDS = ['A1', 'A2', 'A3']

# CORS 헤더 (프론트엔드에서 호출할 수 있게 허용)
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

# Decimal을 JSON으로 변환하기 위한 헬퍼
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    # OPTIONS 요청 처리 (브라우저가 CORS 확인할 때 보내는 사전 요청)
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': ''}

    try:
        # 좌석 3개를 하나씩 가져오기
        seats = []
        for seat_id in SEAT_IDS:
            response = table.get_item(Key={'seat_id': seat_id})
            if 'Item' in response:
                seats.append(response['Item'])

        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps(seats, cls=DecimalEncoder)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }
