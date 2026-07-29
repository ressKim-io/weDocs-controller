---
date: 2026-07-29
slug: m2-phase34-engine-persistence
status: in-progress
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0011-engine-sync-fanout-bridge.md
  - adr/0012-crdt-boundary-content-vs-tree.md
---

# M2 Phase 3+4 — 엔진 스냅샷 복원·저장 (crdt-engine)

> 엔진이 doc-service에 스냅샷을 **저장**하고(Phase 3) 재시작 후 **복원**한다(Phase 4).
> 성공 조건 = M2 DoD: 편집 → 저장 → 엔진 재시작 → 재접속 → 마지막 스냅샷까지 복원.

## Context

**왜 이 작업인가**: M1(실시간 수렴)·M2 Phase 1(doc-service)·Phase 2(인증/인가)는 끝났고,
남은 것이 "프로세스 재시작 = 전 데이터 유실"(ADR-0011 트레이드오프)의 해소다.
ADR-0013이 **엔진 push**를 결정해뒀다 — 엔진이 dirty 시점을 알고 상태 권위를 쥐고 있으니
저장 권위도 엔진이 갖는다.

### 착수 전 실측 — 상태 문서와 어긋난 3건 ✅ 2026-07-29 검증

| 사실 | 기존 기술 | 실측 |
|---|---|---|
| `build_client(true)` flip | "2b에서 선반영 → `SaveSnapshot` **호출 배선부터**" | flip은 됐으나 **`build.rs:18-21`의 `compile_protos`에 `doc.proto`가 없다** → `DocServiceClient` 자체가 미생성. 시작점이 한 칸 앞이다 |
| proto 태그 bump | engine `ci.yml:16` "Phase 3에서 bump 필요" | **불요.** `git show proto-v0.2.0:proto/doc/doc.proto`에 `SaveSnapshot`·`LoadSnapshot` 모두 존재, `git diff proto-v0.2.0 -- proto/` 비어 있음. 그 주석은 stale → C2에서 정정 |
| 엔진의 아웃바운드 gRPC | 2b가 doc-service를 호출한다는 인상 | **엔진에 아웃바운드 클라이언트가 하나도 없다**(`rg 'Channel|Endpoint|connect'` → src/ 0건). 2b는 게이트웨이가 넘긴 `role` 메타 강제였을 뿐. 채널·데드라인·재시도·traceparent 주입이 전부 신규 |

### 확정한 결정 (사용자 2026-07-29)

| # | 결정 | 근거 |
|---|---|---|
| **D1** | **복원 먼저(C3·C4) → 저장 나중(C5·C6)**. plan 번호(3=저장/4=복원)와 실행 순서만 다르고 산출물은 동일 | 저장을 먼저 넣으면 "복원 없는 저장" 구간이 생긴다 — 엔진 재시작 → Doc는 빈 상태 → stale 로컬 상태를 가진 클라가 먼저 붙음 → 스위퍼가 **정상 DB 스냅샷을 열화된 상태로 덮어쓴다**. version 카운터도 0으로 리셋돼 단조성이 성립하지 않는다. 복원을 먼저 넣으면 이 위험 구간이 **존재하지 않는다** |
| **D2** | 저장 트리거 = **전역 sweeper + `try_lock`**(1초 tick) | 태스크 1개, 신호 유실 계열 버그가 원천적으로 없음, `try_lock`이라 머지 핫패스 무간섭(가드레일 5), 종료 flush가 같은 경로 재사용 |
| **D3** | 복원 실패 = **fail-closed**(`Status::unavailable`, 스트림 미개설) | 빈 Doc로 열면 첫 저장이 DB를 덮어써 영구 유실. **문서 fork 불가가 가용성보다 우선.** 대가: doc-service 다운 = 편집 전면 불가(엔진이 doc-service에 하드 의존) |
| **D4** | backend 하드닝 **작은 PR 1건 동승**(C7) | 엔진이 실제로 밀기 시작하면 살아나는 갭 + 이월 finding(`listMine`) 소거 |

**D3 보강 실측** ✅: 게이트웨이 `AuthzHandshakeInterceptor.isUuid`(ws-gateway)가 비UUID room을
핸드셰이크에서 403으로 끊는다 → **엔진에 도달하는 `doc_id`는 항상 UUID**다. doc-service의
`LoadSnapshot`도 `parseUuidOrFail`로 비UUID를 `INVALID_ARGUMENT` 처리하지만(`DocServiceImpl.java:87`),
그 조합은 정상 경로에서 발생 불가(직접 gRPC 호출자·테스트뿐이고 영속화 기본값이 off).
→ **분기 없이 순수 fail-closed.** "비UUID면 빈 Doc로 열고 영속화만 끄기" 대안은 분기만 늘고 실익이 없다.

