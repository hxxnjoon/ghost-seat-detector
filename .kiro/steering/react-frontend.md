---
inclusion: fileMatch
fileMatchPattern: "**/*.{tsx,ts}"
---

# React 프론트엔드 코딩 가이드

## 기술 스택
- React 18 + TypeScript + Vite
- 상태 관리: React hooks (useState, useEffect, useCallback)
- 스타일링: CSS Modules 또는 인라인 스타일 (외부 UI 라이브러리 미사용)
- 배포: Amplify Hosting

## 프로젝트 구조
- 페이지: `frontend/src/pages/` (StudentPage.tsx, AdminPage.tsx)
- API 호출: `frontend/src/api.ts`
- 타입 정의: `frontend/src/types.ts`
- 상수: `frontend/src/constants.ts`
- 유틸리티: `frontend/src/utils.ts`

## 코딩 규칙
- 함수형 컴포넌트만 사용 (class 컴포넌트 금지)
- 주석은 한국어로 작성
- API Base URL은 환경변수 `VITE_API_BASE_URL`에서 로드
- 폴링 간격: 5초 (constants.ts에서 관리)
- 스냅샷 간격: 환경변수 `VITE_SNAPSHOT_INTERVAL` (기본 5초, 데모용)

## 상태별 색상 매핑
- AVAILABLE: 초록 (#4CAF50)
- RESERVED: 노랑 (#FFC107)
- OCCUPIED: 파랑 (#2196F3)
- ABSENT_WITH_STUFF / ABSENT_EMPTY / WARNING_SENT: 주황 (#FF9800)
- AUTO_RETURNED: 빨강 (#F44336)

## API 호출 패턴
- fetch API 사용 (axios 미사용)
- 에러 시 사용자에게 메시지 표시, 다음 폴링에서 재시도
- base64 이미지 전송 시 data URI prefix 포함

## 테스트
- vitest + fast-check 사용
- 테스트 파일: `frontend/src/__tests__/` 디렉토리
- 속성 기반 테스트: `fc.assert(fc.property(...))`, 최소 100회 반복
- 태그 형식: `Feature: ghost-seat-detector, Property {N}: {설명}`

## 접근성
- 시맨틱 HTML 태그 사용 (button, nav, main, section)
- 색상만으로 정보 전달하지 않기 (텍스트 라벨 병행)
- aria-label, aria-live 적절히 사용
