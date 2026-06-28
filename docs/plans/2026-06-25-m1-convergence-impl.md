---
date: 2026-06-25
slug: m1-convergence-impl
status: in-progress
related:
  - plans/2026-06-25-m1-repo-scaffold.md
  - adr/0010-proto-distribution-buf-git-input.md
  - dev-logs/2026-06-25-m1-repo-scaffold.md
  - dev-logs/2026-06-28-m1-convergence-phase1-3.md
---

# weDocs — M1 본 구현: "두 탭 동시 편집 수렴" 증명

스캐폴드(`2026-06-25-m1-repo-scaffold.md`, done)의 빈 스텁을 채워 **두 브라우저가 같은 문서를
동시 편집하면 동일 상태로 수렴**함을 증명한다. 엔진(Rust yrs) 우선.

> 스코프 확정: **awareness(커서) 연기**(proto bump 회피, M1.5) / **OTel trace M1 포함**(Phase 4 — **thin 2-hop 전파 증명만**, 풀 관측 스택[Collector·샘플링·Grafana]은 **M5**로 명시 연기. 2026-06-28 사용자 결정).

## Context

### A. 검증된 와이어 포맷 — y-protocols/y-websocket (2026-06-25 ✅ verified)

게이트웨이 코덱의 린치핀. 출처: yjs/y-protocols `master`(`src/sync.js`,`PROTOCOL.md`) · yjs/y-websocket `master`(`src/y-websocket.js`).

| 레이어 | 상수 | 프레이밍 |
|---|---|---|
| y-websocket top-level | `messageSync=0` · `messageAwareness=1` · `messageAuth=2` · `messageQueryAwareness=3` | `varUint(type) • payload` |
| y-protocols sync 서브 | `SyncStep1=0`(state vector) · `SyncStep2=1`(diff update) · `Update=2`(update) | `varUint(subtype) • varBuffer(payload)` |
| 클라 접속 시 | y-websocket client는 즉시 `messageSync → SyncStep1(SV)` 송신 | — |

- `varBuffer` = `varUint(len) • bytes` (lib0 `writeVarUint8Array`). 작은 값(0/1/2)은 1바이트 varUint.
- 클라 `readSyncMessage`: type0=SyncStep1→step2로 응답 / type1·2=`Y.applyUpdate`. **type1·2는 클라에서 동작 동일**.

### B. 검증된 yrs 0.27 API (docs.rs 0.27.2, 2026-06-25 ✅ verified) — **전부 v1(Yjs 호환)**

| 용도 | API | 비고 |
|---|---|---|
| 인바운드 update 디코드 | `Update::decode_v1(&[u8]) -> Result<Update, Error>` | 실패 가능 → 에러 처리 필수 |
| 머지 | `TransactionMut::apply_update(Update) -> Result<(), UpdateError>` | **unwrap 금지** |
| SyncStep2 diff | `ReadTxn::encode_state_as_update_v1(&StateVector) -> Vec<u8>` | 전체 스냅샷 = `StateVector::default()` |
| SyncStep1 페이로드 | `ReadTxn::state_vector()` → `StateVector::encode_v1()` / `StateVector::decode_v1(&[u8])` | v1 |
| fan-out 페이로드 | **인바운드 v1 update 바이트 그대로 재전송** | `observe_update_v1` 불필요(yrs 멱등·교환) |

- `Doc` Send: 스캐폴드가 `Arc<Mutex<HashMap<String, Doc>>>`로 컴파일됨 → Send 확인됨(write-time 재확인).
- **v1 고정이 상호운용의 전제** — v2 메서드 사용 시 Yjs 클라가 디코드 불가. 모든 인코드/디코드는 `_v1`.

### C. 핵심 설계 — 게이트웨이=프로토콜 번역기, 엔진=sync 권위

