---
paths:
  - "**/istio/**"
  - "**/*virtualservice*"
  - "**/*authorizationpolicy*"
  - "**/*peerauthentication*"
  - "**/*destinationrule*"
  - "**/*gateway*"
  - "**/*requestauthentication*"
---

# Istio Rules

Istio 리소스(VirtualService, AuthorizationPolicy, PeerAuthentication, DestinationRule, Gateway, RequestAuthentication) 작성/수정 시 반드시 준수.
실전 트러블슈팅 기록 + 보안 외부 검증에서 추출한 실전 규칙.

---

## VirtualService

- MUST destination host는 FQDN 사용 (`.svc.cluster.local`)
  - 예: `user-service.app-ns.svc.cluster.local` (O)
  - 예: `user-service.app-ns.svc` (X) — Gateway pod에 DNS search domain 없어 503 발생
  - 근거: cross-namespace routing 503 사고 (Istio Gateway는 routing pod의 DNS search domain을 사용하므로 short name 사용 시 미해결)

---

## PeerAuthentication

- MUST `portLevelMtls` 사용 시 `spec.selector` 반드시 포함
  - selector 없으면 namespace-wide 적용 → 의도하지 않은 워크로드에 영향
  - 근거: 2026-04-08 Prometheus scrape 503 사고 (모든 pod에 PERMISSIVE 적용됨)
- Prometheus scrape 허용 시 해당 port에만 PERMISSIVE + AuthorizationPolicy로 모니터링 NS 접근 제한

---

## AuthorizationPolicy

### 경로 매칭
- `abc*` prefix 매칭은 `abc` 자체도 포함 (zero-or-more characters)
- 정밀 매칭 필요 시 URI template 사용 (Istio 1.22+):
  - `{*}` — 단일 path segment: `/api/{*}` = `/api/users` (O), `/api/users/123` (X)
  - `{**}` — 다중 path segment: `/api/{**}` = `/api/users/123/orders` (O)
- PREFER positive-matching(ALLOW) > negative-matching(DENY) — DENY 규칙은 normalization 우회에 더 취약

### 규칙 구조
- 동일 `from` 절은 merge — 별도 entries는 OR 로직으로 동작하므로 의도치 않게 허용 범위 확대 가능
- port-only 규칙(15020/15090) 작성 시 path/method 제약도 함께 명시 — Envoy admin stats 노출 방지

### Retry + Idempotency
- NEVER non-idempotent(POST, DELETE, PATCH) 작업에 `retryOn: 5xx` 설정
  - Istio 1.24+ 기본 retry 정책은 503 제외 (EXCLUDE_UNSAFE_503_FROM_DEFAULT_RETRY)
  - 그러나 VirtualService에 명시적 `retryOn: 5xx` 설정 시 기본 정책 무시됨
  - 안전한 retryOn: `reset,connect-failure` (요청이 서버에 도달하지 않은 경우만)
  - 근거: 2026-04-03 결제 중복 사고

---

## RequestAuthentication

- `forwardOriginalToken: true` 사용 시 **보안 경고**:
  - Token relay 공격 — upstream 서비스 침해 시 원본 JWT 탈취
  - Scope 누출 — gateway용 JWT claims가 내부 서비스에 전달
  - PREFER `outputPayloadToHeader`로 verified claims만 전달
  - 불가피한 경우 mTLS identity(SPIFFE)로 service-to-service 인증 병행

---

## Path Normalization (보안 필수)

- MUST `meshConfig.pathNormalization.normalization: DECODE_AND_MERGE_SLASHES` 설정
- 미설정 시 우회 가능한 공격:
  - Double slash: `//admin` → `/admin` 정책 우회
  - Encoded slash: `%2F`, `%5C` → path 분리 우회
  - Fragment: `/profile#section` → path 필터 우회
  - Path parameter: `;param=value` → 경로 인식 변조
- 근거: CVE-2021-39156, ISTIO-SECURITY-2021-005, ISTIO-SECURITY-2021-008

---

## Sidecar Startup

- K8s 1.28+에서 PREFER `ENABLE_NATIVE_SIDECARS=true` (istiod 설정)
  - Native sidecars: K8s가 init container 시작 순서 보장 → startup race 제거
  - 설정 시 `holdApplicationUntilProxyStarts`, `terminationDrainDuration` 모두 불필요
- Native Sidecars 미사용 환경: probe `initialDelaySeconds` +5~10s 조정 필요

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| VirtualService destination에 short name 사용 | Gateway pod DNS 해결 실패 → 503 |
| PeerAuthentication `portLevelMtls` + selector 누락 | namespace/mesh-wide 의도치 않은 적용 |
| POST/DELETE에 `retryOn: 5xx` | 중복 트랜잭션 (결제 이중 청구 등) |
| `meshConfig.pathNormalization` 미설정 | AuthorizationPolicy 보안 우회 가능 |
| `forwardOriginalToken: true` 경고 없이 사용 | Token relay 공격 표면 |
