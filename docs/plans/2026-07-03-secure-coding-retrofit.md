---
date: 2026-07-03
slug: secure-coding-retrofit
status: done
related:
  - plans/2026-07-03-security-quality-standards.md
  - plans/2026-07-01-craft-standards-alignment.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
  - dev-logs/2026-07-18-secure-coding-retrofit-completion.md
---

# secure-coding·design-patterns retrofit — 기존 코드 [B] 위반 소급 정합

## Context

크래프트 표준 6종 체제(2026-07-03, [표준 도입 plan](2026-07-03-security-quality-standards.md))가 신규 diff는 게이트로 막지만, **기존 코드의 [B] 위반은 소급 수정이 필요**하다. 위반 목록은 추정이 아니라 **게이트 시뮬레이션 실측**(crdt-engine HEAD `0355a58`, rust-expert 판정 — `secure-coding.md` 부록 수록): 기대 [B] 6종 전부 발화, 오탐 0.

핵심 위험 = **3-레포 관통 DoS 체인**: frontend 무검증 room → gateway 무검증 전달(`roomFromUri`) → engine 무한 문서 생성+eviction 없음. 인증(ADR-0014, M2 Phase 2)과 **독립**인 결함 — 인증이 붙어도 인가된 사용자가 같은 방식으로 자원 고갈 가능.

진행 형식은 직전 정합 사이드트랙([2026-07-01](2026-07-01-craft-standards-alignment.md))과 동일: Phase별 대상 파일 SSOT 명시 → 검증 명령 → **STOP**(push/PR 건별 승인).

## 작업 목록 (우선순위)

### P0 — DoS 체인 차단 (독립 PR 2건)

**엔진 PR (crdt-engine, 1건)** — 시뮬레이션 fire 직결:
- [x] `DocId` 검증 생성자: `From` → `TryFrom<&str>`(길이·문자집합) — `engine.rs:39-49` + 호출부 `service.rs:127-133` (SC-P1)
- [x] 문서 수 상한: `open()` 삽입 전 상한 검사, 초과 시 `Status::resource_exhausted` — `engine.rs:109-123` (SC-P2; **eviction은 범위 밖** — ADR-0013 영속화 선행)
- [x] `max_decoding_message_size` 명시 + `concurrency_limit`/timeout 근거화 — `main.rs:23-29` (SC-P2/P5)
- [x] `ServerFrame` 스마트 생성자로 수동 조립 4곳 단일화 — `service.rs:149·204·235·246` (DP-P4/P5)
- [x] doc-id mismatch 에러의 서버측 바인딩 에코백 제거(분류 code만) — `service.rs:193` (SC-P4)