게이트웨이는 Java라 `Y.Doc`이 없어 SyncStep1에 답할 수 없음 → **엔진이 sync 주도**.
게이트웨이는 `y-websocket 와이어 ↔ gRPC 프레임` 1:1 번역만. **fan-out은 엔진의 per-doc broadcast 채널**
(가드레일 5 "엔진이 엔진이다" 부합 — 게이트웨이는 per-doc 세션 그룹핑 불필요).

```
게이트웨이: WS /ws/doc/{room} 접속 → gRPC Sync 스트림 open + 메타데이터 doc-id={room}
엔진(스트림당):
  open               → 메타데이터 doc-id 읽기 → registry.ensure → broadcast 구독(락 안에서, 아래 §D-2)
                     → ServerFrame{state_vector=sv.encode_v1()}        (옵션: 클라 오프라인분 pull용 SyncStep1)
  ClientFrame{sv}    → ServerFrame{update=encode_state_as_update_v1(sv)}  (= SyncStep2, late-join 핵심)
  ClientFrame{update}→ decode_v1 → apply_update(Result 처리) → broadcast.send(원본 v1 바이트)
  broadcast 수신     → ServerFrame{update}                              (= 타 세션 fan-out)
```

매핑(게이트웨이): WS `SyncStep1`→`ClientFrame{state_vector}`; WS `SyncStep2|Update`→`ClientFrame{update}`.
역방향: `ServerFrame{state_vector}`→WS `SyncStep1(0)`; `ServerFrame{update}`→WS **`Update(2)`**(아래 §D-4).

- **proto 변경 불필요** ✅ — 현 `ClientFrame{doc_id,update,state_vector}` / `ServerFrame{update,state_vector}`로
  SyncStep1/2/Update 전부 표현. controller proto bump·새 태그·다운스트림 재생성 없음.

### D. 설계 정밀화 — 정합성 디테일 (정밀 검토에서 도출한 결정)

1. **doc_id는 gRPC 메타데이터로** (proto 주석과 일치). open 시점엔 아직 ClientFrame이 안 와서 엔진이 doc를
   모르는 chicken-egg → 메타데이터 `doc-id`로 open 즉시 해결. `ClientFrame.doc_id`는 첫 프레임 검증용(불일치→reject).
2. **구독-후-스냅샷을 락 안에서**: 신규 스트림은 (락 획득 → broadcast 구독 → SyncStep2용 현재 상태 스냅샷 → 락 해제)
   순서. 구독 전에 스냅샷 뜨면 그 사이 들어온 update를 놓치는 lost-update 윈도가 생김. **락 보유 중 .await 금지**(가드: apply→send 동기).
3. **self-echo 미필터(M1)**: 단일 broadcast라 송신자도 자기 update를 수신 → 클라 applyUpdate 멱등(no-op)이라 무해.
   트래픽 2배는 M1.5 최적화. (필터하려면 per-stream 채널+sender 레지스트리 → M1 과설계.)
4. **ServerFrame{update}는 전부 `Update(2)`로 프레이밍**: proto가 SyncStep2 vs Update를 구분 안 함. 클라에선 둘 다
   applyUpdate로 동일. 단 y-websocket `provider.synced`는 SyncStep2 수신 시만 set → **M1은 'synced' 이벤트 비의존**,
   E2E는 텍스트 동등성 폴링으로 검증. (synced 라이프사이클 = proto 판별자 필요 → M1.5.)
5. **broadcast Lagged → 강제 resync**: 느린 수신자가 bounded 채널에서 `RecvError::Lagged(n)` → update 유실 → divergence.
   → 그 스트림에 전체 상태(`encode_state_as_update_v1(default)`) 재전송으로 재수렴. 채널 cap 예: 256.
6. **WS 단일 writer 불변식**: 모든 WS send는 gRPC 응답 StreamObserver(스트림당 serial 호출)에서만. 인바운드 핸들러는
   gRPC로 forward만(WS로 직접 send 금지) → 동시 send 없음 → `WebSocketSession` 비동기 안전. 위반 시 `ConcurrentWebSocketSessionDecorator`.
