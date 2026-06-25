---
date: 2026-06-25
category: decision
tier: 2
importance: major
status: resolved
tags: [crdt-engine, code-review, rust, m1, convergence]
related:
  - plans/2026-06-25-m1-convergence-impl.md
  - dev-logs/2026-06-25-m1-repo-scaffold.md
---

# M1 crdt-engine 코드리뷰 — rust-expert + code-reviewer 병렬

PR ressKim-io/weDocs-crdt-engine#1 (`feature/m1-merge-fanout`) 머지 전, 엔진 본 구현을
`rust-expert`(CRDT/동시성 정확성 ★) + `code-reviewer`(일반 품질) 두 에이전트로 병렬 리뷰.
결과를 통합·정직 검증(`cargo fmt --check` 주장 직접 재확인) 후 머지 전 8건 반영, 나머지 후속.

## 검증되어 "안전" 판정 (rust-expert, 조치 불필요)

가장 큰 소득 — 핵심 위험 가설들이 **검증으로 안전 확인**됨:

| 항목 | 판정 | 근거 |
|---|---|---|
| `select!` + `inbound.message()` cancel-safety | 안전 | tonic `Streaming` 디코드 상태가 `&mut self`에 보존 → 브랜치 취소돼도 ClientFrame 무손실. broadcast `recv()`는 문서상 cancel-safe |
| lock discipline | 안전 | Mutex 보유 중 `.await` 없음, §D-2 구독-후-스냅샷 정확 |
| Lagged full-resync 수렴성 | 안전 | yrs 멱등·교환 → 재수렴 보장, 순서/중복 무해 |
| spawn task 정리 | 안전 | 정상/비정상 종료 모두 자가 break, 누수 없음 |

> 단, cancel-safety는 "tonic 구현 사실"이지 "문서화된 계약"이 아님 → `select!`에 근거 주석 + config-contract-audit(tonic 버전업 시 재확인) 표기. 코드에 반영함.

## 머지 전 반영 (8건)

| ID | 항목 | 합의 | 커밋 |
|---|---|---|---|
| F1 | `ClientFrame.doc_id` ≠ stream doc_id → reject(InvalidArgument). 게이트웨이 오라우팅 시 **조용한 교차오염** 방지 (§D-1 계약 미구현이었음) | rust=Major / code=**Critical** | c51029a |
| F2 | `cargo fmt` 드리프트 3파일 | rust=Major | b81b6de |
| F3 | `full_state_v1`가 없는 doc 조회 시 **빈 Doc 생성 부작용** → `get`+빈 바이트 | 둘 다 | c51029a |
| F4 | `sync()` 12레벨 중첩 → `handle_inbound`/`handle_broadcast` 분리(SLAP) | code | c51029a |
| F5 | 손상 프레임 처리 비대칭 — 손상 `state_vector`가 `internal`+스트림 종료였음 → 로그+유지(update와 대칭) | rust | c51029a |
| F6 | `corrupt_update` 테스트 `assert!(is_err())` → `matches!(EngineError::Codec(_))` | code | b81b6de |
| F7 | 백프레셔 상수 관계 주석(`FANOUT_CAPACITY` 256 / `OUTBOUND_BUFFER` 64) | 둘 다 | c51029a |
| F8 | bench 미사용 `_text` 라인 제거 | code | b81b6de |

신규: doc_id 불일치 거부/수용 단위 테스트 2건(`src/service.rs`). 재검증 = `cargo test` 8 green
(service 2 + proptest 3 + fanout 3) · `cargo clippy --all-targets -D warnings` 무경고 · `cargo fmt --check` clean.

## 후속(M1.5 / Phase 4) — 의도적 연기

- `eprintln!` → `tracing` 구조화 로깅 (Phase 4 OTel에서 일괄, 지금 TODO 주석만 — 양 reviewer 합의)
- 테스트 헬퍼 3파일 중복 DRY 공통화 (code CR-006)
- proptest에 **shared-base 동시편집 + delete op** 케이스 추가 (rust n1) — 현 테스트는 독립 update만
- `lagged_total` 메트릭, idle 세션 keep-alive/timeout, 테스트 naming nits

## 교훈

- **두 reviewer의 severity 불일치가 신호다.** doc_id 검증을 rust=Major / code=Critical로 갈렸는데,
  "저비용 + 데이터 무결성 영향"이라 Critical 쪽을 따랐다. 비용 대비 blast radius로 판정.
- **리뷰어 주장도 검증한다.** code-reviewer의 CR-004("two_replicas가 두 복제본 모델 아님")는 제안 코드가
  현재와 동일 → 실substance는 네이밍. `cargo fmt --check` 실패 주장은 직접 재현해 확정(deep-thinking).
- **"안전" 판정도 산출물이다.** cancel-safety/lock/lagged를 검증해 안전 확인한 것이 이 리뷰의 최대 가치 —
  근거를 코드 주석으로 고정해 회귀(tonic 버전업) 대비.
