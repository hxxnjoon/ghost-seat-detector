---
inclusion: fileMatch
fileMatchPattern: "**/*test*"
---

# 테스트 가이드

## 테스트 전략: 이중 접근법
- 단위 테스트: 특정 예시, 엣지 케이스, 에러 조건 검증
- 속성 기반 테스트 (PBT): 모든 입력에 대한 보편적 속성 검증

## 백엔드 (Python)
- 프레임워크: pytest
- PBT 라이브러리: hypothesis
- 테스트 위치: `backend/tests/`
- 실행: `cd backend && python -m pytest tests/ -v`

### Hypothesis 패턴
```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(student_id=st.text(min_size=1, max_size=20))
def test_property_name(student_id):
    # 속성 검증 로직
    pass
```

## 프론트엔드 (TypeScript)
- 프레임워크: vitest
- PBT 라이브러리: fast-check
- 테스트 위치: `frontend/src/__tests__/`
- 실행: `cd frontend && npx vitest --run`

### fast-check 패턴
```typescript
import fc from 'fast-check';

test('property name', () => {
  fc.assert(
    fc.property(fc.string(), (input) => {
      // 속성 검증 로직
    }),
    { numRuns: 100 }
  );
});
```

## 태그 규칙
- 모든 PBT에 태그 포함: `Feature: ghost-seat-detector, Property {N}: {설명}`
- 설계 문서의 17개 정확성 속성과 1:1 매핑

## 모킹 전략
- DynamoDB: moto 라이브러리 또는 직접 mock
- Bedrock: boto3 mock (botocore.stub.Stubber)
- Slack: requests mock
- Lambda invoke: boto3 mock