7. **awareness/queryAwareness 프레임은 drop**: awareness 연기 상태에서도 클라는 messageAwareness(1)을 보냄.
   게이트웨이는 type 1·3을 인식해 무시(엔진 미전달, 미러링 X). 미인식 type 에러 금지.
8. **Doc 미evict(M1)**: 전 세션 disconnect돼도 registry 유지 → 프로세스 내 재접속 시 SyncStep2로 복원. 프로세스 재시작=유실(영속화는 후속).

### E. 워크플로 제약 (중요)

- **controller**: main 직접 commit·push 허용(CLAUDE.md). Phase 0/5는 직접.
- **서비스 레포**(crdt-engine/backend/frontend): 일반 룰 = **branch + PR + 건별 승인**. Phase 1~4 각 PR push/create는
  사용자 건별 승인 필요(user-approval.md). 에이전트가 직접 push·PR 생성 금지.

---

## 실행 체크리스트

### Phase 0 — plan 기록 (controller, main 직접)
- [x] 이 파일 작성 + commit (82b1f67, 정밀화 갱신 후속 커밋) ← 코드 작업 전 게이트

### Phase 1 — crdt-engine 머지 + fan-out (Rust) ★ 가드레일 게이트 — ✅ 완료(PR #1 머지)
- [x] **1.0 write-time 검증**: yrs 0.27 API 전부 docs.rs 검증(§B). `apply_update`/`decode_v1` 모두 `Result`. `Doc` Send=스캐폴드 컴파일로 확인
- [x] 1.1 `engine.rs`: per-doc `{Doc + broadcast(cap 256)}`. `apply_v1`(decode_v1→apply_update→broadcast) · `diff_v1`(SyncStep2) · `full_state_v1`(resync/snapshot) · `open`(구독-후-스냅샷 락순서 §D-2, 락 안 .await 없음). (1d63689)
- [x] 1.2 `service.rs`: `Sync` bidi 실구현 — 메타데이터 `doc-id`(§D-1), 초기 SyncStep1, select 루프
      (ClientFrame{sv}→SyncStep2, ClientFrame{update}→apply+broadcast, broadcast→fan-out, Lagged→full resync §D-5). `GetSnapshot`=full v1. (1d63689)
- [x] 1.3 `tests/convergence_proptest.rs` 본문: 교환(forward=reversed=sorted) · 멱등(2회=1회) · 두 복제본 수렴 — 3 proptest green (가드레일 6). (e280308)
- [x] 1.4 ~~tonic in-process~~ → **레지스트리 레벨 fan-out 통합테스트로 대체**(`tests/registry_fanout.rs`): build.rs `build_client(false)`라 in-process gRPC 클라 미생성 → fan-out/diff/손상거부를 엔진 API로 검증. gRPC transport end-to-end는 Phase 3 E2E(실제 게이트웨이). (e280308)
- [x] 1.5 `benches/convergence.rs`: `apply_256_concurrent_updates` ≈ **1.166 ms**(~4.5µs/update) baseline (가드레일 5). (e280308)
- [x] VERIFY: `cargo test`(proptest 3 + fanout 3 green) · `cargo bench`(실측) · `cargo clippy --all-targets`(무경고) · `cargo build`
- [x] branch `feature/m1-merge-fanout` push + PR #1 생성(승인 후) → https://github.com/ressKim-io/weDocs-crdt-engine/pull/1
- [x] **코드리뷰**(rust-expert + code-reviewer 병렬) → 머지 전 8건 반영(F1~F8: doc_id 검증·full_state 부작용·sync 분리·손상프레임 대칭·테스트강화·fmt·상수주석·bench). 재검증 8 test green / clippy -D warnings / fmt clean. 기록: [dev-log](../dev-logs/2026-06-25-m1-engine-code-review.md)
- [x] **PR #1 머지 완료**(merge commit fbd25fe, 2026-06-26) → 원격 브랜치 삭제, 로컬 main 동기화

