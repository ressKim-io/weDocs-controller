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
- [x] **C3** engine PR1a `feat(engine): 스냅샷 복원-우선 open + SnapshotStore 포트` — [PR #13](https://github.com/ressKim-io/weDocs-crdt-engine/pull/13) **머지** `2ab925e`.
      커밋 `b943959`(포트+슬롯) · `37c9b77`(벤치) · `4d93c91`·`61a8399`(게이트 반영).
      실제 736줄(프로덕션 ~405 / 테스트 ~330) — 추정 355줄을 넘겼다. 초과분은 대부분 테스트 10건과 근거 주석
- [x] **C3.5** engine `refactor: 모듈 구조 + 에러 wire 매핑 + 설정 일원화` ([ADR-0022](../adr/0022-module-structure-rust.md))
      — [PR #14](https://github.com/ressKim-io/weDocs-crdt-engine/pull/14) **머지** `28e1b9c`.
      `engine.rs`→`doc.rs`+`snapshot/`, `service.rs`→`sync/{mod,session,metadata,status}`, `config.rs` 신설.
      동작 무변경(기존 40 테스트 통과, 벤치 166µs 동일)
- [x] **C4** engine PR1b `feat(persistence): doc-service 복원 배선 + fail-closed`
      — [PR #15](https://github.com/ressKim-io/weDocs-crdt-engine/pull/15) **머지** `1a14f13` (+1,112/-7).
      커밋 `cda705e`(codegen) · `5a66154`(config) · `0e2e3a4`(어댑터) · `62cb8a2`(게이트 반영).
      추정 380줄을 크게 넘겼다 — 초과분은 대부분 통합 테스트 2파일(페이크 DocService + 실경로
      trace 검증)과 근거 주석. 회고 = [dev-log](../dev-logs/2026-07-30-m2-phase4-doc-service-adapter.md)
- [ ] **C5** engine PR2a `feat(engine): 스냅샷 dirty 회계 + 저장 대상 수집` — **코드·게이트 완료,
      PR 미착수**(2026-07-30). 브랜치 `feat/m2-phase3-save-accounting`, 커밋 6건:
      `a20beae`(bench Makefile 수정) · `b861673`(newtype) · `30bcdcc`(회계) ·
      `c4885a2`(게이트 1차) · `9e5c0f5`(게이트 2차) · `e2b25a3`(게이트 3차).
      lib 테스트 43 → 62. 추정 ~280줄을 크게 넘겼다(게이트 반영분 + 근거 주석).
      **게이트 3라운드 = 통과**(Critical 0 · Major 0).
      - ⚠️ **2라운드가 실제 버그를 잡았다** — 1차에서 무상한 배치를
        고치며 넣은 `max_batch` 절단이 **특정 doc를 영구히 굶겼다**(슬롯 순회 순서가 안정적 +
        `break`가 백오프 감소·워치독 tick까지 막음). 8 doc·상한 2로 20 tick → 같은 2개만 저장.
        회전 커서(`sweep_cursor`)로 해소. **수정이 새 결함을 낳은 사례라, 게이트는 반영 후
        반드시 재실행한다.** 공허한 테스트 1건(`stale_settle_is_ignored`)도 2라운드가 뮤테이션
        으로 잡았다 — 신원 가드를 통째로 무력화해도 통과하고 있었다
      - ✅ **C4 게이트 이월 M5(b) 소거** — `StoredSnapshot::Present(PresentSnapshot)` newtype +
        private 필드. 핵심은 **형제 모듈**(`snapshot/stored.rs`) 배치다: private 필드는 정의
        모듈 *과 그 하위*에서 보이므로 `snapshot/mod.rs`에 두면 자식인 어댑터가 여전히 우회
        조립할 수 있다. 형제로 내려야 컴파일러가 막는다(에이전트가 `E0451`로 실증)
      - ✅ **가드레일 5** — `registry_apply` 벤치 no-change(§검증). 단 `make bench-compare`가
        **한 번도 동작한 적 없었다**는 것을 이 단계에서 발견(§C5 벤치 도구)
      - ⚠️ **`make bench-baseline`/`bench-compare`는 `--bench convergence`가 없으면 죽는다** —
        `cargo bench`가 libtest 하네스까지 벤치 타깃으로 돌리기 때문. 재발 방지로
        `make bench-smoke`(`--test`, ~10초)를 CI 스텝에 넣었다
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

> ⚠️ **이 절은 C3.5(ADR-0022) 이후 구조로 갱신됐다.** 옛 버전은 `src/persistence.rs`·`service.rs`를
> 지시했으나 그 파일들은 더 이상 없다.

```
build.rs                    compile_protos에 "proto/doc/doc.proto" + rerun-if-changed
src/lib.rs                  pub mod doc_proto { tonic::include_proto!("doc"); }   ← 이름 주의(m1)
.github/workflows/ci.yml:16 stale 주석 정정(bump 불요)
src/snapshot/doc_service.rs ← 신규. tonic이 사는 유일한 곳(포트의 형제 어댑터)
src/config.rs               doc_service 필드 추가 (env는 여기서만 읽는다)
src/sync/mod.rs             CrdtEngineService::with_store — main이 포트를 주입하는 유일한 구멍
```

#### 착수 실측 — 이 절의 지시 3건 정정 (2026-07-29)

C4 절은 C3.5(ADR-0022) **이전**에 쓰였고, 위 경로 갱신 때 아래 3건이 함께 갱신되지 않았다.

| # | 원문 지시 | 실측 · 대체 |
|---|---|---|
| **m1** | `pub mod doc { tonic::include_proto!("doc"); }` | **불가 — 이름 충돌.** `src/doc.rs`가 이미 `pub mod doc`(도메인 `DocRegistry`)다. proto 패키지명과 도메인 관심사명이 같은 단어를 쓴다. → **`pub mod doc_proto`**. `include_proto!`의 인자는 생성 파일명이라 모듈명은 자유롭고, 생성 코드의 `super::common` 참조도 크레이트 루트 기준이라 그대로 해석된다(`crdt` 모듈과 동일 조건) |
| **m2** | 어댑터를 `mod doc_service;`로 **비공개** | **불가 — `main.rs`는 별도 바이너리 크레이트**라 `pub(crate)`조차 닿지 않는다. → **`pub mod doc_service;`** 로 두되 `snapshot/mod.rs`는 어댑터 타입을 **`use`하지 않는다**(재수출 0). 원 목적("포트 파일은 tonic을 모른다")은 그대로 성립한다 — 지켜야 할 것은 *가시성*이 아니라 *의존 방향*이다 |
| **m3** | "`config.rs`에 `doc_service_addr` 필드" (타입 미지정) | 주소가 `SocketAddr`가 **아니다** — gRPC 엔드포인트라 스킴이 필요하다(`http://doc-service:50052`). → `Option<Endpoint>`로 쥔다. `Endpoint: Clone + Debug`(실측 tonic 0.14 `endpoint.rs:22,704`)라 `Config`의 derive가 유지되고, 파싱을 기동으로 끌어올려 **오타 주소가 첫 RPC가 아니라 부팅에서** 드러난다. 스킴 부재도 여기서 거절 — `Endpoint::from_shared`는 `"host:port"`를 스킴 `host`로 읽어 통과시키고 **connect 시점에야** 깨진다 |

> m1·m2는 "구조 리팩토링(C3.5)이 그 뒤 단계의 지시문을 stale하게 만든다"의 두 번째 사례다.
> 첫 번째가 이 절 머리의 ⚠️(`persistence.rs`·`service.rs` 경로)였고, 그때 **경로만** 고치고
> 코드 스니펫은 두었다. 다음 단계 지시문은 경로·이름·가시성을 **함께** 재검한다.

**C3·C3.5에서 이미 끝난 것 — C4에서 다시 하지 않는다:**
- fail-closed `Status` 매핑 → `sync/status.rs`의 `WireFault`가 소유(문구 추가도 거기서만)
- `registry.open()`의 span 배선 → `.instrument(span.clone()).await` 적용 완료
- `SnapshotStore` 포트·`StoredSnapshot`·에러 3분류 → `snapshot/mod.rs`에 존재

**C4에서 새로 할 것:**
- **`StoredSnapshot::from_wire`를 반드시 통과시킨다** — `(version>0, blob=[])` 모순 쌍을 거르는
  유일한 관문이다(C3 게이트 M1이 잡은 데이터 유실 경로). 어댑터가 proto 응답을 직접
  `StoredSnapshot`으로 조립하면 그 가드가 무력화된다
- **채널 = `Endpoint::connect_lazy`**(eager 아님): ① doc-service가 죽어 있어도 엔진이 부팅돼야
  한다(eager면 기동 순서 의존) ② 장애가 호출당 `Unavailable`로 드러나 재시도 분류와 맞물린다
  ③ 반대편(doc-service의 `EngineClient`)도 lazy라 대칭
- 상수: `CONNECT_TIMEOUT=2s` · `RPC_TIMEOUT=3s` · `MAX_MESSAGE_BYTES=4MiB`(doc-service 인바운드
  한도와 명시 정합) · keepalive 30s/10s. **`Request::set_timeout`도 함께** — `Endpoint::timeout`은
  클라 측만 끊고 `grpc-timeout` 헤더를 안 보내 Java 쪽 JDBC 트랜잭션이 고아로 남는다
- **`MetadataInjector`** = `sync/metadata.rs`의 `MetadataExtractor` 역방향. 게이트웨이 → 엔진 →
  doc-service 3-hop을 한 trace로(가드레일 4). 어댑터가 outbound 메타에 주입한다.
  `span.enter()` 가드를 `.await` 너머로 들고 가는 방식은 **금지**(전형적 tracing 함정)
- **`classify(&Status) -> SnapshotStoreError`** — tonic code를 포트 3분류로 접는 유일한 지점.
  분류표는 C6 절 참조(저장 경로와 공용)
- **env 스위치 = `DOC_SERVICE_ADDR` 하나.** 미설정 → `NoopSnapshotStore`(현 동작과 동일),
  설정 → `DocServiceStore`. "enabled인데 주소 없음"을 표현 불가로 만든다. 기동 로그에 활성/비활성
  명시. **C4·C6 내내 기본값은 미설정** → 기존 테스트·`make run`·E2E가 무변경으로 돌고 Phase 6에서 켠다.
  ⚠️ `ConfigError`는 이미 변수 이름을 담는 형태다(C3.5 m2) — 새 주소도 그 경로로 파싱한다
- **어댑터를 `snapshot/mod.rs`에서 재수출하지 않는다**(`mod doc_service;` 비공개) — 그래야
  "포트 파일은 tonic을 모른다"가 유지된다(ADR-0022)

파일: `build.rs` · `lib.rs` · `.github/workflows/ci.yml` · `snapshot/doc_service.rs`(신규) ·
`snapshot/mod.rs`(mod 선언) · `config.rs` · `main.rs` · `tests/support/mod.rs`(신규, 페이크
DocService) · `tests/persistence_restore.rs`(신규). **~380줄**

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

#### 실제 착지한 API ✅ 2026-07-30 (C6는 **이 형태**를 쓴다 — 아래 원문 스케치와 다르다)

```rust
// snapshot/save.rs — 값 타입은 포트의 형제 모듈(어댑터가 조립 못 하게)
pub enum SaveTrigger { Debounced { max_merges: u64, idle_ticks: u32 }, Flush }
pub struct SavePolicy { pub trigger: SaveTrigger, pub max_batch: NonZeroUsize }
pub struct PendingSave { /* 전 필드 private */ }   // doc_id()·blob()·version() 접근자
pub enum SaveOutcome { Committed, Retry, Disable(SnapshotStoreError) }
pub const MAX_SNAPSHOT_BYTES / MAX_BACKOFF_TICKS / MAX_IN_FLIGHT_TICKS;

// doc.rs
pub fn collect_due_saves(&self, policy: SavePolicy) -> Vec<PendingSave>;  // `.await` 없음
pub fn settle_save(&self, saved: &PendingSave, outcome: SaveOutcome);     // doc_id 파라미터 없음
```

원문 스케치와 달라진 4곳과 이유(전부 게이트 반영):
1. **`force: bool` → `SaveTrigger` enum** — flush 정책이 `max_merges: u64::MAX`로 임계값을
   중화해야 했다 = 의미 없는 조합이 표현 가능했다(P4).
2. **`max_batch` 신설(필수)** — 후보는 인코딩된 블롭을 소유하므로 상한이 없으면 최악
   10,000 × 4MiB가 한 `Vec`에 산다. ⚠️ **스위퍼가 `.take(N)`으로 자르면 안 된다** — 잘린
   후보는 이미 `save_in_flight`가 찍힌 채 버려져 settle을 못 받는다. 자르기는 수집 안쪽.
3. **`Disable(SnapshotStoreError)`** — `&'static str`이면 `classify`가 만든 rpc·code·메시지가
   소멸해, 유일한 로깅 지점(`settle_save`)에 사유가 남지 않는다(P4).
4. **`settle_save`에서 `doc_id` 제거** — `saved.doc_id()`가 이미 있어 불일치 쌍이 가능했다.

`DocEntry` 추가: `merges_since_save`·`idle_ticks`·`save_in_flight`·`in_flight_ticks`·
`attempt`·`backoff_ticks`·`consecutive_failures`·`persistence: Active|Disabled`.
(`seen_by_sweeper`는 **불필요**했다 — 유휴 리셋을 핫패스에서 하니 파생값이 아니게 됐다.)

**settle 계약은 코드가 강제한다**(주석 아님):
- `attempt` 일련번호 대조 → 중복·지각 settle 무시(dirty 이중 차감·버전 역행 차단)
- `MAX_IN_FLIGHT_TICKS`(30) 워치독 → settle이 **영영 안 와도** 자가 치유.
  C6의 저장 태스크가 패닉·취소·drop되면 그 doc의 저장이 프로세스 수명 내내 멎던 경로

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
const SHUTDOWN_FLUSH_BUDGET: Duration = Duration::from_secs(10);
// MAX_BACKOFF_TICKS·MAX_SNAPSHOT_BYTES·MAX_IN_FLIGHT_TICKS는 C5가 snapshot/save.rs에 이미 넣었다
```

**C5가 넘긴 전제 5가지**(C6가 지켜야 한다):
1. `SavePolicy { trigger: SaveTrigger::Debounced { max_merges: SAVE_MAX_MERGES,
   idle_ticks: SAVE_IDLE_TICKS }, max_batch: MAX_INFLIGHT_SAVES }` — **`max_batch`를
   반드시 채운다**(`NonZeroUsize`). 종료 flush는 `SaveTrigger::Flush` + 같은 `max_batch`로,
   `SHUTDOWN_FLUSH_BUDGET` 안에서 **여러 tick 루프**를 돌아 남은 dirty를 비운다
   (한 번 호출로 전부 나오지 않는다 — 상한에서 잘린다).
   ⚠️ **`max_batch`에는 제약이 셋**이다: ① 메모리 `max_batch × 4MiB`(8 → 32MiB, 64 → 256MiB)
   ② 워치독 부등식(아래 5번) — ②가 대개 먼저 깨진다 ③ **하한(처리량)**: `max_batch = 8` +
   1초 tick = **저장 8건/초 천장**이다. T=10초 디바운스에서 동시 활성 doc가 80을 넘으면
   상한이 상시 포화돼 doc별 실제 저장 간격이 `활성doc수/8`초로 늘어난다(N·T 정책이 사실상
   무력화되고 WARN이 매 tick 발화). 해법은 `max_batch`를 그냥 키우는 게 아니라 **전제 5의
   디스패치 timeout을 먼저 넣어 워치독 부등식에서 풀려나는 것** — 그 뒤엔 메모리만 보면 된다.
2. `interval`은 **`MissedTickBehavior::Delay`** — 기본 `Burst`는 스톨 후 따라잡기
   버스트로 모든 doc를 거짓 "유휴"로 판정시킨다(C5의 tick 기반 유휴 표현의 대가).
3. 후보 1건당 `settle_save`를 **정확히 한 번** 부른다. 빠뜨려도 워치독이 30 tick 뒤
   자가 치유하지만 그 사이 저장이 멎고 WARN이 남는다 — 정상 경로로 취급하지 않는다.
4. `SaveSnapshotResponse.version` ≠ 보낸 값이면 WARN(계약 드리프트 탐지, ADR-0013 §5).
   C5는 응답을 볼 수 없어 **C6가 디스패치 지점에서** 비교한다.
5. **워치독 오탐을 구조적으로 막는다**(C5 게이트 2차 M1). 인플라이트 지속시간 =
   *세마포어 대기 + RPC*라, 배치가 크면 꼬리 후보가 `MAX_IN_FLIGHT_TICKS`(30)를 넘겨
   **살아 있는 RPC가 유실로 오판**된다. 그러면 같은 version을 실은 저장 2개가 떠
   doc-service UPSERT가 최신 블롭을 옛 것으로 덮고, 그 뒤 dirty도 빠져 유실이 흔적조차
   남기지 않는다. C6가 할 일 둘:
   - `const _: () = assert!(max_batch.div_ceil(MAX_INFLIGHT_SAVES) * RPC_TIMEOUT_TICKS
     < MAX_IN_FLIGHT_TICKS);`
   - 디스패치 **전체(세마포어 획득 포함)**를 워치독보다 짧은 `tokio::time::timeout`으로 감싸
     초과 시 반드시 `Retry`로 settle → "settle이 아예 안 온다"가 태스크 소멸에만 남는다
6. `PendingSave::blob()`은 `&[u8]`뿐이다. `SaveSnapshotRequest`를 만들며 `.to_vec()`하면
   **저장마다 최대 4MiB 복사**다 — 필요하면 `take_blob(&mut self) -> Vec<u8>`(`mem::take`,
   회계 필드는 보존)을 C6에서 추가한다. C5에 미리 넣지 않은 이유는 호출자가 없어 어떤
   테스트도 그 경로를 검증하지 못하기 때문.

**C5에서 이월된 게이트 항목 2건**:
- **경합 벤치**(게이트 M5) — `due_save`가 문서별 락을 쥔 채 전체 상태를 인코딩하므로 그 doc의
  머지가 그동안 멈춘다(4MiB면 ms 단위). `bench-compare`는 스위퍼를 안 돌려 이 비용을
  **측정하지 못한다**.
  > 게이트 2차 m9는 "지금 넣어야 C6가 baseline을 갖는다"며 이월에 반대했다(C3가 C5를 위해
  > `registry_apply`를 심은 것과 같은 논리). **이월을 유지한 이유**: C5에는 스위퍼가 없어
  > 벤치가 잴 수 있는 것은 `collect_due_saves`를 타이트 루프로 도는 **합성 간섭**뿐이고,
  > 그 baseline은 1초 tick으로 도는 실제 스위퍼와 비교 가능하지 않다. 그리고 C6에서 이
  > 벤치가 답해야 할 질문은 회귀 비교가 아니라 **"스위퍼가 도는 동안 머지 지연이 허용
  > 범위인가"**라는 절대값 판정이라, 대조군이 main baseline이 아니라 **같은 PR 안의
  > '스위퍼 off'**다 — C6 안에서 self-contained하게 얻어진다. (게이트 3차에서 이 논거를
  > 받아들여 지적을 철회했다.)
  >
  > ⚠️ **단, C6는 수용 기준을 수치로 먼저 박아야 한다** — 예: "스위퍼 on의 `registry_apply`
  > p99가 off 대비 +X% 이내". 지금처럼 "허용 범위"로 두면 측정은 하되 판정이 없는 상태가 된다.
- **`SweepStats`**(게이트 m13) — in-flight·disabled·contended로 건너뛴 doc가 반환값에 안 남는다.
  절단만 WARN으로 관측된다(미방문 수까지). 소비자(스위퍼 로그·메트릭)가 생기는 C6에서
  반환 타입을 넓힌다.

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

**C5 벤치 도구 — `make bench-compare`가 그동안 공회전이었다** ✅ 발견·수정 2026-07-30

`cargo bench -- --save-baseline main`은 lib·bin·tests의 **libtest 하네스까지** 벤치 타깃으로
돌리는데 그 하네스들은 criterion 플래그를 모른다 → `error: Unrecognized option: 'save-baseline'`.
인자 없는 `make bench`만 우연히 통과해 왔던 탓에, 가드레일 5의 **회귀 비교 수단이 한 번도
동작한 적이 없었다**. 처방 = 세 타깃 전부 `--bench convergence` 지정 + `make bench-smoke`
(`-- --test`, ~10초)를 CI에. "게이트를 붙여뒀다"와 "게이트가 돈다"는 다르다 —
[2026-07-29 frontend `npm-audit`](../dev-logs/2026-07-29-m2-phase2c-frontend-auth.md)와 같은 계열.

**C5 실측 결과**(criterion, 200 samples · 10s window, 조용한 상태의 A/B 쌍):

| registry_apply | main | C5 | 변화 | 판정 |
|---|---|---|---|---|
| `sequential_typing_256` | 289.79 µs | 291.82 µs | +0.59% (p=0.17) | No change detected |
| `large_paste_10k` | 10.321 µs | 10.538 µs | +1.36% (p=0.27) | No change detected |

두 구간 모두 신뢰구간이 0을 포함한다. ⚠️ **측정 위생**: 로드가 걸린 상태에서는 같은 코드의
A/B가 −4%~+7%로 흔들렸고(손대지 않은 raw yrs 그룹도 +33%), 한 쌍 안에서 C5가 main보다
*빨라* 보이기도 했다. 신뢰구간 폭(±0.15%)이 좁은 쌍만 유효한 측정으로 채택했다.

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
마지막 완료 = **C5 코드 + 크래프트 게이트 반영**(2026-07-30). engine 브랜치
              `feat/m2-phase3-save-accounting`, 커밋 4건(a20beae·b861673·30bcdcc·c4885a2).
              **로컬만 — push·PR 둘 다 미착수**(건별 승인 필요)
다음        = ① C5 push + PR 생성·머지(승인 후) → ② **C6**(PR2b: 스위퍼 + graceful flush)
              C7(backend 하드닝)은 C5와 무관하게 지금도 병렬 가능

C6 착수 시 반드시 = §C5 "실제 착지한 API"와 §C6 "C5가 넘긴 전제 4가지"를 먼저 읽어라.
              C5의 API가 plan 원문 스케치와 **다르다**(SaveTrigger enum · max_batch 필수 ·
              settle_save에 doc_id 없음 · Disable이 에러를 싣는다). 원문대로 쓰면 컴파일 실패한다.
              이건 C4에서 이미 한 번 겪은 함정이다(구조 변경이 뒤 단계 지시문을 stale하게 만든다).

주의        = ① 실행 순서가 plan 번호와 반대다(복원 C3·C4 먼저, 저장 C5·C6 나중, D1)
              ② proto 태그 bump·PROTO_REF 변경 **불요** — proto-v0.2.0에 이미 다 있다
              ③ 벤치: `make bench-baseline`/`bench-compare`는 C5 전까지 **동작하지 않았다**
                 (`--bench convergence` 누락). 지금은 고쳐졌고 CI가 `bench-smoke`로 경로를 지킨다.
                 `--baseline main`은 **main에 머지된 뒤에야** 의미를 갖는다
              ④ DOC_SERVICE_ADDR 기본 미설정 유지 — Phase 6에서 켠다
              ⑤ 서비스 레포는 push·PR 생성·머지 **각각** 승인
              ⑥ 저장 경로도 `PendingSave`/`PresentSnapshot`을 **직접 조립할 수 없다**(필드 private).
                 관문은 `from_wire`와 `due_save` 하나씩 — 컴파일러가 강제한다
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
