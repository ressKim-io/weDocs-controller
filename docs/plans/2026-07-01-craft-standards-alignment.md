---
date: 2026-07-01
slug: craft-standards-alignment
status: in-progress
related:
  - ../../.claude/rules/error-handling.md
  - ../../.claude/rules/concurrency.md
  - ../../.claude/rules/layering-readability.md
  - ../../.claude/rules/observability.md
  - dev-logs/2026-07-01-craft-standards-set-completion.md
---

# 크래프트 표준 정합 개선 — crdt-engine(Rust) + backend(Java)

## Context (왜)

controller에 방금 머지된 4개 크래프트 표준(`error-handling` / `concurrency` / `layering-readability` / `observability`)은 리뷰 게이트가 강제하는 체크리스트다. 이 중 3개 문서가 **본 프로젝트의 기존 코드**를 동기 예시로 직접 인용한다(엔진 `Arc<tokio::sync::Mutex<HashMap>>` 전역락, raw `doc_id: String`, 수동 `impl Display+Error`). 즉 "아는데 안 쓴" 갭을 표준 도입과 동시에 닫는 정합 패스다.

**스캔 결과**: 실제 위반은 전부 **crdt-engine(Rust)** 에 있다. backend(Java)는 blocking 위반이 없다(`ConcurrentHashMap` 정상, 엔티티에 `@Data` 미사용, REST 컨트롤러 아직 없음 → error-handling P1/P3 N/A). backend는 `[A]` advisory(엔티티 수기 getter → Lombok)만 해당.

**검증 완료 사실**(Plan 에이전트가 yrs 0.27.2 소스·`cargo add --dry-run`으로 확인):
- `dashmap`은 이미 yrs의 전이 의존성(직접 추가해도 크레이트 0개 증가). `parking_lot` 직접 추가 시 크레이트 1개만 증가.
- `yrs::Doc`은 `unsafe impl Send + Sync`이며 내부 `RwLock`으로 실제 동기화 → `transact()`는 blocking(동기), `.await` 아님. 따라서 per-doc 락은 **동기락**(parking_lot)이 옳다(concurrency.md P5).
- `Update::decode_v1` → `encoding::read::Error`, `apply_update` → `UpdateError` = **서로 다른 타입**. 단일 `Codec(#[from] yrs::error::Error)`로 원인 체인(P4) 통합 불가 → `Codec(String)` 유지가 최소·올바른 선택(P4 full은 변형 2분할=메시지·테스트 변경 → 별도 후속으로 스코프아웃).

---

## Phase A — crdt-engine (Rust) · 지금 착수 가능

레포: `/home/ressbe/my-file/weDocs/weDocs-crdt-engine` (현재 `main`, clean, origin 동기).
브랜치: `refactor/craft-standards-alignment` (신규). 논리 단위 3커밋. **push/PR은 별도 승인**(서비스 레포 규칙).

수정 파일: `Cargo.toml` · `src/engine.rs` · `src/service.rs` · `tests/registry_fanout.rs`. (`lib.rs`/`main.rs`/`telemetry.rs`는 무변경 — observability.md 이미 준수.)

### 실행 체크리스트
- [x] Commit 1 — thiserror로 EngineError derive (`538ace0`)
- [x] Commit 2 — DashMap 샤딩 + per-doc parking_lot::Mutex (`2d933fc`)
- [x] Commit 3 — DocId newtype 도입 (`79c3786`)
- [x] 검증: build/clippy(-D warnings)/fmt/test + `cargo bench --no-run` + CI `make check && make test` 전부 green
- [x] push + PR 생성 (승인됨) → [crdt-engine PR #4](https://github.com/ressKim-io/weDocs-crdt-engine/pull/4) OPEN

### 검증 (각 커밋 후)
```sh
cargo build --all-targets && cargo clippy --all-targets -- -D warnings && cargo fmt --check && cargo test
```
commit 2·3 추가: `cargo bench --no-run`. 전체 후 `make check && make test`. → **STOP**(push/PR 승인 대기).

### 주의(정확성 리스크 — 반드시 지킬 것)
- **DashMap 가드 수명**: `.value().clone()`을 `.lock()` **이전 문장에서 끝내** 샤드 가드를 per-doc 임계구역 동안 붙들지 않는다. `if let Some(e)=docs.get(){ e.lock()... }` 금지.
- **subscribe-before-snapshot 불변식(§D-2)**: `tx.subscribe()`+`state_vector()`가 **같은 per-doc 락** 안 → doc X open이 doc X apply_v1과 완전 직렬화, 타 doc과 독립.
- `unwrap`/`expect`/`panic!` 신규 도입 금지(`ok_or_else(..)?` / `let-else`).

---

## Phase B — backend doc-service (Java) · **M2 Phase 1a PR #3 머지 + main 최신화 후**

레포: `/home/ressbe/my-file/weDocs/weDocs-backend`. 현재 `feature/m2-doc-service-skeleton`(PR #3 OPEN, 리뷰 1차 완료·머지 대기). **선행 조건: PR #3 머지 → `git checkout main && git pull` → 새 브랜치.**

**성격**: blocking 위반 없음. layering-readability `[A]` advisory(엔티티 수기 getter/생성자 → Lombok)만. 우선순위 낮음.

### 실행 체크리스트
- [ ] 게이트: ⚠️ **Lombok × JDK 25 호환성 검증**(`./gradlew dependencies | grep lombok` → 릴리스노트 대조). 미지원이면 최신 핀 or 보류.
- [ ] `doc-service/build.gradle.kts`: Lombok `compileOnly` + `annotationProcessor`(BOM 버전).
- [ ] 엔티티 4종(`Page`/`Workspace`/`User`/`PageSnapshot`) + 베이스 2종(`BaseTimeEntity`/`BaseCreatedEntity`)에 `@Getter` + `@NoArgsConstructor(access = PROTECTED)`. 수기 getter·`protected Xxx(){}` 제거. **비즈니스 생성자·`rename()` 유지.**
  - ⛔ `@Data`/`@ToString`/기본 `@EqualsAndHashCode` 금지. equals/hashCode 추가 안 함(identity 유지).
- [ ] 검증: `./gradlew :doc-service:compileJava :doc-service:test` (TC 영속 테스트 3건 green). → **STOP**.

---

## 재개 지점 (Resume)
- **마지막 완료** = Phase A 완료 → [crdt-engine PR #4](https://github.com/ressKim-io/weDocs-crdt-engine/pull/4) OPEN (3커밋 `538ace0`/`2d933fc`/`79c3786`, 전체 검증 green).
- **다음** = PR #4 리뷰/머지 대기. 그 후 = Phase B(backend Lombok) — **단, backend M2 Phase 1a PR #3 머지 + main 최신화 전엔 착수 금지**.
- **주의** = 서비스 레포는 branch+PR+**건별 승인**·push 승인. controller만 main 직접.

## 범위 밖
- error-handling P4 full(원인 체인 `#[source]`) — yrs 에러 2타입 분할 필요, 별도 후속.
- concurrency Actor(Level-2, 락 프리) 리팩터 = M2/M3 벤치 트랙.
- backend equals/hashCode 도입, REST `@RestControllerAdvice`(= Phase 1c).
- frontend(React) — 대상 표준 아님. proto 변경 없음.
