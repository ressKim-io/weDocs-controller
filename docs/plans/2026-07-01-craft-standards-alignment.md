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

## Phase C — crdt-engine `sync()` 함수 분해 (layering P1) · **PR #4 머지 후 별도 PR**

`service.rs::sync()`가 73줄(그 중 `tokio::spawn` 클로저 37줄)로 layering-readability P1(≈40줄)·clean-code(50줄 초과 분할) 초과 + 추상화 수준 혼재(SLAP). 동작 불변 리팩토링.
- 세션 루프(step1 전송 + `loop{select!{inbound,fanout}}`)를 `async fn run_session(...)`로 추출 → `sync()`는 셋업+spawn만(~30줄).
- (선택) traceparent/doc-id 파싱을 `extract_*` 헬퍼로.
- 이미 있는 `handle_inbound`/`handle_broadcast`와 같은 분해 방향(일관성).
- **PR #4와 분리 이유**: PR #4=동작 불변 기계적 치환(리뷰 쉬움) vs 함수 분해=로직 이동(동작 동일성 별도 검증). git.md 하나의 목적=하나의 PR.
- 검증: 로직 이동만 → 기존 테스트 그대로 green. `make check && make test`.

---

## 재개 지점 (Resume)
- **마지막 완료** = Phase B **머지 완료**([backend PR #4](https://github.com/ressKim-io/weDocs-backend/pull/4), squash `18e1aa1`). backend origin/main 최신화 완료(로컬도 fast-forward, feature 브랜치 원격 삭제됨).
- **다음(이 세션 clear 후 시작점)** = **Phase C(crdt-engine `sync()` 함수 분해)** — crdt-engine 레포에서 새 브랜치, §Phase C 설명대로 `run_session` 추출. PR #4(craft-standards-alignment) 머지됐으니 독립 착수 가능.
- **주의** = 서비스 레포는 branch+PR+**건별 승인**·push 승인. controller만 main 직접.

## 범위 밖
- error-handling P4 full(원인 체인 `#[source]`) — yrs 에러 2타입 분할 필요, 별도 후속.
- concurrency Actor(Level-2, 락 프리) 리팩터 = M2/M3 벤치 트랙.
- backend equals/hashCode 도입, REST `@RestControllerAdvice`(= Phase 1c).
- frontend(React) — 대상 표준 아님. proto 변경 없음.
