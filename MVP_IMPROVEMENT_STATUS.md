# MVP 개선 현황 (vNext)

## 목표
- 시험 예측 중심 리포트에서
  "강의 근거 기반 교재 문제 추천 큐"로 전환

## 완료 항목
- [x] Phase 2 신호 타입 개편
  - `hint | priority | trap | repeat`
- [x] Phase 4 출력 스키마 전환
  - `professor_mentioned/likely/trap_warnings` -> `recommendation_queue`
- [x] Phase 4 서버 검증/정렬 로직 개편
  - proof/reference 무결성 검증
  - dedup + importance 정렬
  - queue size 제한(`PHASE4_MAX_QUEUE_ITEMS`)
- [x] 프론트 리포트 UI 개편
  - 추천 문제 큐 카드
  - 근거 타임스탬프 패널
  - 교재 좌표 패널
- [x] 대시보드 요약 지표 변경
  - 추천 개수/근거 개수/경고 개수

## 운영 가드레일
- [x] 원문 직접 인용 보호(Verbatim guard)
- [x] 근거 부족 시 경고 출력
- [x] 단일 파일 업로드 시 불충분 안내 유지

## 남은 작업
- [ ] 근거 구간 클릭 시 오디오 플레이어 타임점프
- [ ] 추천 큐 완료 체크(학습 실행 추적)
- [ ] 멀티에이전트 검증 단계(Advocate/Skeptic/Judge)

## 성능/비용 방향
- Map 단계는 경량 모델 + 검색 중심 유지
- Reduce 단계만 고지능 추론 사용
- 기존 저비용 구조 유지(대규모 구조 변경 없음)
