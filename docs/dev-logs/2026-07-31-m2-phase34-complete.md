---
date: 2026-07-31
category: milestone
tier: 1
importance: critical
status: resolved
tags: [m2, phase3, phase4, snapshot, persistence, sweeper, dod, live-validation]
related:
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0022-module-structure-rust.md
  - plans/2026-07-29-m2-phase34-engine-persistence.md
  - dev-logs/2026-07-29-m2-phase34-engine-restore.md
  - dev-logs/2026-07-30-m2-phase4-doc-service-adapter.md
---

# M2 Phase 3+4 완료 — 스냅샷 영속화 전 경로 동작

> 편집 → 엔진 수신 → sweeper 유휴 감지 → SaveSnapshot RPC → DB 저장 → 엔진 재시작 →
> LoadSnapshot 복원 → 클라이언트 재접속 시 내용 유지. **M2 DoD를 로컬 4프로세스로 실증.**

## 타임라인

| 날짜 | 단계 | 산출 |
|---|---|---|
| 07-29 | C3 복원 코어 + C3.5 모듈 재편 | engine `2ab925e`, `28e1b9c` |
| 07-30 | C4 doc-service 어댑터 | engine `1a14f13` (PR #15) |
| 07-30 | C5 저장 회계 (dirty tracking) | engine PR #16, 커밋 6건 |
| 07-31 | C6 전역 스위퍼 + graceful flush | engine PR #17 |
| 07-31 | C7 backend 하드닝 | backend PR #20 (`abf7dc8`) |
| 07-31 | 실기동 검증 (M2 DoD) | 이 dev-log |

## 실기동 검증 결과

환경: postgres(docker) + doc-service(bootRun) + ws-gateway(bootRun) + crdt-engine(cargo run, `DOC_SERVICE_ADDR=http://localhost:50052`)

```
page_id                              | version | blob_bytes
2a237fac-03c0-4dd3-90b1-1c8434186310 |       7 |        430
```

엔진 재시작 후 로그: `doc opened doc_id=2a237fac-... version=7` — 스냅샷 복원 확인.

## 교훈

### 1. 실행 순서가 plan 번호와 반대여야 했다

복원(Phase 4)을 먼저 넣고 저장(Phase 3)을 나중에. 반대로 하면 엔진 재시작 후 빈 Doc에 stale
클라가 붙어 정상 스냅샷을 열화된 상태로 덮어쓰는 구간이 생긴다. plan 작성 시점에 이 순서를
명시해 두었고, 실제로 이 순서를 지켰다.

### 2. FK/PK 위반 오분류가 조용한 데이터 유실을 만든다

`DataIntegrityViolationException`을 전부 `PAGE_NOT_FOUND`로 접으면, PK 경합(동시 삽입)도
"페이지 없음"이 된다. 엔진은 `NotFound`를 영구 실패로 보고 그 doc의 영속화를 끈다.
C7에서 SQL state code(`23505` vs `23503`)로 구분해 해소.

### 3. 게이트를 붙이는 것과 게이트가 도는 것은 다르다

C5에서 `make bench-compare`가 한 번도 동작한 적이 없었음을 발견. `cargo bench`가 libtest
하네스를 벤치 타깃으로 돌려서 criterion 플래그를 못 알아듣는 구조였다. `--bench convergence`
지정 + `make bench-smoke`를 CI에 추가해 해소.

### 4. 엔진 ALREADY_EXISTS 재시도 계약이 누락됐다

C7에서 PK conflict를 `ALREADY_EXISTS`로 올바르게 반환하게 됐지만, 엔진 sweeper가 이 코드를
어떻게 분류하는지는 아직 구현되지 않았다. engine issue #18로 추적 — C6 sweeper의 에러
분류 체계에 동승 예정.

### 5. WS 재연결 로그가 기능 이상처럼 보인다

y-websocket의 재연결 사이클에서 "closed before established" 로그가 콘솔에 반복 출력.
핸드셰이크 자체는 성공하고 엔진 세션도 정상이라 데이터 흐름에 영향 없음.
UX 관점에서 불필요한 노이즈 — 프론트 쪽에서 재연결 간격/중복 provider 정리 필요.

## 열린 후속

- engine issue #18: `ALREADY_EXISTS` 재시도 분류 (C6 동승)
- M5: 컨테이너화 + docker-compose + E2E 자동화
- 관측: 에러 전용 구조화 로그 (logback JSON appender + engine tracing layer)
- API 문서: SpringDoc OpenAPI + proto-doc
