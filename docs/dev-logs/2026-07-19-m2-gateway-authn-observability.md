---
date: 2026-07-19
category: decision
tier: 2
importance: major
status: resolved
tags: [m2, phase2, ws-gateway, auth, jwt, observability, micrometer, nimbus, spring-websocket, handshake]
related:
  - plans/2026-07-19-m2-phase2-auth-authz.md
  - adr/0021-ws-handshake-auth-failure-observability.md
  - adr/0014-auth-authz-boundary.md
  - adr/0017-jwt-rs256-jwks.md
---

# M2 Phase 2a-1 — gateway WS 핸드셰이크 인증 완성 + 관측 계약 (backend PR #16)

이전 세션이 남긴 **미커밋 WIP**를 검증·완성해 merge-ready로 만든 기록. 핵심 교훈 5건 + 크래프트 게이트 H-1 실증·수정.

## Context

- 산출: [backend PR #16](https://github.com/ressKim-io/weDocs-backend/pull/16)(`19d7716`) — WS 핸드셰이크 RS256 JWT 검증 + 관측 1급(ADR-0021). 69 테스트 green, 크래프트 게이트(☕ 2-렌즈) BLOCKING 0.
- 진입 시 controller plan은 2a-1을 "미착수"로 표기했으나, **backend 브랜치 `feature/m2-phase2a1-gateway-authn`에 ~90% 구현이 스테이징(미커밋) WIP로 존재**했다.

## 교훈

### 1. ⚠️ WIP 드리프트 — plan 상태 ≠ 서비스 레포 실제 상태
- controller plan/CLAUDE.md는 "다음=2a-1 착수"였으나 backend 브랜치엔 2a-1 코드가 이미 있었다(이전 세션이 커밋 전 종료).
- **교훈**: 세션 시작 시 plan만 믿지 말고 **서비스 레포 `git status`/`git branch`를 먼저 확인**. 재개 지점은 "다음 할 일"을 서비스 레포 브랜치 상태와 대조해야 정확. (2026-07-17 retrofit 드리프트와 동류 — 별세션 진행분이 controller에 반영 안 됨.)

### 2. Micrometer counter → Prometheus `_total` 렌더링 (config-contract)
- 카운터 base name은 dot(`ws.handshake`)로 등록하면 Prometheus는 underscore + **`_total` 접미**를 붙여 `ws_handshake_total`으로 낸다. base name에 `_total`을 직접 넣으면 `_total_total` 이중 접미 함정.
- **검증**: `PrometheusMeterRegistry.scrape()` 출력에 `ws_handshake_total{result="ok"}`가 실재하는지 테스트로 고정(`AuthMetricsTest`). 이름이 바뀌면 대시보드/알림이 조용히 깨지므로 계약을 스크레이프로 회귀 가드.
- 카디널리티: `result` 태그만(고정 enum 값) — user/docId를 태그로 쓰지 않아 폭증 없음.

### 3. Nimbus `JWKSourceBuilder` 기본값 검증 + jwks_refresh 계측 seam
- `create(url).build()` 기본 = **5분 캐시 + 만료 30초 전 백그라운드 갱신(별도 스레드) + 30초 rate-limit** — WebFetch(connect2id 공식) + 10.9 jar 바이트코드로 이중 검증. → Q3 "키 회전 무중단" 근거 정합. (`retrying(true)`만 추가, 기본 스택 보존.)
- **`jwks_refresh_total` 계측**: 이벤트 리스너는 레이어별(caching/rateLimited/retrying/outageTolerant)로 **분산**돼 단일 refresh 리스너가 없다(`javap`로 확인). → **`create(URL, ResourceRetriever)`에 `MeteredResourceRetriever` 데코레이터**를 끼워 실제 URL fetch만 계측(캐시 히트는 retriever를 안 탐 → fetch=refresh만 정확히 셈). 버전 안정적이고 이벤트 클래스 계층 커플링 없음.
- **nimbus 10.9 발급측 정합**: gateway 명시 핀(10.9)이 doc-service가 `oauth2-resource-server` BOM으로 해석하는 값과 일치하는지 `./gradlew :doc-service:dependencies`로 실측(config-contract-audit 3단계).

### 4. 🔴 H-1 — Spring 핸드셰이크 순서상 auth가 Origin 검사보다 먼저 → ok 오집계 (실증→수정)
- **증상**: 유효 JWT + 비허용 Origin이 `ws_handshake_total{ok}`를 증가시킴(실제 응답은 403). ADR-0021 전제(앱 신호=상태코드) 위반.
- **원인**: Spring `WebSocketHttpRequestHandler`는 `applyBeforeHandshake`(커스텀 인터셉터 Room→Auth) → (통과 시) `HandshakeHandler.doHandshake`(Origin 검사=`setAllowedOrigins`) 순. 즉 **Origin 검사가 auth 인터셉터 뒤**라, auth가 `beforeHandshake`에서 낙관적으로 ok를 세면 이후 Origin 403을 못 본다.
- **실증**: 추측 대신 통합테스트에 "evil-origin → `ws.handshake{ok}` 불변" assertion 추가 → **red로 버그 확정**(deep-thinking.md: 검증 우선).
- **실패한 1차 시도(폐기)**: 명시 `OriginHandshakeInterceptor`를 auth 앞에 재배선 → `setAllowedOrigins` auto-wiring과 충돌해 **Origin 방어가 오히려 뚫림**(evil-origin이 세션까지 도달). Spring origin 배선 내부 상호작용은 rabbit hole → 원복.
- **채택 수정**: **ok 집계·로그를 `afterHandshake`로 미룸** — 최종 응답이 4xx가 아닐 때만 `ws_handshake{ok}`. authn_fail·jwt_verify는 인터셉터에서 즉시(정확). `beforeHandshake`↔`afterHandshake`는 같은 요청·스레드의 두 콜백인데 **afterHandshake엔 attributes 맵이 없어** ok-로그 필드(docId/masked user/verify_ms)를 **요청 스코프 ThreadLocal**로 전달(항상 제거 → 누수 없음, VT에서도 요청당 격리).
- **양방향 실증**: evil-origin → ok 불변 + 정상 접속 → ok +1(실 업그레이드 경로, `afterHandshake`는 101 이후라 Awaitility 대기) + 단위테스트(afterHandshake status 101→ok / 403→ok 아님).

### 5. 크래프트 게이트 findings 반영 (BLOCKING 0)
- H-1(위) · `verify_ms` 로그 필드 보강 · **user 마스킹 SHA-256 해시화**(UUID 접두 노출 제거 — 다른 로그의 원문과 대조 역식별 방지, ADR-0021 "해시/미노출") · **config fail-fast 회귀 테스트**(`GatewayAuthPropertiesTest`/`AuthConfigTest` — 빈 jwks-uri·잘못된 URI 기동 실패 분기).
- **이월(추적)**: actuator health/prometheus 무인증 노출 → M5 mesh 하드닝 · JWKS-fail vs bad-token `reason` 세분화 → 2a-2(단 `jwks_refresh_total{fail}`로 인프라 다운 구분 가능).

## 재사용 패턴
- **before→afterHandshake 상태 전달 = ThreadLocal**(afterHandshake에 attributes 없음). 종단 결과(성공/거절)를 응답 상태코드로 판정하는 관측은 afterHandshake에서.
- **외부 라이브러리 "명시 안 한 기본값"은 WebFetch+바이트코드로 검증 후 주석에 근거**(config-contract-audit). 계측 seam이 이벤트API로 안 나오면 데코레이터로 감싼다.
- **관측 이름 계약은 실제 렌더링(scrape) 출력으로 테스트 고정**.