## 실행 체크리스트

> ⛔ **서비스 레포(crdt-engine·backend)는 브랜치+PR+건별 승인**(push·PR 생성·머지 각각).
> controller(C1·C2·C8)만 main 직접.

- [x] **C1** `docs(plan):` 이 파일 신설 + `status: in-progress` — **코드 작업 전 필수** — `3d9aef6`
- [x] **C2** `docs(adr):` ADR-0013 개정 3건 (재시도 정책 · 복원 실패 fail-closed · T 표현) — `2bf8542`
- [x] **C3** engine PR1a `feat(engine): 스냅샷 복원-우선 open + SnapshotStore 포트` — [PR #13](https://github.com/ressKim-io/weDocs-crdt-engine/pull/13) (CI 3/3 green, **머지 대기**).
      커밋 `b943959`(포트+슬롯) · `37c9b77`(벤치) · `4d93c91`·`61a8399`(게이트 반영).
      실제 736줄(프로덕션 ~405 / 테스트 ~330) — 추정 355줄을 넘겼다. 초과분은 대부분 테스트 10건과 근거 주석
- [ ] **C3.5** engine `refactor: 모듈 구조 + 에러 wire 매핑 + 설정 일원화` ([ADR-0022](../adr/0022-module-structure-rust.md))
      — C4 **전에** 한다. C4가 어댑터·`DOC_SERVICE_ADDR`를 더하면 이동량이 2배가 되므로 지금이 가장 싸다
- [ ] **C4** engine PR1b `feat(persistence): doc-service 복원 배선 + fail-closed` — ~380줄
- [ ] **C5** engine PR2a `feat(engine): 스냅샷 dirty 회계 + 저장 대상 수집` — ~280줄, `bench-compare` 첨부
- [ ] **C6** engine PR2b `feat(sweeper): 전역 스냅샷 스위퍼 + graceful flush` — ~400줄
- [ ] **C7** backend PR3 `fix(doc-service): 스냅샷 경계 검증 + 조회 상한` — C4 머지 후, C5와 병렬 가능
- [ ] **C8** `docs:` dev-log + 이 plan `done` + `current.md` 갱신 + **역방향 점검**

### C2 — ADR 개정 사유

ADR-0013 §트레이드오프 원문은 "3회 지수 백오프 재시도, 소진 시 경고 로그 + **드롭**"이다.
실제 설계에서는 스위퍼가 **매 시도마다 살아있는 상태에서 블롭을 재인코딩**하므로 드롭할
"보관 중인 페이로드"가 존재하지 않는다. 따라서:

- `Transient` → **상한 백오프(최대 60 tick ≈ 1분)로 무기한 재시도.** 비용 = 백오프 창당 RPC 1회
- `NotPersistable`(NOT_FOUND·INVALID_ARGUMENT) / `Permanent`(Unimplemented·PermissionDenied 등)
  → **즉시 영구 비활성** + ERROR 로그. 재시도해도 결과가 같은 것을 매 tick 두드리지 않는다

근거 없는 이탈이 아니라 **기록된 이탈**로 남긴다.

### C3 — 핵심 문제와 해법 (복원-우선 open)

첫 open이 `LoadSnapshot`을 await하는 동안 두 번째 세션이 구독하면, 그 세션은 **빈 문서의
state vector**를 SyncStep1로 받는다. 복원 업데이트는 broadcast가 아니라 doc에 직접 apply되므로
그 세션은 복원분을 영영 못 받고 자기 상태를 권위로 착각해 되민다 = **fork**.

해법 = `DashMap<DocId, Arc<DocSlot>>` + `DocSlot { entry: tokio::sync::OnceCell<Mutex<DocEntry>> }`.
`get_or_try_init`이 ① 동시 opener를 첫 initializer 뒤에 줄세우고(single-flight — 엔진 재시작 후
N개 클라가 동시 재접속해도 `LoadSnapshot`은 1회) ② **실패를 캐시하지 않아** 다음 open이 재시도한다.
복원 `.await`는 `parking_lot::Mutex`가 **아직 생성되기도 전** 시점이라, 동기 락 안에서 await할
방법이 구조적으로 없다(락 규약 보존, `concurrency.md` P5).

```rust
// src/engine.rs — tonic import 없음. 도메인이 포트를 소유한다(DIP, layering-readability P7)
#[async_trait::async_trait]
pub trait SnapshotStore: Send + Sync + 'static {
    async fn load(&self, doc_id: &DocId) -> Result<StoredSnapshot, SnapshotStoreError>;
    async fn save(&self, doc_id: &DocId, snapshot: Vec<u8>, version: i64) -> Result<(), SnapshotStoreError>;
}
pub struct StoredSnapshot { pub blob: Vec<u8>, pub version: i64 }  // 부재 = 빈 blob + version 0
pub enum SnapshotStoreError { Transient(String), NotPersistable(String), Permanent(String) }
pub struct NoopSnapshotStore;   // 기본값 = 현 동작과 바이트 단위로 동일

pub async fn open(&self, doc_id: &DocId) -> Result<Subscription, EngineError>   // sync → async
```

- `apply_v1`/`diff_v1`/`full_state_v1`은 **동기 유지** — `slot.entry.get()`(원자적 load 1회)만 추가
- `DocEntry` += `version: i64`, `Subscription` += `version`(로그 필드 겸 테스트 관측점, `dead_code` 회피)
- `RESTORE_BUDGET = 5s`로 `get_or_try_init`을 감싼다 — single-flight 대기의 호출자별 상한
- ⚠️ **복원 실패한 슬롯을 `docs.remove()` 하지 않는다** — `Arc<DocSlot>` 클론을 쥔 동시 opener가
  고아 슬롯을 초기화하는 사이 다른 opener가 새 슬롯을 넣으면 **한 docId에 Doc 2개** = 막으려던
  fork 그 자체. 슬롯은 남기고 다음 open에서 자연 치유 → `MAX_DOCUMENTS`·`len()` 주석에 반영
- **동승**: `benches/convergence.rs`에 `registry_apply` 그룹 신설(별도 커밋). 현재 벤치는 raw `yrs`만
  돌려 `DocRegistry::apply_v1` 회귀를 **볼 수 없다** — 가드레일 5가 이 트랙에 대해 공회전 중이다.
  C5의 핫패스 변경 **전에 main에 baseline이 있어야** `--baseline main` 비교가 성립한다

### C4 — 복원 배선

```
build.rs             compile_protos에 "proto/doc/doc.proto" + rerun-if-changed
src/lib.rs           pub mod doc { tonic::include_proto!("doc"); } + pub mod persistence;
.github/ci.yml:16    stale 주석 정정(bump 불요)
src/persistence.rs   ← 신규. tonic이 사는 유일한 곳(어댑터)
```

- **채널 = `Endpoint::connect_lazy`**(eager 아님): ① doc-service가 죽어 있어도 엔진이 부팅돼야
  한다(eager면 기동 순서 의존) ② 장애가 호출당 `Unavailable`로 드러나 fail-closed 분류와 맞물린다
  ③ 반대편(doc-service의 `EngineClient`)도 lazy라 대칭
- 상수: `CONNECT_TIMEOUT=2s` · `RPC_TIMEOUT=3s` · `MAX_MESSAGE_BYTES=4MiB`(doc-service 인바운드
  한도와 명시 정합) · keepalive 30s/10s. **`Request::set_timeout`도 함께** — `Endpoint::timeout`은
  클라 측만 끊고 `grpc-timeout` 헤더를 안 보내 Java 쪽 JDBC 트랜잭션이 고아로 남는다
- **`MetadataInjector`(신규)** = `service::MetadataExtractor`의 역방향. 게이트웨이 → 엔진 →
  doc-service 3-hop을 한 trace로(가드레일 4).
  ⚠️ **호출부 배선 주의**: `registry.open()`이 지금 `crdt.sync` span **밖**에서 호출된다(span은
  `tokio::spawn(...).instrument()`에만 붙음) → 복원 RPC에 traceparent가 안 실린다.
  `registry.open(&doc_id).instrument(span.clone()).await`로 고친다. `span.enter()` 가드를
  `.await` 너머로 들고 가는 방식은 **금지**(전형적 tracing 함정)
- **fail-closed 매핑**: `service.rs`의 `map_err`가 지금 모든 에러를 `resource_exhausted`로 접는다.
  명시 match로 분리 — `CapExceeded`→`resource_exhausted` · `RestoreFailed`→`unavailable` ·
  나머지는 도달 불가라 `internal`(조용한 오분류 대신 드러낸다). 클라 메시지는 분류만(P4)
- **손상된 저장 블롭도 fail-closed** — 디코드 실패 시 빈 Doc로 열면 첫 저장이 살아있는 행을 덮는다
- **env 스위치 = `DOC_SERVICE_ADDR` 하나.** 미설정 → `NoopSnapshotStore`(현 동작과 동일),
  설정 → `DocServiceStore`. "enabled인데 주소 없음"이라는 불가능 상태를 표현 불가로 만든다.
  기동 로그에 활성/비활성 명시. **C4·C6 내내 기본값은 미설정** → 기존 테스트·`make run`·E2E가
  무변경으로 돌고 Phase 6에서 켠다

### C5 — dirty 회계 (핫패스 훅)

`apply_v1`의 **기존 락 안**, 정수 증가 1줄. 새 락 없음, **시계 호출도 없음**:

```rust
entry.merges_since_save = entry.merges_since_save.saturating_add(1);
```

> **T를 `Instant` 델타가 아니라 "연속 유휴 tick 수"로 표현한다.** ① 핫패스 비용이
> `Instant::now()`에서 정수 덧셈으로 떨어지고 ② `DocEntry`에 시계가 안 들어가니 `Clock` 트레이트
> 주입 자체가 불필요해지고 ③ **디바운스 테스트가 `sweep_once()`를 10번 부르는 것으로 끝난다** —
> `tokio::time::pause`도 sleep도 페이크 시계도 없다. 주입 가능한 시계보다 강한 결정론.
> 대가: `interval`을 **`MissedTickBehavior::Delay`**로 설정해야 한다 — 기본 `Burst`는 스톨 후
> 따라잡기 버스트로 모든 doc를 거짓 "유휴" 판정시킨다.

```rust
pub struct SavePolicy { pub max_merges: u64, pub idle_ticks: u32, pub force: bool }
pub struct PendingSave { pub doc_id: DocId, pub blob: Vec<u8>, pub version: i64, merges: u64 }
pub enum SaveOutcome { Committed, Retry, Disable(&'static str) }

pub fn collect_due_saves(&self, policy: SavePolicy) -> Vec<PendingSave>;  // `.await` 없음
pub fn settle_save(&self, doc_id: &DocId, saved: &PendingSave, outcome: SaveOutcome);
```

`DocEntry` 추가: `merges_since_save`·`seen_by_sweeper`·`idle_ticks`·`save_in_flight`·
`backoff_ticks`·`consecutive_failures`·`persistence: Active|Disabled`.

- **`try_lock`만** — 실패 = 그 doc가 지금 머지 중 → 이번 tick 건너뜀(유휴 판정도 진행되지 않아
  "편집 중인데 유휴"로 오판하지 않는다). 락 역전이 블로킹 자체가 불가능해진다
- **version 규칙**: collect 시 `PendingSave.version = version + 1`(엔트리 불변) → `Committed`에서만
  반영. `Retry`는 같은 후보 번호 재사용(버전 구멍 없음). `Committed` 시
  `merges_since_save -= PendingSave.merges` → **왕복 중 들어온 편집은 dirty로 남는다**
- **`MAX_SNAPSHOT_BYTES = 4MiB − 1KiB`** — doc-service가 어차피 끊을 크기를 보내기 전에 판정.
  초과 = Disabled + ERROR. 근본 해소(증분 저장·GC)는 M3
- `SaveSnapshotResponse.version` ≠ 보낸 값이면 WARN — doc-service가 조용히 버전 권위가 되는
  계약 드리프트(ADR-0013 §5가 지목한 위험)의 최저비용 탐지기

### C6 — 스위퍼

```rust
const SWEEP_INTERVAL: Duration = Duration::from_secs(1);
const SAVE_IDLE_TICKS: u32 = 10;      // T=10초 (ADR-0013)
const SAVE_MAX_MERGES: u64 = 100;     // N=100 (ADR-0013)
const MAX_INFLIGHT_SAVES: usize = 8;  // doc-service Hikari 기본 10 아래로 여유
const MAX_BACKOFF_TICKS: u32 = 60;
const SHUTDOWN_FLUSH_BUDGET: Duration = Duration::from_secs(10);
```

**실패 분류** (`persistence::classify(&Status)` → 포트 3분류 → `SaveOutcome`):

| `tonic::Code` | 결과 | 왜 |
|---|---|---|
| `Unavailable`·`DeadlineExceeded`·`Cancelled`·`ResourceExhausted`·`Aborted`·`Internal`·`Unknown`·`DataLoss` | **Retry** | 블롭을 매 시도 재인코딩하므로 재시도가 사실상 무료 |
| `NotFound` | **Disable**("page row absent") | FK 위반 → `PAGE_NOT_FOUND`. 영구 |
| `InvalidArgument` | **Disable**("doc-id is not a uuid") | `parseUuidOrFail`. 구조적으로 영구 |
| `PermissionDenied`·`Unauthenticated`·`Unimplemented`·`FailedPrecondition` 등 | **Disable + ERROR** | M5 mTLS 오설정 / proto 스큐 = 시끄러워야 할 신호 |

백오프 = **tick 카운트**: `min(2^failures, 60) + hash(doc_id) % 4`. 새 dep 없고(`rand` 불요)
sleep 없고, 지터가 있어 500개 doc가 동시에 재시도하지 않으며, 테스트가 **정확한 tick 인덱스를
단언**할 수 있다.

⚠️ **`main.rs` 종료 순서**: `serve_with_shutdown`이 **반환한 뒤** flush한다 — 그 시점이 "세션이
모두 끝나 더 이상 머지가 없는" 순간이라 "마지막 상태"가 진짜 마지막이다. 종료 신호를 shutdown
future 안에서 보내면 flush와 잔여 머지가 레이스한다.

### C7 — backend 하드닝 3건

1. **blob 크기 무검증** — `SaveSnapshot`이 `doc_id` UUID 형식만 본다(`DocServiceImpl.java:67-83`).
   4MiB gRPC 한도가 유일한 방어. `SnapshotService.save` 진입부에 명시 상한 + 도메인 에러(가드레일 8)
2. **FK/PK 위반 오분류** — `catch (DataIntegrityViolationException) → NotFoundException(PAGE_NOT_FOUND)`
   (`SnapshotService.java:35-42`)가 두 위반을 구분 못 한다. 동시 저장의 PK 경합이 "페이지 없음"으로
   둔갑하면 엔진이 그 doc의 영속화를 **영구 비활성**시킨다(C6 분류표) — 조용한 데이터 유실
3. **`WorkspaceService.listMine` 무상한 조회**(이월 finding) — `PageRepository:17`과 대칭으로
   `WorkspaceMemberRepository.findById_UserId`에 `Limit` + `MAX_WORKSPACE_LIST` 상수.
   API 형태 무변경(Pageable 전환은 과잉). 클래스 주석의 "P2 예외" 문구도 함께 제거 — 안 그러면 모순

## 검증

**C3 — 순수 단위(페이크 store, 서버 없음)**
`restore_applies_stored_snapshot` · `restore_of_absent_snapshot_starts_empty` ·
`restore_failure_is_not_cached`(fail→ok 스크립트, `calls == 2` — OnceCell 의미론 고정) ·
**`concurrent_opens_restore_once`**(페이크가 `Notify`에 park, 8개 동시 open → `calls == 1`) ·
`second_opener_never_sees_pre_restore_state`(fork 불변식을 독립 테스트로 — 구조를 바꿔도 잡힌다) ·
`apply_v1_on_uninitialized_slot_is_unknown_doc` · `cap_is_checked_before_the_store_call`(`calls == 0`) ·
`corrupt_stored_snapshot_fails_closed`

**C4 — 실 tonic 서버 양단** (`tests/support/mod.rs` 기록형 페이크 `DocService`,
`tests/sync_role.rs:29-50` 하네스 그대로. sleep 없이 `RECV_TIMEOUT=5s` 상한)
`restored_doc_is_delivered_to_the_first_client`(**M2 DoD 와이어 레벨 증명**) ·
`load_failure_closes_the_stream_with_unavailable`(+ 메시지 내부 누출 없음, P4).
traceparent 주입은 **단위 테스트로** — OTel 레이어가 없으면 `Span::current().context()`가 비어
아무것도 주입되지 않아 통합 단언이 **공허하게 통과**한다. `with_default` + 로컬 `SdkTracerProvider`로.

**C5 — 순수 동기 단위(페이크·async 불요)**
`n_threshold_triggers_at_100_merges` · `idle_threshold_triggers_on_the_10th_quiet_tick`(9회 empty,
10회째 1건) · `a_merge_between_ticks_resets_idle` · `in_flight_doc_is_not_dispatched_twice` ·
`backoff_skips_ticks_then_retries` · `oversized_blob_disables_persistence` ·
`committed_save_clears_only_saved_merges`(5에서 collect → 3 머지 추가 → commit → `== 3`) ·
`retry_keeps_version_and_dirty` · `force_collects_every_dirty_doc` ·
`contended_doc_is_skipped`(락을 쥔 채 `spawn_blocking`+timeout — `lock()`으로 회귀하면 CI가 매달리는
대신 깔끔히 실패)

**C6** — `transient_failure_is_retried_after_backoff_ticks`(정확한 tick 인덱스) ·
`permanent_failure_disables_the_doc` · `inflight_cap_is_respected` · `flush_all_forces_every_dirty_doc`.
통합(`tests/persistence_save.rs`, **tick 루프를 돌리지 않고 `sweep_once()`를 직접 호출** → 1초 대기 0):
`snapshot_is_saved_after_threshold_updates` · `save_is_retried_after_unavailable`(3회 기록, 최종
`version == 1`) · `savesnapshot_carries_traceparent` ·
**`restart_restores_the_last_saved_snapshot`**(레지스트리 A가 페이크에 저장 → drop → 같은 페이크로
B 구성 → `full_state_v1` 일치. **M2 DoD를 인프로세스로, CI 안에서**)

```bash
# 매 engine PR
make proto-sync && cargo build && cargo test --all-targets \
  && cargo clippy --all-targets -- -D warnings && cargo fmt --check
# C5는 추가 (가드레일 5 — 핫패스 변경)
make bench-compare        # main baseline 대비. baseline은 C3에서 main에 심는다

# 크래프트 표준 6종 [B] 체크리스트 = 반드시 rust-expert **에이전트로**
# (룰이 레포 경계를 안 넘는다 — 2026-07-28 실측, dev-logs/2026-07-28-rules-do-not-cross-repo.md)
```

**최종 실기동 검증**(C6 머지 후, `DOC_SERVICE_ADDR` 켜고 4프로세스 = postgres·doc-service·gateway·engine):
편집 → 10초 유휴 → `select page_id, version, octet_length(snapshot) from page_snapshots;` 행 확인 →
엔진 재시작 → 재접속 → 내용 복원 확인. **= M2 DoD.**

## 재개 지점 (Resume)

```
마지막 완료 = C3 (engine PR #13, CI 3/3 green). 브랜치 feature/m2-phase34-snapshot-restore
다음        = PR #13 머지 승인 → C4(PR1b: build.rs에 doc.proto 추가 · persistence 모듈 ·
              MetadataInjector · DOC_SERVICE_ADDR · 페이크 DocService 통합 테스트)
주의        = ① 실행 순서가 plan 번호와 반대다(복원 C3·C4 먼저, 저장 C5·C6 나중, D1)
              ② proto 태그 bump·PROTO_REF 변경 **불요** — proto-v0.2.0에 이미 다 있다
              ③ 벤치 baseline(registry_apply)은 C3에서 심었다 → C5에서 bench-compare 성립.
                 단 **main에 머지된 뒤에야** `--baseline main`이 의미를 갖는다
              ④ DOC_SERVICE_ADDR 기본 미설정 유지 — Phase 6에서 켠다
              ⑤ 서비스 레포는 push·PR 생성·머지 **각각** 승인
              ⑥ C4 어댑터는 반드시 `StoredSnapshot::from_wire`를 통과시킬 것 —
                 (version>0, blob=[]) 모순 쌍을 거르는 유일한 관문이다(C3 게이트 M1)
```

## 범위 밖

- **Phase 5(outbox)·Phase 6(E2E 통합)** — 이 plan 다음. 부모 = [m2-persistence-session](2026-06-30-m2-persistence-session.md)
- **version 단조성 가드**(backend UPSERT `WHERE version < :new`) — 복원-우선(D1)으로 **이제 안전하게
  넣을 수 있게 됐다**는 사실만 기록. 이번 미포함(사용자 선택), M3 캡 정량화 트랙
- **멀티인스턴스 중복 저장** — 단일 인스턴스 가정. consistent-hash = M3
- **무손실 복원**(Redis 버퍼) — 보장 경계는 최종 스냅샷, in-flight 유실 허용(ADR-0013 §4). M5
- **엔진 직접 gRPC 우회 차단**(mTLS STRICT·NetworkPolicy) — M5. 엔진↔doc-service는 여전히 plaintext·무인증
- **증분 저장·GC** — 4MiB 초과 문서의 근본 해소. M3
- **문서 eviction** — 영속화가 선행 조건이었으나 이번엔 상한(`MAX_DOCUMENTS`)만 유지
- **proto 변경·태그 bump** — 불요(§Context 실측)