### Phase 2 — ws-gateway 브리지 (Java) — 최고위험 TDD — ✅ 완료(PR #1 머지, e0e8277)
- [x] **2.0 write-time 검증**(2026-06-26): Spring Boot 4.1/Framework 7.0.x — `WebSocketConfigurer`/`addHandler(h, String...)` 유지, `BinaryWebSocketHandler` 유지, Ant 와일드카드 `/ws/doc/*`(AntPathMatcher) 지원, `WebSocketSession.getUri()/getId()/sendMessage/isOpen()` 존재(javadoc: JSR-356 동시송신 불가→`ConcurrentWebSocketSessionDecorator`), 생성 stub `CrdtEngineStub.sync(StreamObserver<ServerFrame>)→StreamObserver<ClientFrame>` 확인
- [x] 2.1 lib0 코덱 `Lib0.java`(varUint=unsigned LEB128 + varUint8Array) — TDD Red→Green. `Lib0Test` 8 pass(경계값·known-byte 벡터·손상프레임 거부)
- [x] 2.2 `DocWebSocketHandler`: 세션당 Sync 스트림 open(메타데이터 `doc-id`=URL room §D-1), WS→ClientFrame(`YProtocolCodec.decodeInbound`), ServerFrame→WS `Update(2)`(§D-4), awareness/auth/query/미인식 drop(§D-7), close/onError/onCompleted/transportError 전 경로 스트림 정리(bridges ConcurrentHashMap remove 게이팅). `WebSocketConfig` 경로 `/ws/doc/*`
- [x] 2.3 `EngineClient.openSync(docId, respObs)`: `Metadata doc-id`+`MetadataUtils.newAttachHeadersInterceptor`→`asyncStub.withInterceptors(..).sync(..)`. 엔진 키 `"doc-id"`(service.rs:52) 정합 확인. JNI 미사용 유지
- [x] 2.4 통합테스트 `DocWebSocketBridgeIntegrationTest`(✅ 결정=fake in-process gRPC 엔진): doc-id 메타데이터 전파+SyncStep1 forward, 2클라 fan-out→WS Update(2). 2 pass. 실제 Rust 엔진 수렴=로컬 스모크+Phase 3
- [x] VERIFY: `./gradlew :ws-gateway:test`(**22 pass**: Lib0 9·Codec 10·통합 3) · `make build`(bootJar green)
- [x] 2-lens 코드리뷰 완료·전부 반영(2026-06-26~27, 커밋 077db1a): **java-expert**(동시성/생명주기) Major2건 — endSession 스트림 누수→`completeQuietly`, handleBinaryMessage↔close TOCTOU→`computeIfPresent` 직렬화. **code-reviewer**(정합/테스트/가독) Major1건 — `encodeOutbound` both-set 무성 드롭→방어 log.warn+계약주석(verified service.rs:66)+우선순위 테스트. Minor: SLF4J Throwable 전달·roomFromUri null guard·@AfterEach 격리·lib0 오버플로·decode 대칭. 보류: FakeEngine 추출(nit)·Origin 제한(Phase 5)
- [x] branch push + PR + 리뷰 코멘트 게시(2026-06-27, 사용자 건별 승인): https://github.com/ressKim-io/weDocs-backend/pull/1 (3 커밋: 3507a85 codec, 19d5453 bridge, 077db1a review-fix) → **PR #1 머지 완료**(e0e8277, 2026-06-27), backend main 동기화

### Phase 3 — frontend 검증 + E2E 수렴 (React) — 헤드라인 산출물 — ✅ 완료(PR #1 머지)
- [x] 3.1 `Editor.tsx` 표준 provider 유지 + room=`?room=<id>` 쿼리(미지정 demo)로 다중 문서. (ed4068d)
- [x] 3.2 **E2E 수렴 테스트** `test/e2e/convergence.e2e.test.ts`(vitest): 2 클라이언트(Node `y-websocket`+`ws` 폴리필,
      `disableBc:true`로 BroadcastChannel 우회 차단→게이트웨이 경로만) concurrent edit → **텍스트 동등성 폴링** 수렴 assert(§D-4, 'synced' 비의존).
      실행마다 고유 room(엔진 미evict §D-8 오염 차단). 연결 타임아웃 10s로 미기동 시 명확 실패. `vitest`+`ws` devDep. (f433d0b)
