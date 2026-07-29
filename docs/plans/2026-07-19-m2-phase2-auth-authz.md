---
date: 2026-07-19
slug: m2-phase2-auth-authz
status: done
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0014-auth-authz-boundary.md
  - adr/0011-engine-sync-fanout-bridge.md
  - adr/0017-jwt-rs256-jwks.md
  - prd/4-data-and-permission-model.md
---

# M2 Phase 2 — 인증/인가 (gateway 검증 · viewer 다층 방어)

> M2 본류([m2-persistence-session](2026-06-30-m2-persistence-session.md)) **Phase 2**의 상세 plan. 상위 §재개 지점이 이 파일을 "다음"으로 가리킨다.
> 서비스 레포(ws-gateway/crdt-engine/frontend) 코드는 **branch+PR+건별 승인**. controller(이 plan·ADR)만 main 직접.

## Context

**왜**: M1~Phase 1은 인증이 없다 — 누구나 어떤 room이든 접속·편집. Phase 2는 [ADR-0014](../adr/0014-auth-authz-boundary.md)에 따라 gateway를 인증 게이트로 만든다: `Sec-WebSocket-Protocol`로 JWT 수신 → 검증 → `user_id` 추출 → `DocService.CheckPermission(doc_id, user_id)` → `none`=거절 / `viewer`=read-only / `editor`=양방향. 발급측(JWT/JWKS, [ADR-0017](../adr/0017-jwt-rs256-jwks.md))은 1c①(#7)에서 완료 — 이번은 **검증측 + 연결시 인가 + viewer 쓰기 차단**.

### 코드 기준 확정 사실 (2026-07-19 탐색)
- proto(SSOT): `CheckPermissionRequest {doc_id, user_id}` → `CheckPermissionResponse {bool allowed, common.Role role}`. `Role {ROLE_UNSPECIFIED=0, ROLE_VIEWER=1, ROLE_EDITOR=2, ROLE_OWNER=3}`. **proto 변경 불요**(추가 계약 없음).
- gateway 핸드셰이크 진입점 = `ws-gateway/…/ws/RoomHandshakeInterceptor.beforeHandshake` — `/ws/doc/{room}`에서 room을 **업그레이드 전** 검증·거절하고 `RoomId`를 세션 attribute로 넘긴다. **인증/인가도 여기(업그레이드 전)에 붙는다.** `doc_id = room = 마지막 경로 세그먼트`.
- gateway엔 **doc-service gRPC 스텁 없음** — 엔진용 `EngineClient`만 존재 → CheckPermission 클라이언트가 신규.
- doc-service JWKS 엔드포인트(`JwksController`, kid=RFC 7638 thumbprint) 존재 → gateway 검증키 소스.
- gateway = Java 25 Virtual Thread(가드레일 3: JNI 금지) → 핸드셰이크의 블로킹 gRPC/HTTP 호출은 VT에 적합(스레드 pinning 회피 검증은 구현 시).

### 이 세션 확정 결정 (사용자, 2026-07-19)

| # | 결정 | 채택 | 근거 |
|---|---|---|---|
| Q1 | PR 분해 | **레포별 3(+1) PR**: 2a gateway 인증 → 2b engine 방어 → 2c frontend 토큰 | PR≤400줄·레포 분리. viewer 다층방어(D-5)를 Phase 2 안에서 완성(2b 미루면 gateway 단일지점 의존) |
| Q2 | 인증/인가 실패 처리 | **인증·인가 모두 핸드셰이크(업그레이드 전) HTTP 거절**: authn 실패=**401**, authz 거부=**403** + **운영 관측 1급**(구조화 로그·메트릭·fail-closed 신호). WS close **4401/4403 = 연결 후 close 경로로 예약** | 실무 표준·근본 해결. HTTP 상태코드가 access log·Istio/Envoy·Prometheus에 그대로 노출(L7 관측), WS close code는 프레임 내부라 프록시·메트릭에 불가시. 업그레이드 전 거절=세션 자원 미할당(DoS). → **[ADR-0021](../adr/0021-ws-handshake-auth-failure-observability.md)** |
| Q3 | gateway 검증키 | **doc-service JWKS fetch + 캐시**(kid 매칭, TTL, 회전 지원, fail-closed) | 기존 `JwksController` 재사용, 키 회전 무중단. 런타임 gateway→doc-service 의존은 mTLS(ztunnel)+캐시로 완화 |

### 2a-2 착수 시 확정 결정 (사용자, 2026-07-20)

| # | 결정 | 근거 |
|---|---|---|
| D1 | **비UUID `doc_id`/`user_id` → gRPC 호출 없이 403**(`reason=invalid_doc_id`) | `RoomId`는 `[A-Za-z0-9_-]{1,128}`을 허용하지만 `DocServiceImpl`은 `doc_id`·`user_id` 둘 다 **UUID 파싱 필수**(아니면 `INVALID_ARGUMENT`). doc-service가 이미 "비존재 page → `DENIED`(NOT_FOUND 아님)"로 존재 여부를 비노출하므로, 게이트웨이 단축 거절이 **동일 결과 + 무의미 왕복 제거**. ⚠️ 필연적 결과: 기존 `DocWebSocketBridgeIntegrationTest`(room=비UUID, subject=`"it-user"`)는 UUID로 갱신해야 함 |
| D2 | **2a-2를 단일 PR로**(≤400줄 룰 초과 시 PR 본문에 근거 명시) | authz만 선머지하면 **viewer가 쓰기 가능한 중간 상태**가 열린다(D-5 구멍). 단일 관심사 + 테스트 비중 큼(~300/615줄) |

### 2b 착수 시 확정 결정 (사용자, 2026-07-20)

| # | 결정 | 근거 |
|---|---|---|
| D3 | **`role` 메타 부재/미인식 = 스트림 거절**(`invalid_argument`, open 시점 · registry.open 이전) | fail-closed. 게이트웨이는 `role`을 **무조건** 보내므로(`EngineClient.openSync`가 유일 호출부·null 분기 없음, 롤 미해결 시 스트림을 아예 안 엶) 정상 경로 무영향. "메타 없으면 조용히 동작"은 계약 위반을 은폐한다. 대가: grpcurl 수동 디버깅 시 `-H role:editor` 필수 |
| D4 | **viewer 스트림에 update 도착 = `permission_denied` 전송 후 스트림 종료** | 정상 게이트웨이는 viewer update를 절대 전달하지 않는다(`DocWebSocketHandler.isPermitted` 필터) → **도착 자체가 우회 신호**. 기존 `doc_id mismatch` 선례와 동일 규약(하드 위반=닫음). 같은 프레임의 `state_vector`도 함께 버려짐 — 게이트웨이도 프레임 통째로 drop하므로 판정 의미 동일 |
| D5 | **`build.rs`의 `build_client(false)` → `true` flip 후 실제 Sync 스트림 통합 테스트** | 2b 정확성이 전부 gRPC 메타 경계에 있어, private 헬퍼 단위테스트로는 "실제로 막히는지"를 증명 못 한다(배선 회귀에 취약 = 공허한 green). ADR-0013상 Phase 3에서 어차피 flip 예정이라 선반영 |

**2b wire 계약(2a-2가 이미 흘리는 값, 2026-07-20 양 레포 탐색으로 확인)**: 메타 키 `role`(ASCII, `doc-id`와 같은 open-time 채널, `EngineClient.java:28-29·56-64`) · 값은 **`"viewer"` | `"editor"` 둘뿐**(OWNER는 게이트웨이서 editor로 접힘·UNSPECIFIED는 403, `SessionRole.java:27-33·43-45`) · "쓰기"의 정의 = **`update` 필드 non-empty**(`state_vector`/SyncStep1은 viewer도 통과해야 함 — 막으면 문서 수신 불가, `DocWebSocketHandler.java:100-107`).

### 인가 매핑 (CheckPermissionResponse → 세션 정책)
- `allowed=false` (또는 `role=UNSPECIFIED`/응답 이상) → **403 거절**(fail-closed).
- `allowed=true, role=VIEWER` → **read-only 세션**: client→server update **drop**, server→client만 통과 + 엔진에 `role=viewer` 메타 전달.
- `allowed=true, role=EDITOR|OWNER` → **양방향** + 엔진에 `role=editor` 메타.

## Blast Radius

| 항목 | 내용 |
|---|---|
| 직접 변경(controller) | `docs/adr/0021-…md`(Q2 결정), 이 plan |
| 직접 변경(2a, ws-gateway) | 신규 `JwksVerifier`/JWKS 클라이언트·캐시, `AuthHandshakeInterceptor`(또는 Room 인터셉터 확장)+subprotocol echo `HandshakeHandler`, 신규 doc-service gRPC 클라이언트(`DocServiceClient`), `DocWebSocketHandler`(viewer write-drop·role 메타), 관측(메트릭·구조화 로그), config(JWKS URL·clock skew·CheckPermission timeout) |
| 직접 변경(2b, crdt-engine) | Sync 스트림 open 시 `role` 메타 수신 → viewer 스트림의 write 프레임 거부(엔진 방어, D-5) |
| 직접 변경(2c, frontend) | y-websocket provider가 `Sec-WebSocket-Protocol`로 JWT 전달(로그인 토큰 소비) |
| 간접 영향 | 인증 도입 → 기존 무인증 E2E(Phase 3 frontend E2E) 토큰 필요. gateway↔doc-service 신규 런타임 의존(JWKS+gRPC) |
| 롤백 | 각 PR revert. proto 무변경이라 계약 롤백 불요. controller = git revert |
| 검증 | 아래 §검증(DoD) — authn 401·authz 403·viewer read-only(다층)·editor 양방향·JWKS 회전·fail-closed·관측 |
| 다운타임 | 없음(로컬 dev/test). 클러스터 배포=M5 |

## PR 분해 (서비스 레포, 게이트 통과 후)

> 각 PR = 해당 레포 branch+PR+건별 승인. 크래프트 6종(+P7) 게이트 2-렌즈(☕/🦀). PR 경계마다 이 plan 재개지점 갱신.

### 0. ADR-0021 (controller, main 직접) — Q2 결정 기록 ✅
- [x] `docs/adr/0021-ws-handshake-auth-failure-observability.md`: 핸드셰이크 HTTP 거절 vs WS close 대안비교 + 관측 계약(로그 필드·메트릭·알림) + fail-closed. (커밋 `8e08af5`)

### 2a-1. gateway 인증 핸드셰이크 (ws-gateway) ✅ ([backend PR #16](https://github.com/ressKim-io/weDocs-backend/pull/16) 머지, squash `583b065`)
- [x] **JWKS 검증기**(`JwtVerifier`/`AuthConfig`): 원격 JWKS fetch + Nimbus 기본 캐시/회전(5분·30초전 갱신·30초 rate-limit, 공식 검증) + kid 매칭, RS256 서명·`iss`/`exp` 검증(clock skew). **fail-closed**: JWKS 미획득/키 부재 → empty. (`aud`는 발급측 미발급이라 검증 대상 아님 — plan 문구 정정)
- [x] **subprotocol 토큰**(`AuthSubprotocol`/`AuthHandshakeHandler`): `Sec-WebSocket-Protocol` `[SENTINEL, <jwt>]`(SENTINEL=`wedocs.sync.v1`) → 서버가 SENTINEL만 echo(토큰 비반향), 모호(토큰≠1개) 시 거절.
- [x] **authn 게이트**(`AuthHandshakeInterceptor`): 무토큰/무효/만료 → **HTTP 401**(업그레이드 전, 세션 미생성). 성공 → `user_id` 세션 attribute.
- [x] **관측**(ADR-0021, `AuthMetrics` + actuator/micrometer): 구조화 로그(`result=ok|authn_fail` `doc_id` `user`(SHA-256 해시) `reason` `verify_ms` `trace_id`, 토큰·PII 비로깅) + 메트릭 `ws_handshake_total`·`jwt_verify_total`·`jwks_refresh_total{result}`(후자=`MeteredResourceRetriever` 데코레이터). **H-1**: ok 집계·로그를 `afterHandshake`로 미뤄 Origin 거절(403)을 ok로 오집계 안 함(앱 신호=상태코드, before→after=ThreadLocal).
- [x] 테스트(TDD, 69 green): 유효/무효/만료/서명불일치/unknown-kid/subject부재/형식오류, subprotocol echo, 메트릭 Prometheus `_total` 계약, config fail-fast, H-1 정상·거절 양경로. 크래프트 게이트(☕ 2-렌즈, BLOCKING 0).
- **이월(추적)**: actuator 무인증 노출 → M5 mesh 하드닝 · JWKS-fail vs bad-token `reason` 세분화 → 2a-2(단 `jwks_refresh_total{fail}`로 인프라 다운 구분 가능). VT pinning = 2a-1 무해(첫 fetch만, 이후 refresh는 Nimbus 별도 스레드) — **2a-2 CheckPermission 블로킹 gRPC에서 재검**.

### 2a-2. gateway 인가 + viewer 다층 1차 ✅ ([backend PR #17](https://github.com/ressKim-io/weDocs-backend/pull/17) 머지, squash `4cb750d`)

> 배선 사실(2026-07-20 탐색): 핸드셰이크 체인 = `RoomHandshakeInterceptor`(400) → `AuthHandshakeInterceptor`(401) → **신규 authz** → 프레임워크 Origin(403). authz는 auth 뒤라 `wedocs.roomId`(`RoomId`)·`wedocs.userId`가 이미 세팅된 상태로 받는다. **H-1 불변식이 자동 보호됨** — authz가 403을 세팅하면 Spring이 앞선 인터셉터의 `afterHandshake`를 호출하고, 거기서 `isRejected(status≥400)`로 ok 집계를 건너뛴다(회귀 테스트로 고정).

- [x] **doc-service gRPC 클라이언트**(`grpc/DocServiceClient`): `EngineClient` 채널 패턴 재사용(keepalive 30s/10s, `@PreDestroy` shutdown) + **blocking 스텁 + `withDeadlineAfter`**(모듈 내 최초 deadline 사용 — 핸드셰이크 무한대기 방지). 반환은 proto 비누출 3-상태 `ALLOWED(role)`/`DENIED`/`BACKEND_ERROR`(관측에서 거부 vs 장애 구분). **fail-closed**: 모든 `StatusRuntimeException`·타임아웃 → `BACKEND_ERROR`(=거절), 예외 비삼킴.
- [x] **경계 타입**(`auth/SessionRole`): `enum {VIEWER, EDITOR}` + `fromProto(Role)` → `OWNER`=EDITOR, `UNSPECIFIED`/`UNRECOGNIZED`=empty(거절). 외부 입력→도메인 타입 단일 변환점(secure-coding P1).
- [x] **authz 게이트**(`auth/AuthzHandshakeInterceptor`): roomId·userId **UUID 파싱**(D1, 실패 시 gRPC 없이 403) → `CheckPermission` → `allowed=false`/role 매핑 실패 = **403** `reason=authz_denied` · `BACKEND_ERROR` = **403** `reason=backend_error`. 성공 시 `ROLE_ATTRIBUTE`(`wedocs.role`) 세팅.
- [x] **viewer write-drop(1차)**: `DocWebSocketHandler.handleBinaryMessage`가 디코드 결과에 **update가 담겼고** 세션=VIEWER면 엔진 미전달(`SYNC_STEP1`/state_vector는 초기 문서 수신에 필요하므로 **통과**). `YProtocolCodec` 무수정, server→client 단일 writer 불변식(D-6) 유지.
- [x] **role 메타 전달**: `EngineClient.openSync(docId, role, …)` — 기존 `doc-id` 메타데이터에 `role`(`viewer|editor`) 추가([ADR-0011](../adr/0011-engine-sync-fanout-bridge.md) 결정4, **proto 무변경**). 엔진 측 강제는 2b.
- [x] **관측(fail-closed 1급)**: `ws_handshake_total{result}`에 `authz_denied`·`backend_error` 추가(2a-1의 `ok`/`authn_fail` 계약 연장) + `checkpermission_duration` + `authz_backend_error_total`(알림 후보=page) + `ws_write_dropped_total{reason=viewer}`(D-5가 실제 발화하는지 — 무신호 실패 금지). 로그는 2a-1 규칙 재사용(user=SHA-256 해시, 토큰·PII 비로깅). OTel javaagent가 CheckPermission을 자식 span으로 자동 계측.
- [x] **config**(config-contract-audit 3곳 동시): `DocServiceProperties`(`wedocs.doc-service`, `GatewayAuthProperties` fail-fast 패턴) + `@DefaultValue` + `application.yml`.
- [x] 테스트: 단위(`AuthzHandshakeInterceptorTest`, 2a-1 테스트 구조 미러링 — `SimpleMeterRegistry` 실계측·Mock 서블릿·fake 클라이언트, 모킹 라이브러리 없음) 비UUID·denied·UNSPECIFIED·backend_error 403 + **H-1 회귀**(403 시 ok 미증가) / 통합 `FakeDocService`(랜덤 포트 실 TCP + `@DynamicPropertySource`, `FakeCrdtEngine` 패턴 — ws-gateway엔 `grpc-inprocess` 없음) + **기존 통합 테스트 room·subject UUID화**(D1 필연) + viewer write drop·editor 양방향·role 헤더 캡처 + **VT pinning 실측**(JFR `jdk.VirtualThreadPinned`; Java 25 JEP 491로 무해 가능성 높으나 **추정 금지·측정**).

### 2b. crdt-engine 방어층 ✅ ([crdt-engine PR #11](https://github.com/ressKim-io/weDocs-crdt-engine/pull/11) 머지, squash `4d9c39e`)

> 게이트웨이 무변경. `service.rs` 358줄 / `handle_inbound`(:223-263)의 read·write 분기는 **독립 `if` 2개**(oneof 아님 → 한 프레임에 둘 다 가능) / 엔진 `grep -rn "role" src/` = 0건 / 엔진엔 메트릭 익스포터 없음(tracing만).

> **완료(2026-07-28)**: [PR #11](https://github.com/ressKim-io/weDocs-crdt-engine/pull/11) squash 머지 `4d9c39e`. 크래프트 게이트 **BLOCKING [B] 0 → PASS**, 30 테스트 green(lib 18 + proptest 3 + fanout 3 + **sync_role 6**), clippy `-D warnings`·fmt clean, CI green(gitleaks·cargo-audit). ⚠️ 원 커밋 `7fb01b5` 메시지의 과장 서술은 **squash 메시지에서 정정**해 머지(방어 범위 = 게이트웨이 회귀·계약 위반).
>
> ⚠️ **게이트 실행 방식 변경**: `rust-expert`+`code-reviewer` 서브에이전트 병렬 spawn이 **2세션 연속 세션 한도로 중단**(각자 표준 6종+엔진 소스를 콜드 스타트로 재적재 = 예산 2배) → 3회차는 **인라인 직접 실행**으로 전환해 완주. 같은 규모의 단일 레포 게이트는 인라인이 비용·완주율 모두 우위.
>
> **게이트 검증한 주장**(주석이 단언한 것 → 실재 확인): `MAX_DOCUMENTS`(engine.rs:79) · `max_decoding_message_size`(main.rs) · GetSnapshot 갭 추적(`sdd/5-…:101` + retrofit plan:53 양쪽 실재 → escape hatch 성립, [B] 미발화) · 게이트웨이 `isPermitted`/`SessionRole.fromProto`/`EngineClient.openSync` 3심볼 실재 · 게이트웨이도 위반 프레임 통째 drop(`.filter`) → 판정 의미 동일.
>
> **findings**: Major 2(CR-001 혼합 프레임 무테스트 · CR-002 문서 서술 과장) + Minor 4(CR-003 role 거절 로그에 doc_id·trace 없음 / CR-004 Cargo.toml feature 주석 사실오류 / CR-005 `let _ = send` 근거 주석 / CR-006 plan의 `INVALID_ROLE_MSG` 상수 미도입 = plan 문구를 코드에 맞출 것). **CR-001·CR-002만 반영**(사용자 결정), Minor 4건은 §게이트 findings 이월.

- [x] **경계 타입**: `src/service.rs`에 `SessionRole {Viewer, Editor}` + `TryFrom<&str>`. 위치 근거 — `DocId`는 레지스트리 키라 `engine.rs`지만 role은 CRDT가 전혀 모르는 **전송 경계 개념**이므로 경계 파일에 둔다.
- [x] **추출**: `extract_role(&MetadataMap) -> Result<SessionRole, Status>` — `extract_doc_id`(:168-179) 패턴 그대로(부재 → `invalid_argument("missing role metadata")`, 미인식 → 상수 `INVALID_ROLE_MSG`, 상세는 서버 로그만 = P4). ⚠️ untrusted 원문 무상한 로깅 금지(길이 캡 또는 값 생략). `sync()`에서 `extract_doc_id` 직후·`registry.open` **이전**에 호출(자원 할당 전 거절) + span에 `role` 필드.
- [x] **강제**: `run_session`→`handle_inbound`에 `role` 전달, `doc_id mismatch` 가드 **직후**(=read 블록보다 앞)에 guard clause — viewer + `!update.is_empty()` → `permission_denied` 전송 후 `return false`. 혼합 프레임이 diff를 받아가지 못하게 순서가 중요.
- [x] **신뢰 경계 주석 갱신**(:96-101): "엔진 자체 방어선은 docId·`MAX_DOCUMENTS`·프레임 크기뿐"이 더 이상 사실이 아님 → role 강제 추가 + 남는 갭(호출자 신원 미검증 = mTLS/NetworkPolicy는 M5) 명시.
- [x] **테스트**: `build.rs` `build_client(true)`(D5) + `tests/sync_role.rs` 신규 — 랜덤 포트 `TcpListener`(0) + `serve_with_incoming` + 생성 클라이언트로 실제 스트림. ① viewer+update → `PermissionDenied`·스트림 종료 ② **viewer+state_vector만 → diff 정상 수신·유지**(읽기 불가 회귀 방지, 가장 중요한 반대 케이스) ③ editor+update → 적용·유지 ④ role 부재 → open 실패 ⑤ 미인식(`"owner"`/`"admin"`/`""`) → 거절(⚠️ `"owner"` 거절이 의도임을 테스트명에 명시 — 게이트웨이가 이미 editor로 접음). + 인라인 `extract_role` 단위 테스트(:331-337 미러링).
- [x] **CR-001 반영(게이트, 2026-07-28)**: **혼합 프레임**(한 프레임에 `update`+`state_vector` 동시) viewer 케이스 추가 — 인라인 `inbound_rejects_viewer_mixed_frame_before_replying_diff` + 통합 `viewer_mixed_frame_is_denied_without_diff`(루프로 Ok를 건너뛰지 않고 **바로 다음** 프레임이 거절임을 단언 = 순서 증명). 게이트웨이 코덱은 SyncStep1→`state_vector`/Step2·Update→`update`로 **둘 다 채우지 않으므로**, 이 프레임은 우회 호출자만 만든다 = 2b의 존재 이유인 경로가 무테스트였다. **대조군으로 실효성 증명**: 가드를 read 블록 뒤로 옮기면 신규 2건만 FAIL하고 **기존 5건은 전부 통과** — 순서 회귀가 실제로 무방비였음을 실증(억제와 무력화 구분, `secure-coding.md` 대조군 규율).
- [x] 검증: `make proto-sync && cargo build && cargo test && cargo clippy --all-targets -- -D warnings && cargo fmt --check` (⚠️ `proto/`는 gitignore·미생성 시 빌드 자체 실패, Makefile에 clippy/fmt 타깃 없음).

### 2c. frontend 인증·페이지 선택·역할 인지 → **별도 plan으로 분리**

> **상세 SSOT = [`2026-07-28-m2-phase2c-frontend-auth.md`](2026-07-28-m2-phase2c-frontend-auth.md).**
> 체크리스트·재개 지점은 그쪽에만 둔다(사본 금지 — `plan-logging.md` §재개 정보의 SSOT).

- [x] **2c 완료**(2026-07-29) — C0~C3 전 단계 종료. frontend PR #5·#6·#7·#8 + backend #19 머지.
      **이로써 Phase 2 전체 완료.** 상세 = 분리 plan §재개 지점 · 결과 = [dev-log](../dev-logs/2026-07-29-m2-phase2c-frontend-auth.md)

**왜 분리했나(2026-07-28)**: 원래 2c는 "`protocols` 옵션으로 JWT 전달" 한 줄이었으나, 착수 탐색에서
프론트엔드에 **로그인이 전혀 없고**(토큰 출처 없음) **페이지 UUID를 얻을 방법도 없음**(1c REST 미소비)이
드러났다. 또한 **클라이언트가 자기 역할을 알 방법이 없어**(`PageResponse`에 역할 필드 없음 · 핸드셰이크는
SENTINEL만 echo) viewer의 로컬 `Y.Doc`이 조용히 divergent해지는 **정합성 버그**가 확인됐다.
사용자 결정 = 우회하지 말고 **로그인 + 페이지 목록 + 역할 노출까지 근본 해결** → 2레포 3~4 PR 규모라 별도 트랙.

## 관측(Observability) 계약 — 운영 문제없게 (사용자 요구, ADR-0021)

핸드셰이크 HTTP 거절을 택한 이유가 곧 관측이므로 **1급 산출물**로 취급한다(monitoring.md·observability.md 렌즈).

- **로그(구조화, key=value)**: `event=ws_handshake`, `doc_id`, `user`(해시/미노출), `result=ok|authn_fail|authz_denied|backend_error`, `reason`, `role`, `verify_ms`, `check_permission_ms`, `trace_id`. **토큰·비밀번호·PII 금지**(security.md).
- **메트릭(Micrometer→Prometheus)**: `ws_handshake_total{result}`, `jwt_verify_total{result}`, `jwks_refresh_total{result}`, `checkpermission_duration`, `authz_backend_error_total`.
- **트레이스**: gateway OTel javaagent(Phase 4.2)로 CheckPermission gRPC = 자식 span, W3C traceparent 전파(가드레일 4). 폴리글랏 단일 trace 유지.
- **알림 후보(M5 배선, 지금은 계약만)**: 401/403 rate 급증(공격/클라이언트 버그), `authz_backend_error_total>0`(doc-service 불가 → fail-closed로 전 연결 거절, **page 대상**), JWKS refresh 실패 지속.
- **왜 HTTP인가**: 상태코드가 access log·Istio/Envoy 텔레메트리·`http_*{status}`에 노출 → 앱 코드 없이 L7 관측. WS close code는 WS 프레임 내부라 프록시·표준 메트릭 불가시.

## 검증 (Phase 2 DoD)

- **authn**: 무토큰/만료/무효 서명 → 핸드셰이크 **401**, 세션 미생성(로그/메트릭 확인).
- **authz**: 비멤버/none → **403**. viewer → 연결되나 **write drop(gateway) + 엔진 거부(2b)** 다층. editor/owner → 양방향.
- **JWKS 회전**: doc-service 키 회전 후 신규 kid 토큰 검증 성공(캐시 refresh).
- **fail-closed**: doc-service/JWKS 불가 시 연결 **거절** + `authz_backend_error_total`/`jwks_refresh_total{result=fail}` 발화(무신호 실패 없음).
- **관측**: Jaeger서 `ws-gateway → doc-service CheckPermission` 단일 trace, Prometheus서 handshake 결과 메트릭 노출.
- **회귀**: 기존 수렴 E2E가 토큰 경로로 green(2c).

## 재개 지점 (Resume)
- **이전 완료**: **2a-1 gateway 인증 핸드셰이크 ✅ 머지** — [backend PR #16](https://github.com/ressKim-io/weDocs-backend/pull/16) squash 머지(`583b065`, main), 69 테스트 green·CI green(gitleaks/dependency-review pass). ADR-0021(`8e08af5`)도 완료. 교훈 = [dev-log](../dev-logs/2026-07-19-m2-gateway-authn-observability.md).
- **마지막 완료**: **2a-2 gateway 인가 + viewer 다층 1차 ✅ 머지** — [backend PR #17](https://github.com/ressKim-io/weDocs-backend/pull/17) squash `4cb750d`, main 100 테스트 green·CI green(gitleaks/dependency-review pass, **squash 후 main 스캔도 success** 확인). 크래프트 게이트 2-렌즈 BLOCKING 0, advisory 전량 반영. **VT pinning 이월 검증점 종결** — JFR 0건 + `isVirtual()` 프로브로 공허한 green 배제, ⚠️ 안전 근거는 JEP 491이 아니라 grpc-java `LockSupport.park`라 **재측정 트리거 = grpc-java 메이저 업그레이드**([dev-log](../dev-logs/2026-07-20-vt-pinning-grpc-blocking-stub.md)).

- **2b crdt-engine role 강제 ✅ 머지** — [crdt-engine PR #11](https://github.com/ressKim-io/weDocs-crdt-engine/pull/11) squash `4d9c39e`, 크래프트 게이트 BLOCKING 0, 30 green, CI green.
- ✅ **Phase 2 전체 완료 (2026-07-29)** — 2a-1 · 2a-2 · 2b · 2c 전부 머지. 마지막 조각인 2c는
  분리 plan([2026-07-28-m2-phase2c-frontend-auth.md](2026-07-28-m2-phase2c-frontend-auth.md), **done**)이
  소유한다(진척 사본 금지). 결과 = [dev-log](../dev-logs/2026-07-29-m2-phase2c-frontend-auth.md).
  **다음은 Phase 2가 아니라 Phase 3(엔진 저장)** — 본류 [m2-persistence-session](2026-06-30-m2-persistence-session.md).
- ✅ **CI 갭 사이드트랙 완료(2026-07-28)** — 2c 착수 전 권고였던 항목 해소. 서비스 3레포에 빌드·테스트 CI가 없어 `cargo test`·Gradle·vitest가 CI에서 한 번도 안 돌던 상태를 3 PR로 정합(engine `fab982d`·backend `181b8de`·frontend `ff2e077`, 전부 main 트리거까지 green). 이제 **2c PR의 초록은 실제 검증을 뜻한다**. ⚠️ 단 프론트 **E2E는 여전히 CI 밖**(engine+gateway 실기동 필요) — 2c의 E2E 스모크는 로컬 실행으로 확인해야 한다. 상세 = [plan](2026-07-28-build-test-ci-gap.md)(done) · [dev-log](../dev-logs/2026-07-28-build-test-ci-gap.md).
- **Minor findings 이월(게이트 2026-07-28, PR에 미반영)**: CR-003 `extract_role` 거절 로그에 `doc_id`·`trace_id` 없음(span 생성 이전에 발화 + 함수가 `MetadataMap`만 수신) — 2b가 만드는 유일한 보안 신호인데 대상 문서 추적 불가, observability [A] P3/P6 · CR-004 `Cargo.toml` dev-dep 주석의 "테스트 빌드에서만 net/time" 주장이 사실과 다름(`cargo tree -e features,no-dev` 확인 = 프로덕션 빌드에도 tonic/hyper-util 전이로 이미 활성. dev-dep 선언 자체는 옳은 관행이니 **근거 문구만** 교체) · CR-005 `let _ = out_tx.send(...)`(:322) 무시 근거 주석 없음(기존 :309 동일 패턴 → 함께) · CR-006 plan이 명시한 `INVALID_ROLE_MSG` 상수 미도입(발화점 1곳이라 **plan 문구를 코드에 맞추는 쪽** 권장).
- 2b 설계 요지(Rust, `rust-expert` 🦀 + code-reviewer 2-렌즈). **2a-2가 이미 `role` 메타데이터를 보내고 있다** — 엔진은 지금 그것을 무시하므로, 2b는 수신·강제만 하면 된다(게이트웨이 무변경).
  - 입력 계약(2a-2가 확정, 이미 wire에 흐름): `Sync` 스트림 open 시 gRPC 메타데이터 **`role` = `"viewer"` | `"editor"`** (`doc-id`와 같은 open-time 채널, **proto 무변경**). 게이트웨이측 생성 지점 = `EngineClient.openSync`, 값의 출처 = `SessionRole.wireValue()`.
  - 할 일: `service.rs`가 open 시 `role`을 읽어 스트림에 보존 → `handle_inbound`의 **`apply_v1` 경로(=`!frame.update.is_empty()`)를 viewer 스트림에서 거부**. `state_vector`(`diff_v1`)는 읽기이므로 통과시켜야 한다(막으면 viewer가 문서를 못 받는다 — 게이트웨이와 같은 판정 기준). 상세 체크리스트 = 위 §2b.
  - ✅ **메타 부재 시 기본 정책 = 결정됨(D3, 2026-07-20)**: 부재·미인식 모두 **open 시점 `invalid_argument`로 스트림 거절**(fail-closed). 게이트웨이는 항상 보내므로 정상 경로 무영향. viewer 위반 처리는 D4(스트림 종료), 테스트 깊이는 D5(실 스트림).
  - 왜 미루면 안 되나 (⚠️ **2026-07-28 게이트 리뷰에서 서술 정정**): 2b가 닫는 것은 **게이트웨이 회귀·계약 위반**이다 — `DocWebSocketHandler.isPermitted`가 유실되는 회귀가 나면 viewer의 update가 `role=viewer`를 단 채 엔진에 도착하고, 2b가 그걸 잡는다(=D-5 다층 방어의 실제 의미). **닫지 못하는 것**: `role`은 클라이언트 통제 메타데이터라 **악의적 직접 호출자는 `editor`를 자칭하면 그대로 통과**한다 — 비인가 직접 접속 차단은 M5(mTLS STRICT·NetworkPolicy) 몫이다. 코드 주석(`service.rs` 신뢰 경계 "호출자 *신원*은 여전히 미검증")은 처음부터 정확했고, 이 plan·CLAUDE.md의 "엔진 직접 gRPC로 우회 가능 → 2b가 해소" 서술만 과장이었다(정정 완료).
  - 이후 = **2c frontend 토큰 전달**(`WebsocketProvider` `protocols` 옵션으로 JWT, subprotocol 지원 spec 사전검증). ⚠️ 2c에서 **데모 `?room=demo` 경로가 UUID여야 함**(2a-2 D1의 이월) — 실제 페이지 UUID를 쓰도록 정리.
- **주의**: 서비스 레포 = branch+PR+push 건별 승인. proto **무변경** → 태그 bump 불요. **관측 계약**: `ws_handshake_total{result}` = `ok`·`authn_fail`(2a-1) + `authz_denied`·`backend_error`(2a-2) — 2b가 엔진측 거부 신호를 추가하면 이 계약을 이어서 확장한다. VT pinning 재검점은 2a-2에서 종결(위). 이 §재개 지점 변경 시 상위 persistence plan·CLAUDE.md 동기화(plan-logging §재개 지점 SSOT).

## 범위 밖
- 연결 중 권한 강등 즉시 반영·연결 중 토큰 주기 재검증 → 후속(ADR-0014 트레이드오프, 재연결 시 반영이 MLP).
- 인증 서비스 분리 → 후속(M2=doc-service 내장).
- 엔진 영속화(save)·복원 → Phase 3/4. outbox → Phase 5. 권한 E2E 풀세트 → Phase 6.
- 알림 실배선·클러스터 mTLS STRICT → M5(지금은 관측 계약만).
- 4401/4403 연결후 close 실제 사용(연결중 무효화) → 후속. Phase 2는 핸드셰이크 HTTP 거절이 주경로.
