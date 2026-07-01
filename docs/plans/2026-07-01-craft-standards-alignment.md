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

## Phase B — backend doc-service (Java) · **착수 가능 (PR #3 머지 완료 `54a8b48`)**

레포: `/home/ressbe/my-file/weDocs/weDocs-backend`. PR #3가 origin/main에 머지됨(`54a8b48`). **선행: 로컬이 아직 `feature/m2-doc-service-skeleton` → `git checkout main && git pull` → 새 브랜치.**

**성격**: blocking 위반 없음. layering-readability `[A]` advisory(엔티티 수기 getter/생성자 → Lombok)만. 우선순위 낮음.

**✅ 완료** — [backend PR #4](https://github.com/ressKim-io/weDocs-backend/pull/4) 승인·머지(squash, `18e1aa1`), 브랜치 삭제됨.

### 대상 파일 (경로 SSOT — 재도출 불필요)
루트 `/home/ressbe/my-file/weDocs/weDocs-backend`, 모듈 `doc-service`.
- 빌드: `doc-service/build.gradle.kts` (현재 Lombok 없음, JDK 25 toolchain, Spring Boot 4.1.0 BOM)
- 엔티티/베이스: `doc-service/src/main/java/io/wedocs/doc/domain/` 아래
  `Page.java`(getter 6·`rename()` 유지) · `Workspace.java`(3) · `User.java`(5·`@Convert systemRole`) · `PageSnapshot.java`(3) · `BaseTimeEntity.java`(`getUpdatedAt`) · `BaseCreatedEntity.java`(`getCreatedAt`)
- 검증 테스트(변경 없어야 함, 통과 확인용): `doc-service/src/test/java/io/wedocs/doc/PageTreePersistenceTest.java` — `new User(...)`/`new Page(...)` 등 비즈니스 생성자 사용 → 생성자 시그니처 유지 필수.

### 실행 체크리스트
- [x] 착수 전: `cd weDocs-backend && git checkout main && git pull` → 새 브랜치 `refactor/craft-standards-lombok`.
- [x] 게이트: ⚠️ **Lombok × JDK 25 호환성 검증** — Spring Boot 4.1.0 BOM resolve = `1.18.46`(로컬 캐시 POM 확인). Lombok 공식 changelog(WebFetch): JDK25 지원은 **v1.18.40**(2025-09-04)부터, 1.18.46은 그 이후 안정 버전 → **지원 확인, 버전 핀 불필요**.
- [x] `doc-service/build.gradle.kts`: Lombok `compileOnly` + `annotationProcessor`(BOM 버전).
- [x] 엔티티 4종 + 베이스 2종에 `@Getter` + `@NoArgsConstructor(access = AccessLevel.PROTECTED)`. 수기 getter·`protected Xxx(){}` 제거. **비즈니스 생성자·`rename()` 유지.** getter명 정합: `archived`→`isArchived()`, `position`→`getPosition()` 그대로 생성됨(Lombok 확인).
  - ⛔ `@Data`/`@ToString`/기본 `@EqualsAndHashCode` 금지 — 미사용 확인. equals/hashCode 추가 안 함(identity 유지).
- [x] 검증: `./gradlew :doc-service:compileJava :doc-service:test` — compileJava green, PageTreePersistenceTest **6건**(계획서 "3건"은 과소 기재 — 실제 테스트 메서드 6개) 전부 green(`tests="6" skipped="0" failures="0" errors="0"`). → 커밋 `0226a97`. **STOP**(push/PR 승인 대기).

### 함정 발견 — annotationProcessor는 BOM platform을 상속하지 않음
`implementation(platform(...))`는 `implementation`을 extendsFrom하는 구성(`compileClasspath`/`testImplementation` 등)에만 버전 제약이 전파된다. `annotationProcessor`는 별도 구성이라 `compileOnly("org.projectlombok:lombok")`만으론 `annotationProcessor`가 버전을 못 찾고 `Could not find org.projectlombok:lombok:.`로 실패. 해결: `annotationProcessor(platform("org.springframework.boot:spring-boot-dependencies:4.1.0"))`를 별도 명시. (config-contract-audit.md 사례 — "BOM에 적힌 버전이 자동 적용될 것" mental model 오류.)

---

## Phase C 사전검토 — 외부 아키텍처 제안(Arena+jemalloc+write-behind) 리뷰 (2026-07-01)

Phase C 착수 직전 사용자가 외부에서 받은 성능 아키텍처 제안(bumpalo Arena+jemalloc 하이브리드 할당, dirty-flag+mpsc+debounce write-behind)을 crdt-engine 실제 코드·yrs 0.27.2 소스 기준으로 검증(rust-expert 서브에이전트 교차검증 포함).

- **bumpalo Arena — 영구 반려**. 전제("병합=짧은 수명 트리, 끝나면 일괄 폐기")가 yrs 실제 동작과 상충. `apply_update`→`update.integrate`→`Box<Item>` move→`ClientBlockList`(영속 store) 소유권 이전 체인 확인(`transaction.rs:820`·`update.rs:324`·`block_store.rs:18`). 디코드 블록은 폐기되지 않고 영속 Doc 구조로 move-in. `ItemPtr(NonNull<Item>)` raw pointer 사용 + crate 전체 `allocator_api` 0건 → `&'bump T`로 대체 시 라이프타임상 컴파일 불가.
- **jemalloc — 후보(보류)**. 근거(criterion A/B 벤치) 없이 도입 시 가드레일 5 위반. 채택하려면 `benches/convergence.rs` 하니스로 전/후 실측 별도 스파이크 필요. **사용자 결정: Phase C 먼저, jemalloc 벤치는 별도 후속.**
- **write-behind(dirty flag+mpsc+debounce) — 이미 [ADR-0013](../adr/0013-snapshot-persistence-lifecycle.md)(Accepted)과 정합**. T=10초 유휴 OR N=100 update 상한 트리거로 이미 결정됨(사용자 제안보다 N 상한이 있어 starvation 방지 우위). 단 crdt-engine에 DB 의존성 자체가 없음(Cargo.toml 확인) → **M2 Phase 3(`build_client(true)`) 몫, 지금 액션 아님.** 훅 지점만 확정: `DocRegistry::apply_v1` 성공 직후 mpsc로 DocId 전달(락 아님) → 워커 debounce → 재락 `full_state_v1` 동기 스냅샷 → 락 해제 후 async DB write.

**Phase C 스코프에는 영향 없음** — 아래 원래 계획대로 진행.

---

## Phase C — crdt-engine `sync()` 함수 분해 (layering P1) · **착수**

레포: `/home/ressbe/my-file/weDocs/weDocs-crdt-engine`. 브랜치: `refactor/sync-fn-decomposition`(신규).

`service.rs::sync()`가 73줄(그 중 `tokio::spawn` 클로저 37줄)로 layering-readability P1(≈40줄)·clean-code(50줄 초과 분할) 초과 + 추상화 수준 혼재(SLAP). 동작 불변 리팩토링.
- 세션 루프(step1 전송 + `loop{select!{inbound,fanout}}`)를 `async fn run_session(...)`로 추출 → `sync()`는 셋업+spawn만(~30줄).
- (선택) traceparent/doc-id 파싱을 `extract_*` 헬퍼로.
- 이미 있는 `handle_inbound`/`handle_broadcast`와 같은 분해 방향(일관성).
- **PR #4와 분리 이유**: PR #4=동작 불변 기계적 치환(리뷰 쉬움) vs 함수 분해=로직 이동(동작 동일성 별도 검증). git.md 하나의 목적=하나의 PR.

### 실행 체크리스트
- [x] `cd crdt-engine && git checkout main && git pull` → 새 브랜치 `refactor/sync-fn-decomposition`.
- [x] `run_session(registry, doc_id, inbound, fanout, out_tx, state_vector)` 추출 — `sync()`의 `tokio::spawn(async move {...}.instrument(span))` 클로저 본문을 그대로 이동(로직 변경 없음). `broadcast::Receiver<Vec<u8>>` 타입 명시 위해 `tokio::sync::broadcast` import 추가.
- [x] traceparent 추출·doc-id 파싱을 각각 `extract_trace_context`/`extract_doc_id` 헬퍼로 추출(선택 항목도 실행).
- [x] `sync()` 본문 34줄로 축소 확인(셋업 + spawn만 남김, P1 임계 ~40줄 내).
- [x] 검증: build/clippy(-D warnings)/fmt/test 전부 green(단위 2 + proptest 3 + registry_fanout 3 = 8건). `make check && make test` 동일 green. → 커밋 `ddc4d7d`.
- [ ] push + PR 생성 승인 요청. → **STOP**(현재 여기).

---

## 재개 지점 (Resume)
- **마지막 완료** = Phase C **구현+로컬커밋 완료**(crdt-engine `refactor/sync-fn-decomposition` 브랜치, 커밋 `ddc4d7d`). `run_session`/`extract_trace_context`/`extract_doc_id` 추출, `sync()` 34줄로 축소, build/clippy/fmt/test(8건) + `make check && make test` green. **push/PR 미승인 — 아직 로컬에만 존재.**
- **다음(이 세션 clear 후 시작점)** = Phase C **push + PR 생성 승인 요청** → 승인 시 push·PR 생성.
- **그 다음** = jemalloc criterion A/B 벤치 스파이크(사용자 보류 결정, 별도 작업으로 재요청 시). Phase A/B/C 전부 완료되면 이 plan `status: done`.
- **주의** = 서비스 레포는 branch+PR+**건별 승인**·push 승인. controller만 main 직접.

## 범위 밖
- error-handling P4 full(원인 체인 `#[source]`) — yrs 에러 2타입 분할 필요, 별도 후속.
- concurrency Actor(Level-2, 락 프리) 리팩터 = M2/M3 벤치 트랙.
- bumpalo Arena — 영구 반려(yrs 소유권 모델과 상충, §Phase C 사전검토 참조).
- jemalloc criterion A/B 벤치 — 후보로 보류, 이번 세션 범위 아님.
- backend equals/hashCode 도입, REST `@RestControllerAdvice`(= Phase 1c).
- frontend(React) — 대상 표준 아님. proto 변경 없음.
