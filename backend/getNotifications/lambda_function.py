import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['NOTIFICATIONS_TABLE'])

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
        # 쿼리 파라미터에서 student_id 가져오기
        params = event.get('queryStringParameters') or {}
        student_id = params.get('student_id')

        if not student_id:
            return response(400, {'error': 'student_id 필수'})

        # 해당 학생의 알림을 최신순으로 조회
        result = table.query(
            KeyConditionExpression=Key('student_id').eq(student_id),
            ScanIndexForward=False,  # 최신순 (내림차순)
            Limit=20
        )

        return response(200, {'notifications': result.get('Items', [])})

    except Exception as e:
        return response(500, {'error': str(e)})

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, cls=DecimalEncoder) if isinstance(body, dict) else body
    }