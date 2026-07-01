---
date: 2026-07-01
category: meta
tier: 2
importance: major
status: resolved
tags: [concurrency, layering-readability, observability, code-review, rules, standard-activation]
related:
  - dev-logs/2026-07-01-error-handling-standard-activation.md
  - rules/error-handling.md
---

# 크래프트 표준 세트 완성 — concurrency·layering-readability·observability 추가

## Context
- 첫 표준(`error-handling.md`) 활성화(`docs/dev-logs/2026-07-01-error-handling-standard-activation.md`) 직후, 같은 세션에서 사용자가 나머지 3개 표준(concurrency/layering-readability/observability)을 한 번에 제공하며 동일 패턴으로 추가 요청.
- 목표: 4개 표준을 하나의 세트로 완성하고, 이미 배선된 🦀 rust-expert / ☕ java-expert 크래프트 렌즈가 4개 전부를 실행하도록 게이트 참조를 확장.

## 한 일

### 1. 3개 표준 신규 작성
- `concurrency.md`(P1~7 — tokio 락종류 선택 기준+샤딩 / Java `ConcurrentHashMap`+VT pinning)
- `layering-readability.md`(P1~6 — Java `record`/Lombok+엔티티 `@Data` 금지 / Rust newtype+derive)
- `observability.md`(P1~6 — 코드 레벨 로깅/트레이싱. `monitoring.md`(운영 레벨)와 역할을 문서 서두에서 명시적으로 분리)

### 2. 사실 확인 (`deep-thinking.md` 검증 의무)
`concurrency.md` 부록이 "이 체크리스트가 실제 blocking 2건을 잡았다"는 증명 형태라 특히 엄격히 검증했다:
- `DocRegistry.docs: Arc<Mutex<HashMap>>`(`tokio::sync::Mutex`) 확인 → 전역락 샤딩 안 됨(P4) 실재.
- `open`/`apply_v1`/`diff_v1`/`full_state_v1` 4개 메서드 전부 소스 전문 대조 — 락 보유 구간에 `.await` 0건 → `tokio::sync::Mutex`가 불필요한 비동기 오버헤드(P5) 실재.
- `FANOUT_CAPACITY=256`/`OUTBOUND_BUFFER=64` 수치·"락 보유 중 .await 금지" 주석까지 토씨 일치. `handle_inbound`/`handle_broadcast` 함수 분리, `tracing::warn!(%doc_id, ...)` 구조적 로깅 패턴도 실제 코드와 일치.
- 결론: 부록의 "P4/P5 두 blocking 포착" 주장은 검증대로 정확 — 내용 수정 없이 그대로 반영.

### 3. 게이트 배선 확장 (신규 행 추가 아님 — 기존 렌즈의 체크리스트 목록만 확장)
- `code-review.md` 🦀/☕ 두 행의 "핵심체크" 열을 `error-handling.md` 단독 참조 → 4개 표준 전체 참조로 갱신. **표 행수는 늘리지 않음** — 언어당 1행 유지, 그 행이 검사하는 체크리스트 개수만 늘어남.
- `phase-workflow.md` Gate 3의 "예: `error-handling.md`" 단일 예시 → 4개 파일 전체 나열로 갱신.
- `CLAUDE.md` "상황별 룰" 인덱스의 단일 `error-handling.md` 줄 → 4개 파일 묶음 줄로 교체.

## 결정 (decisions)
- **표준이 늘어도 `code-review.md` 표 행수는 늘리지 않는다** — 언어(Rust/Java) 크래프트 렌즈는 1행씩 고정, 그 행이 실행하는 표준 체크리스트 목록만 늘어나는 구조로 확정. 직전에 저장한 [[craft-standards-gate-activation]] 메모리가 "표준마다 행 추가"로 오해될 소지가 있어 이 결정에 맞춰 갱신 필요.
- 각 표준 파일 내부의 저작 시점 라벨("두 번째 표준(2026-06-30)" 등)은 사용자 원문 그대로 보존 — 실제 배포일(오늘, 2026-07-01)과 다르더라도 임의 수정하지 않음(첫 표준 활성화 때와 동일 판단 유지).

## 다음 세션 할 일 (TODO)
1. `ress-claude-agents` 로컬 경로가 확보되면 4개 표준을 일괄 승격.
2. ~~`concurrency.md` 부록이 지적한 실제 코드 갭(`DocRegistry` 전역락 미샤딩·`tokio::sync::Mutex` 오용)은 이번 세션 범위 밖~~ → **해소됨(2026-07-01)**: `docs/plans/2026-07-01-craft-standards-alignment.md`(status: done)에서 크래프트 표준 4종 전체(error-handling/concurrency/layering-readability/observability)가 지적한 crdt-engine/backend 갭을 정합 — DashMap 샤딩+parking_lot(concurrency P4/P5), thiserror(error-handling), DocId newtype+Lombok(layering-readability), `sync()` 함수 분해(layering-readability P1). [crdt-engine PR #4](https://github.com/ressKim-io/weDocs-crdt-engine/pull/4)·[#5](https://github.com/ressKim-io/weDocs-crdt-engine/pull/5)·[backend PR #4](https://github.com/ressKim-io/weDocs-backend/pull/4) 전부 머지.
3. 다음 표준이 추가되면 이번 결정(신규 행 추가 아님, 기존 렌즈의 체크리스트 목록만 확장)을 그대로 따른다.

## 관련 자료
- `.claude/rules/concurrency.md` · `.claude/rules/layering-readability.md` · `.claude/rules/observability.md`
- 첫 표준 활성화: `docs/dev-logs/2026-07-01-error-handling-standard-activation.md`
