# Project Thunder vNext

강의 근거 기반 교재 문제 추천 엔진(MVP) 프로젝트입니다.  
현재 전략은 "시험문제 예측"이 아니라 "근거 기반 추천 큐"입니다.

## 현재 구현 상태 (2026-02-18 기준)

- Phase 1 완료: PDF OCR/구조화/chunk/embedding 파이프라인 운영 중
- Phase 2 완료: 오디오 신호 추출(Map) 운영 중
- Phase 3 완료: Hybrid Retrieval + RRF 기반 근거 후보 수집 운영 중
- Phase 4 완료: recommendation_queue 중심 Reduce 리포트 생성 운영 중
- 프론트 완료: 다중 파일 업로드 + 업로드 진행률 표시 + 통합 리포트 워크플로우

## 최근 안정화 반영

- PDF 업로드 경로를 GCS signed URL 기반 서버 파이프라인으로 복귀
- 다중 오디오 업로드 시 파일별 실패 격리 및 요약 결과 반환
- Phase 2
  - `audio_chunks(session_id, chunk_index)` 중복 충돌 대응(upsert)
  - 청크/모델 호출 재시도(backoff) 도입
  - 신호 저장 idempotent 처리
- Phase 1
  - 스캔 OCR 병렬도 상한 도입(메모리 폭주 방지)
  - 배치 단위 온디맨드 처리로 메모리 압력 완화
- Gemini API 전환
  - Phase 1 OCR: Vertex SDK 호출 대신 Gemini API 호출
  - Phase 2 STT/신호추출: Vertex SDK 호출 대신 Gemini API 호출
  - Gemini Batch API 기반 그룹 처리 + in-flight 동시 처리
  - 글로벌 endpoint 사용 (`GEMINI_LOCATION=global`)
  - 다중 프로젝트 API 키 샤딩 지원 (`GEMINI_API_KEY`, `GEMINI_API_KEY_SECONDARY`)
- Cloud Run Job 운영값 조정
  - `INGEST_BATCH_PAGES=10`
  - `PHASE1_SCANNED_MAX_WORKERS=8`
  - `PHASE1_OCR_TIMEOUT_SEC=50`

## 운영 환경 요약

- GCP Project: `pdf-lab-468815`
- Cloud Run Job: `thunder-worker` (`asia-northeast3`)
- Cloud Run Job Generation: `78`
- 모델: `gemini-2.5-flash-lite`
- Phase 1/2 호출 경로: Gemini API(+Batch), Phase 3 임베딩은 Vertex 유지

## 쿼터 상향 요청 현황 (접수 완료)

요청 쿼터:
`GenerateContentRequestsPerMinutePerProjectPerRegionPerBaseModel`

- `gemini-2.5-flash-lite`, `asia-southeast1`, 요청값 `30 RPM`
  - preference: `b3efb306-398a-4842-ba8a-cc2c47b6cb98`
  - 상태: `reconciling=true`
- `gemini-2.5-flash-lite`, `us-central1`, 요청값 `30 RPM`
  - preference: `b46df814-592f-4fbd-82c3-a6bef7bdc50e`
  - 상태: `reconciling=true`

## 문서 인덱스

- 전략/로드맵: `전략 전환 실행 계획.md`
- MVP 상태: `MVP_IMPROVEMENT_STATUS.md`
- Phase 1: `페이즈1 개발 문서.md`
- Phase 2: `페이즈2 개발 문서.md`
- Phase 3: `페이즈3 개발 문서.md`
- Phase 4: `페이즈4 개발 문서.md`
- 환경/초기 설정: `SETUP_GUIDE.md`
- 인프라(Terraform): `infra/README.md`

## 다음 우선순위

- 근거 타임스탬프 클릭 시 오디오 플레이어 점프 UX
- 추천 큐 완료 체크(학습 행동 KPI 수집)
- 멀티에이전트 최종 검증 단계(Advocate/Skeptic/Judge) 설계/도입