→ [crdt-engine PR #9](https://github.com/ressKim-io/weDocs-crdt-engine/pull/9) 머지(`5854b72`, 2026-07-18). 17건 green.

**게이트웨이 PR (backend, 1건)**:
- [x] room 경계 검증(`HandshakeInterceptor`: 길이·문자집합) + `RoomId` 도메인 타입 내부 관통 — `roomFromUri` 소급 (SC-P1, DP-P6)
- [x] WS 프레임/버퍼 상한 + 세션 idle timeout 명시(`ServletServerContainerFactoryBean`) — Tomcat 기본 8192B 암묵 의존 해소, Yjs sync-step2 최대 크기 근거 명시 (SC-P2)
- [x] Origin 화이트리스트(프로파일 분리) — `setAllowedOriginPatterns("*")` 해소 (SC-P5)

→ [backend PR #14](https://github.com/ressKim-io/weDocs-backend/pull/14) 머지(`1d94a9a`, 2026-07-18). 40건 green.

### P1 — 안전 기본값 (M2 Phase 1b/2와 접점)
- [x] gateway→engine gRPC: 채널 keepalive·재연결 정책. **신규 unary deadline은 M2 1b 신규 코드가 게이트로 강제**(retrofit 아님) (SC-P5) — 위 게이트웨이 PR #14에 포함
- [x] `Sync`/`GetSnapshot` 신뢰 경계 주석+이슈(mTLS/NetworkPolicy 전제 — M5) — 인가 **구현**은 M2 Phase 2 소속 (SC-P3) — 위 엔진 PR #9에 포함

### P2 — 잔여 [A]류
- [x] dev 크리덴셜 프로파일 분리(`application.yml`) · 무페이지네이션 조회 `Pageable`(doc-service — backend 최신 fetch 후 재확인) — [backend PR #15](https://github.com/ressKim-io/weDocs-backend/pull/15) 머지(`a74667b`). 페이지네이션은 재확인 결과 기존에 이미 처리됨(트리 쿼리=Limit, `findById_UserId`=문서화된 예외).
- [x] frontend: room 파라미터 클라 측 sanity + `wss://` 배포 강제(비고 — 크래프트 렌즈 비대상) — [frontend PR #3](https://github.com/ressKim-io/weDocs-frontend/pull/3) 머지(`f7b5b92`).

### 제외 (오지목 교정 — 게이트 시뮬레이션 발견)
- ~~레지스트리 `DocStore` trait 도입~~ — **기각**. ADR-0013의 실제 seam은 엔진→doc-service **아웃바운드 클라이언트**(SaveSnapshot/LoadSnapshot)이지 레지스트리가 아님. trait(`SnapshotStore`)는 **M2 Phase 3 신설 코드**에 design-patterns P2 게이트로 적용(retrofit 대상 아님). 레지스트리 trait는 과설계.
- viewer write-block·인가 구현 → M2 Phase 2 / GetSnapshot 접근 제어 최종 → M5 mesh와 함께.

## 배치·순서

1. **엔진 PR 먼저**(독립적, 충돌 없음) → 2. **게이트웨이 PR은 M2 Phase 2 브랜치 분기 전 머지**(`WebSocketConfig`를 Phase 2 핸드셰이크 인터셉터도 만지므로 충돌 최소화). 두 PR 모두 branch+PR+**건별 승인**.

## 검증

- 엔진: `cargo build && cargo clippy -- -D warnings && cargo fmt --check && cargo test` + `make check` + `cargo bench --no-run` + proptest 수렴 회귀
- 게이트웨이: `./gradlew test`(기존 22+ green 유지) + 로컬 engine+gateway 실기동 E2E 수렴(frontend vitest, M1 Phase 3 하니스)
- **게이트 재실행**: 크래프트 렌즈 6종으로 수정 diff 리뷰 → 시뮬레이션 fire 목록(secure-coding.md 부록)이 소거됐는지 대조
- 대형 프레임 회귀: 상한 설정 후 정상 대형 sync-step2가 통과하는지(상한을 너무 낮게 잡는 역결함 방지)

## 재개 지점 (Resume)

- 마지막 완료 = **전 항목 완료(2026-07-18)**: crdt-engine PR #9(`5854b72`)·backend PR #14(`1d94a9a`)·backend PR #15(`a74667b`)·frontend PR #3(`f7b5b92`) 전부 머지. 상세 = `docs/dev-logs/2026-07-18-secure-coding-retrofit-completion.md`.
- 다음 = Phase 2(M2 인증) 착수 — `docs/plans/2026-06-30-m2-persistence-session.md` §재개지점 참조.
- 주의 = 이 4 PR은 controller와 별도 세션에서 진행·머지되어 있었고, controller의 plan/CLAUDE.md 상태 갱신이 하루 지연됨(2026-07-19 pull 동기화 중 발견·정합). 서비스 레포 작업 후에는 controller plan도 같은 세션에서 갱신할 것.

## 범위 밖

- 인증/인가 구현(JWT·CheckPermission·viewer write-block) — M2 Phase 1c/2 몫
- 엔진 문서 eviction/idle unload — ADR-0013 영속화(M2 Phase 3+) 선행 조건
- TLS/mTLS·NetworkPolicy — M5(Istio ztunnel). SAST 확장(semgrep/CodeQL) — M5
- 레이트리밋·캡 정량화 — M3 부하 검증과 동시
- rust 일반 패턴 스킬(`skills/rust/rust-idioms.md`) 신설 — **트리거**: 신규 게이트 2~3회 실행 후 rust-expert [A] 코멘트의 처방 구체성이 부족하면 그때 SKILL-SPEC 준수로 신설
