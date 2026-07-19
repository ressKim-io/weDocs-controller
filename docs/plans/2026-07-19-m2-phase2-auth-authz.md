---
date: 2026-07-19
slug: m2-phase2-auth-authz
status: in-progress
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

### 2a-2. gateway 인가 + viewer 다층 1차 (ws-gateway PR)
- [ ] **doc-service gRPC 클라이언트**: `CheckPermission(doc_id, user_id)` 채널(mTLS 전제), timeout + **fail-closed**(에러/타임아웃 → 거절).
- [ ] **authz 게이트**(핸드셰이크): `allowed=false`/UNSPECIFIED → **HTTP 403**. `VIEWER` → read-only 플래그·`EDITOR|OWNER` → 양방향(세션 attribute).
- [ ] **viewer write-drop(1차)**: `DocWebSocketHandler`가 read-only 세션의 client→server update 프레임 drop(server→client 유지).
- [ ] **role 메타 전달**: Sync 스트림 open 시 `role`을 gRPC 메타데이터로 엔진에 전달(doc-id 채널, [ADR-0011](../adr/0011-engine-sync-fanout-bridge.md) 결정4, **proto 무변경**).
- [ ] **관측(fail-closed 1급)**: `checkpermission_duration` 히스토그램 + `authz_backend_error_total`(doc-service 불가 시 발화 → 알림 후보) + authz 결과 로그. OTel javaagent가 gRPC CheckPermission을 자식 span으로 자동 계측(트레이스 연속성).
- [ ] 테스트: none=403·viewer read-only(write drop)·editor 양방향, doc-service down=fail-closed 403+메트릭, VT pinning 미발생.

### 2b. crdt-engine 방어층 (crdt-engine PR, rust-expert 리뷰)
- [ ] Sync 스트림 open 메타에서 `role` 수신 → **viewer 스트림에 도착한 write(update) 프레임 거부**(엔진 방어, D-5 다층 완성). 클라이언트/게이트웨이 우회 대비 최종 방어선.
- [ ] 테스트: viewer 메타 스트림의 write 거부 + editor 통과, 메타 부재 시 기본정책(fail-closed 관점).

### 2c. frontend 토큰 전달 (frontend PR)
- [ ] y-websocket `WebsocketProvider`가 로그인 JWT를 `Sec-WebSocket-Protocol`(`protocols` 옵션)로 전달. 버전의 subprotocol 지원 **spec 사전검증**(workflow.md 신규도구 검증). read-only(viewer) UI 반영은 최소.
- [ ] E2E 스모크(로컬): editor 양방향·viewer read-only·무토큰 연결 실패.

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
- **마지막 완료**: **2a-1 gateway 인증 핸드셰이크 ✅ 머지** — [backend PR #16](https://github.com/ressKim-io/weDocs-backend/pull/16) squash 머지(`583b065`, main), 69 테스트 green·CI green(gitleaks/dependency-review pass). ADR-0021(`8e08af5`)도 완료. 교훈 = [dev-log](../dev-logs/2026-07-19-m2-gateway-authn-observability.md).
- **다음**: **2a-2 gateway 인가 + viewer 다층 1차**(같은 ws-gateway 레포, PR #16 머지됨 → 새 브랜치 착수 가능) — doc-service `CheckPermission` gRPC 클라이언트(mTLS·timeout·fail-closed) + 핸드셰이크 authz(`allowed=false`/UNSPECIFIED→**403**, VIEWER=read-only·EDITOR/OWNER=양방향) + viewer write-drop 1차 + role 메타 엔진 전달 + 관측(`checkpermission_duration`·`authz_backend_error_total`). 이후 2b(engine role 방어)→2c(frontend 토큰). §PR 분해 2a-2 참조.
- **주의**: 서비스 레포 = branch+PR+push 건별 승인. proto **무변경** → 태그 bump 불요. **VT pinning 재검 포인트 = 2a-2**(CheckPermission 블로킹 gRPC를 핸드셰이크 VT에서 호출). **관측 계약 이어짐**: 2a-2가 `ws_handshake_total{result}`에 `authz_denied`·`backend_error` 추가(2a-1이 authn_fail·ok 확립). 이 §재개 지점 변경 시 상위 persistence plan·CLAUDE.md 동기화(plan-logging §재개 지점 SSOT).

## 범위 밖
- 연결 중 권한 강등 즉시 반영·연결 중 토큰 주기 재검증 → 후속(ADR-0014 트레이드오프, 재연결 시 반영이 MLP).
- 인증 서비스 분리 → 후속(M2=doc-service 내장).
- 엔진 영속화(save)·복원 → Phase 3/4. outbox → Phase 5. 권한 E2E 풀세트 → Phase 6.
- 알림 실배선·클러스터 mTLS STRICT → M5(지금은 관측 계약만).
- 4401/4403 연결후 close 실제 사용(연결중 무효화) → 후속. Phase 2는 핸드셰이크 HTTP 거절이 주경로.