- [x] VERIFY(실측, 추정 아님): 로컬 engine(`cargo run`:50051)+gateway(bootJar:8080) 기동 → `npm run test:e2e` **2회 green**(168ms/978ms).
      gateway 로그가 테스트 시각(17:17:48)에 WS 핸들러+gRPC TcpMetrics 초기화 → WS→gateway→gRPC→engine→fan-out 실경로 확인(false positive 아님). `npm run build`(tsc+vite) green.
- [x] branch `feature/m1-e2e-convergence`(2 커밋: ed4068d editor, f433d0b e2e) push + **PR #1 머지 완료**(merge commit e8f0c83, 2026-06-28): https://github.com/ressKim-io/weDocs-frontend/pull/1 → 원격 브랜치 삭제, 로컬 main 동기화

### Phase 4 — OTel 폴리글랏 trace 전파 (gateway+engine) 가드레일 4 — **thin 2-hop 확정(2026-06-28)**

> **스코프 확정**: `traceparent` **2-hop 전파 증명만**(가드레일 4 충족 + 패턴 확립). 풀 관측 스택(Collector·tail 샘플링·Grafana 대시보드)은 **M5로 명시 연기**.
> **정직한 한계(2026-06-28 검증)**: bidi 스트림의 traceparent는 **stream-open(HTTP/2 헤더) 시 1회** 주입 → 산출물은 "한 *편집*"이 아니라 **"한 WS 세션(스트림 open)이 Java span→Rust span 단일 trace로 연결"**. **per-edit 메시지 span**은 proto field 또는 수동 컨텍스트 전파 필요 → **M1.5/M5**(원 plan 문구 "한 편집이…" 교정).
> **검증된 접근(2026-06-28 WebSearch)**: Java = **OTel javaagent 2.28.x**(grpc-java 클라 자동계측이 W3C traceparent out-of-box 주입, **앱 코드 변경 0**) / Rust = **`tonic-tracing-opentelemetry` server layer**(메타데이터 traceparent 추출→child span) + `opentelemetry`/`opentelemetry_sdk`/`opentelemetry-otlp`/`tracing-opentelemetry`. 출처: [OTel Java agent](https://opentelemetry.io/docs/zero-code/java/agent/) · [tonic-tracing-opentelemetry](https://crates.io/crates/tonic-tracing-opentelemetry).

**Blast Radius**: 직접변경 = engine `main.rs`·`service.rs`·`Cargo.toml`(+lock) / gateway 기동 스크립트·`Makefile`·문서(**Java 앱 코드 0** — javaagent 런타임 부착). 간접영향 = engine 부팅 경로(tracer init 실패가 부팅 막지 않게 graceful degrade) · gateway 실행 커맨드(`java -jar` → `java -javaagent:… -jar`). 롤백 = 각 서비스 레포 PR revert / controller plan은 main 커밋 revert. 검증 = Jaeger 단일 trace 스크린샷 + 양쪽 trace_id 로그 일치 + **기존 E2E 수렴 회귀 green 유지**. 다운타임 = 로컬 only N/A. 두 서비스 레포 = **branch+PR+건별 승인**.

- [x] **4.0 write-time 검증(2026-06-28 완료)** — 버전 pin + 정합 확인:
  - **Java**: OTel javaagent **v2.29.0**(2026-06-19, GitHub releases authoritative). grpc 자동계측 W3C traceparent out-of-box(앱 코드 0). VT·Spring Boot 4.1 호환은 agent 부착 후 스모크로 재확인
  - **Rust 코어(0.32 line 동반 정렬)**: `opentelemetry` 0.32 · `opentelemetry_sdk` 0.32.1 · `opentelemetry-otlp` 0.32(✅ **tonic ^0.14.1 지원** — 엔진 tonic 0.14 정합) · `tracing-opentelemetry` 0.33 · `tracing` 0.1 · `tracing-subscriber` 0.3
  - **traceparent 추출 2안**: (1) **수동(권장, lean)** — `global::get_text_map_propagator().extract(MetadataExtractor(&MetadataMap))` → `tracing_opentelemetry::OpenTelemetrySpanExt::set_parent`. 코어 crate만 의존·tonic 버전 무관. (2) `tonic-tracing-opentelemetry` **0.38.0**(✅ deps 검증: tonic ^0.14 · opentelemetry ^0.32 · tracing-opentelemetry ^0.33 정합) server layer — 코드 적지만 tower/hyper/http 전이 의존. **최종 선택은 4.4 otel-expert와 함께**
  - **API 정밀 정합**(exporter init·`TraceContextPropagator` 경로 등)은 engine 브랜치에서 `cargo add` 후 docs.rs 0.32/0.33로 재확인(추측 코드 금지)
  - ⚠️ **로컬 docker 미설치 확인** → 검증 경로 docker-free로 조정(§4.3)
- [ ] 4.1 **engine(Rust)**: `main.rs`에 OTLP tracer init(`opentelemetry-otlp`→Jaeger) + `tracing-subscriber` + `TraceContextPropagator` 전역 등록(tracer init 실패해도 서버는 기동). `service.rs::sync`에 `tonic-tracing-opentelemetry` server layer로 traceparent 추출→span. **이참에 `eprintln!`→`tracing` 일괄 전환**(리뷰 후속 해소). proto 변경 X
- [ ] 4.2 **gateway(Java)**: OTel **javaagent 부착**(기동 커맨드/Makefile/run 스크립트만) — `OTEL_SERVICE_NAME=ws-gateway` · `OTEL_EXPORTER_OTLP_ENDPOINT`(Jaeger) · `OTEL_TRACES_EXPORTER=otlp`. **앱 코드·build.gradle 변경 0**(javaagent=bytecode instrumentation, JNI 아님 → 가드레일 3 무관)
- [ ] 4.3 **검증(실측, 추정 금지) — docker-free 1차**: gateway javaagent `OTEL_TRACES_EXPORTER=logging`(console) ↔ engine `opentelemetry-stdout`(0.32) console export → 두 탭 편집 시 **gateway CLIENT span ↔ engine SERVER(`sync`) span의 trace_id 일치**를 양쪽 stdout에서 확인(가드레일 4 증명, 외부 의존 0). **선택(showcase)**: docker 또는 **Jaeger all-in-one 바이너리**(OTLP `4317`/UI `16686`)로 단일 trace UI 스크린샷
- [ ] 4.4 **otel-expert cross-check**: tracer init·exporter protocol(gRPC vs HTTP 기본값, config-contract-audit)·propagator·샘플링 기본값 정합 검토
- [ ] branch + PR (engine·backend 각각, 건별 승인)

### Phase 5 — 마감 (controller, main 직접)
- [ ] dev-log: 수렴 증명 결과(Before/After·검증 방법·교훈) + §D 결정들
- [ ] ADR: 엔진 sync/fan-out 브리지 설계(게이트웨이=번역기, 엔진=권위, broadcast fan-out, v1 고정) — 대안 비교표
- [ ] 이 plan `status: done` + dev-log 링크 + commit

---

## 검증

| 대상 | 명령 | 게이트 |
|---|---|---|
| engine | `cargo test`(proptest 수렴 green) · `cargo bench --no-run` | 가드레일 5·6 |
| gateway | `./gradlew test`(코덱 라운드트립 + 통합) | TDD(testing.md) |
| frontend | `npm run build` + E2E(2클라 텍스트 수렴) green | 헤드라인 |
| 전체 | 로컬 engine(50051)+gateway(8080) 기동 → 두 탭 `ws://localhost:8080/ws/doc/demo` 동시 편집 → 동일 텍스트 | M1 정의 |
| OTel | Java span→Rust span 단일 trace 연결 | 가드레일 4 |

- 로컬 환경(buf 1.71·cargo 1.96·java 25.0.3·node 26·gh 2.95) 설치 확인 → 모든 검증 실행 가능.
- 못 돌린 검증은 "추정 통과" 금지, "미실행" 명시(deep-thinking.md).

## 범위 밖

doc-service·ai-service / 스냅샷 DB 영속화 / Istio 메타데이터 consistent-hash 라우팅 / 멀티-인스턴스 엔진 /
**awareness(커서) — M1.5**(proto bump) / **'synced' 라이프사이클·self-echo 필터 — M1.5** / **브라우저-origin trace span — M1.5** / 인증·인가.

리뷰 후속(M1.5/Phase 4, [dev-log](../dev-logs/2026-06-25-m1-engine-code-review.md)): `eprintln!`→`tracing`(Phase 4 OTel 일괄) / 테스트 헬퍼 DRY 공통화 / proptest에 shared-base 동시편집·delete op 케이스 / `lagged_total` 메트릭 / idle 세션 keep-alive.

---

## 재개 지점 (Resume)

> **마지막 완료**: **Phase 3 frontend E2E 수렴 — PR #1 머지 완료**(e8f0c83, frontend main 동기화·브랜치 삭제). Phase 1~3 전부 머지 = **수직 슬라이스 수렴 본체 증명 끝**. (Phase 2 e0e8277, Phase 1 fbd25fe.) `Editor.tsx` room=`?room=` 쿼리 + `test/e2e/convergence.e2e.test.ts`(vitest, 2클라 y-websocket+ws, `disableBc:true`, 고유 room, 텍스트 폴링 §D-4). 로컬 engine+gateway 실기동 → `npm run test:e2e` 2회 green + gateway 로그 gRPC 실경로 확인 + `npm run build` green. (문서 최신화: CLAUDE.md 현재상태 · onboarding §6 · controller README 마일스톤.)
> **다음 작업**: **Phase 4 OTel thin 2-hop trace**(2026-06-28 스코프 확정 — 풀 관측 스택은 M5 연기). gateway(Java OTel **javaagent**, 앱 코드 0)→engine(Rust **`tonic-tracing-opentelemetry`** server layer) gRPC 메타데이터 `traceparent` 전파. **검증된 한계**: stream-open 1회 주입 → "한 WS 세션이 Java span→Rust span 단일 trace 연결"(per-edit span은 M5). 검증 = 로컬 **Jaeger all-in-one**(docker)에서 단일 trace 스크린샷 + trace_id 로그 일치 → otel-expert cross-check. **시작 = §4.0 write-time 검증**(Java agent patch pin + Rust 0.x crate `cargo add`/docs.rs 정합 — 추측 코드 금지). **양쪽 서비스 레포 = branch+PR+건별 승인.** 이후 Phase 5 마감(dev-log 수렴 증명 + ADR 브리지 설계 + plan done) → **M2(영속화·세션·권한, doc-service 신설)**.
> **주의(검증된 자산, 변경 금지)**: Phase 1~3 모두 v1 인코딩 고정(§B). 엔진 메타데이터 키=`"doc-id"`(service.rs:52)↔게이트웨이 정합(§D-1). ServerFrame{update}=전부 `Update(2)` 프레이밍 → E2E는 'synced' 비의존 텍스트 폴링(§D-4). E2E는 `disableBc:true` 필수(없으면 BroadcastChannel로 게이트웨이 우회=거짓 green). 엔진 M1 미evict(§D-8) → E2E 실행마다 고유 room.
> **주의(로컬 검증 기동)**: engine `cd weDocs-crdt-engine && cargo run`(:50051) / gateway `cd weDocs-backend && java -jar ws-gateway/build/libs/ws-gateway-0.1.0.jar`(:8080, 먼저 `make proto-gen && ./gradlew :ws-gateway:bootJar -x test`) / E2E `cd weDocs-frontend && npm run test:e2e`.
> **환경**: buf 1.71 · cargo 1.96 · java 25.0.3 · node 26 · gh 2.95.
