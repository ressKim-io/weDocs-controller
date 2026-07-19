# ADR-0021 — WS 인증/인가 실패 처리 = 핸드셰이크 HTTP 거절 + 관측 계약

- 상태: **Accepted**
- 날짜: 2026-07-19
- 관련: [ADR-0014](0014-auth-authz-boundary.md)(인증/인가 경계) · [ADR-0011](0011-engine-sync-fanout-bridge.md) · [Phase 2 plan](../plans/2026-07-19-m2-phase2-auth-authz.md) · `monitoring.md`·`observability.md`·`secure-coding.md`
- 범위: M2 Phase 2 WS 연결시 인증/인가 **실패 경로**의 종료 지점·상태코드·관측. 정상 경로·권한 해석은 ADR-0014.

## 맥락

[ADR-0014](0014-auth-authz-boundary.md)는 gateway가 `Sec-WebSocket-Protocol`로 JWT를 받아 검증하고 `CheckPermission`으로 연결시 인가한다고 정했으나, **실패 시 연결을 어디서 끊는지**를 두 가지로 함께 언급했다 — "핸드셰이크 차단"(decision 2)과 "WS close 4401/4403"(decision 5). 이 둘은 실제로 **택일 지점**이다:

- **핸드셰이크(HTTP 업그레이드) 단계 거절** → 응답은 HTTP 상태코드(401/403). WS로 업그레이드되지 않는다.
- **업그레이드 후 WS close** → 연결이 수립된 뒤 close code(4401/4403, RFC 6455 application range)로 종료.

브라우저 `WebSocket` API는 HTTP 핸드셰이크 실패를 상세히 노출하지 않고(단순 "connection failed"), close code는 이벤트로 노출한다. 반대로 **운영 관측** 관점에선 정반대다. 무엇을 택하느냐가 보안(DoS)·운영(모니터링)·클라이언트 UX를 가른다.

이 프로젝트의 제약: ① 기존 `RoomHandshakeInterceptor`가 이미 "업그레이드 전 거절"로 무검증 room 플러드를 세션 할당 전에 차단(`secure-coding.md` P2). ② gateway는 OTel javaagent + Istio ambient(ztunnel) 환경 — L7 관측이 1급. ③ 사용자 요구: "회피성이 아닌 근본 해결, 운영/모니터링에 문제없게".

## 결정

1. **인증·인가 실패는 모두 핸드셰이크(업그레이드 전) HTTP로 거절**한다.
   - 인증 실패(토큰 없음/만료/서명·클레임 무효) → **HTTP 401**.
   - 인가 거부(`allowed=false`/`Role UNSPECIFIED`/응답 이상) → **HTTP 403**.
   - `CheckPermission`은 핸드셰이크 인터셉터에서 호출(gateway=VT라 블로킹 I/O 적합). 세션은 인증·인가 통과 후에만 생성된다.
2. **fail-closed**: JWKS 미획득·CheckPermission 타임아웃/에러 → **거절**(fail-open 금지) + 전용 에러 메트릭 발화(무신호 실패 방지).
3. **관측을 1급 산출물로** 배선한다(아래 §관측 계약). 핸드셰이크 HTTP 거절을 택한 근거가 곧 관측이므로 계약을 ADR에 고정한다.
4. **WS close 4401/4403은 "연결 후" 종료 경로로 예약**한다 — 핸드셰이크 통과 후 발생하는 종료(향후 연결중 권한 무효화·토큰 만료 강제 종료, ADR-0014 후속)에서 사용. Phase 2의 주경로는 아니다. 표준 정책위반 1008 병용.

## 대안 비교

| 방안 | 보안(DoS) | 운영 관측 | 클라이언트 UX | 판정 |
|---|---|---|---|---|
| **핸드셰이크 HTTP 401/403** (채택) | ✅ 업그레이드 전 거절 = 세션·스트림 자원 미할당 | ✅ 상태코드가 access log·Istio/Envoy 텔레메트리·Prometheus `http_*{status}`에 노출 — **앱 코드 없이 L7 알림** | △ 브라우저는 4401/4403 미노출("connection failed") → 프론트가 사유 구분하려면 REST 프리체크/로그인 상태로 보완 | ✅ 근본·관측 우위 |
| 업그레이드 후 WS close 4401/4403 | ❌ 무인증/무권한 연결이 잠깐 수립 → 세션 자원 소모, 플러드 표면 | ❌ close code는 WS 프레임 내부 — L7 프록시·access log·표준 HTTP 메트릭 **불가시**, 앱이 별도 계측해야 겨우 집계 | ✅ 사유가 close code로 명확 | ❌ 관측·DoS 열위 |
| 하이브리드(authn=핸드셰이크, authz=close) | △ authz 연결이 잠깐 수립 | △ 절반만 L7 노출 → 대시보드 이원화 | △ 혼재 | ❌ 복잡·일관성 저하 |

핵심 비대칭: **HTTP 상태코드는 인프라(프록시/메시/메트릭)가 공짜로 관측**하지만, **WS close code는 애플리케이션만 안다**. 운영 알림·SLO·이상탐지를 "앱 코드 없이" 걸 수 있느냐가 갈린다.

## 관측 계약 (MANDATORY, gateway)

- **구조화 로그**(key=value): `event=ws_handshake`, `doc_id`, `user`(해시/미노출), `result=ok|authn_fail|authz_denied|backend_error`, `reason`, `role`, `verify_ms`, `check_permission_ms`, `trace_id`. **토큰·비밀번호·PII 절대 비로깅**(`security.md`).
- **메트릭**(Micrometer→Prometheus): `ws_handshake_total{result}` · `jwt_verify_total{result}` · `jwks_refresh_total{result}` · `checkpermission_duration`(히스토그램) · `authz_backend_error_total`.
- **트레이스**: gateway OTel javaagent가 `CheckPermission` gRPC를 자식 span으로 자동 계측, W3C traceparent 전파(가드레일 4) — 폴리글랏 단일 trace 유지.
- **알림 후보**(M5 실배선, 지금은 계약): 401/403 rate 급증(공격/클라이언트 버그) · `authz_backend_error_total>0`(doc-service/JWKS 불가 → fail-closed로 전 연결 거절, **page 대상**) · JWKS refresh 실패 지속.

## 결과

- Phase 2 실패 경로 확정: authn=401·authz=403(핸드셰이크), fail-closed, close code=연결후 예약.
- proto·ADR-0014 무변경(실패 처리 세부 결정의 보강). ADR-0014 decision 2/5의 모호성 해소.
- 운영 대시보드/알림을 상태코드 기반으로 설계 가능(앱 계측 최소).

## 트레이드오프 (인정)

- **브라우저가 4401/4403을 못 봄** → 프론트가 실패 사유(인증 vs 인가)를 구분하려면 로그인 상태·REST 프리체크로 보완. MLP 수용(연결 실패=재로그인/권한없음 안내).
- **CheckPermission을 핸드셰이크 동기 경로에 둠** → doc-service 지연이 핸드셰이크 지연으로 전파. VT + timeout + `checkpermission_duration` 관측으로 관리, 상한 초과=fail-closed 거절.
- **fail-closed** → doc-service/JWKS 장애 시 전 신규 연결 거절(가용성 희생). 보안·일관성 우선(무권한 통과보다 거절), `authz_backend_error_total` 알림으로 즉시 가시화.
