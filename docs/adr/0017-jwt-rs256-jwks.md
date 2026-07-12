# ADR-0017 — JWT 서명 알고리즘: RS256 비대칭 + JWKS 배포

- 상태: **Accepted**
- 날짜: 2026-07-12
- 관련: [ADR-0014](0014-auth-authz-boundary.md)(발급/검증 위치) · [PRD §5](../prd/4-data-and-permission-model.md)(JWT 인증 MLP) · SDD §8 · [M2 1c plan](../plans/2026-07-12-m2-phase1c-rest-jwt.md)
- 범위: JWT **서명 방식·키 배포**. 발급/검증 위치·전달 채널·TTL은 ADR-0014가 SSOT(변경 없음). 키 로테이션 자동화 = 후속.

## 맥락

ADR-0014는 "발급=doc-service, WS 검증=gateway, REST 검증=doc-service(self)"까지 확정했지만 **서명 알고리즘과 검증자에게 키를 어떻게 배포하는지**는 미지정이었다. M2 Phase 1c(발급 구현) 착수 시점에 확정해야 Phase 2(gateway 검증)·M5(클러스터 배포)가 재작업 없이 이어진다.

제약/전제: 검증자가 늘어난다 — Phase 2 gateway(Java), M5에서 Istio 메시 레벨 검증(`RequestAuthentication`) 가능성, 후속 인증 서비스 분리(SDD §15). 사용자 방향: "단순·빠른 것보다 근본적 보안 방식, K8s에서 Istio 같은 인프라가 관리한다는 가정까지."

## 결정

1. **RS256(RSA 2048) 비대칭 서명.** 개인키는 **doc-service만** 보유(발급 단독 권한). 검증자는 공개키만 갖는다 — 어떤 검증자도 토큰을 위조할 수 없다.
2. **공개키 배포 = JWKS 표준 엔드포인트** `GET /.well-known/jwks.json`(RFC 7517, 무인증 공개). 검증자는 키를 복사·배포받지 않고 `jwksUri`로 가져온다:
   - Phase 2 gateway: Spring `NimbusJwtDecoder.withJwkSetUri(...)`
   - M5 Istio: `RequestAuthentication.jwtRules[].jwksUri` — 메시가 검증을 대행하는 경로가 열림
3. **`kid` = RFC 7638 JWK thumbprint** — 키 로테이션 시 신·구 키를 JWKS에 병존시켜 무중단 전환 가능(로테이션 자동화 자체는 후속).
4. **개인키 주입**: `wedocs.doc-service.jwt.private-key-location`(Spring `Resource`, PKCS#8 PEM — M5에선 K8s Secret 파일 마운트). **미설정 시 시작 때 임시 키 생성 + WARN**(로컬 dev 전용 — 재시작 시 기존 토큰 무효). prod 배포 시 Secret 주입 강제화는 M5 매니페스트 몫으로 추적.
5. claims 최소화: `sub`(user_id)·`iss`·`iat`·`exp`·`system_role`. email/표시이름 미포함(토큰 PII 최소화, ADR-0016 system_role은 후속 admin 가드 대비).

## 대안 비교

| 방안 | 위조 가능 주체 | 키 배포 | 검증자 확장(Istio·신규 서비스) | 운영 비용 | 판정 |
|---|---|---|---|---|---|
| **RS256 + JWKS** (채택) | doc-service만 | jwksUri 표준 — 복사 불요 | ✅ `RequestAuthentication` 그대로 연결 | 키쌍 관리(Secret 1개) | ✅ 발급 권한 단독화 + 표준 배포 |
| HS256 공유 시크릿 | **시크릿 보유 전원**(gateway 포함) | 검증자마다 시크릿 복사 | ❌ Istio에 대칭키 배포 = 비표준·위험 | 최소 | ❌ 검증자=발급자 동격, 유출 반경 큼 |
| RS256 + 공개키 정적 배포(PEM 복사) | doc-service만 | 검증자마다 파일 배포·로테이션 시 전원 재배포 | △ 가능하나 수동 | 중 | △ JWKS 대비 이점 없음 |
| EdDSA(Ed25519) | doc-service만 | JWKS 동일 | △ 지원 매트릭스 확인 필요(Istio/Envoy·라이브러리별 상이) | 소 | △ 성능 이점 있으나 생태계 호환 검증 비용 — RS256이 최광폭 호환 |

**HS256을 기각한 결정적 이유**: ADR-0014에서 gateway는 이미 `user_id`를 신뢰받는 지점이지만, 그것은 **mTLS 내부 경계**의 신뢰다. 서명 시크릿 공유는 그와 별개로 **토큰 발급 권한 자체**를 복제한다 — 검증자가 늘수록(M4 ai-service, M5 Istio) 유출 반경이 선형 증가한다. 비대칭이면 발급 권한은 구조적으로 doc-service에 고정된다.

## 결과

- doc-service 1c: Nimbus JOSE(Spring Security oauth2-resource-server 스타터 경유)로 발급(`NimbusJwtEncoder`)+자가 검증(메모리 공개키 `JwtDecoder`, 자기 HTTP 호출 없음) + `JwksController`.
- Phase 2 gateway: `spring-security-oauth2-resource-server` + `jwk-set-uri=http://doc-service:8081/.well-known/jwks.json` — 코드 최소.
- M5: `RequestAuthentication` + `AuthorizationPolicy`로 메시 레벨 검증 선택지 확보(gateway 앱 검증과 다층).

## 트레이드오프 (인정)

- **RSA 서명 비용 > HMAC** — 로그인(발급)·핸드셰이크(검증)는 저빈도 경로라 수용. 매 요청 REST 검증도 RSA verify는 서명보다 훨씬 저렴.
- **JWKS 엔드포인트 공개** — 공개키는 비밀이 아님(설계상). 단 개인키 자료가 응답에 섞이지 않음을 테스트로 고정(`"d"` 필드 부재 단언).
- **임시 키 dev 폴백** — 재시작 시 토큰 전부 무효 + 다중 replica 불가. 로컬 dev 한정으로 수용, prod 강제화는 M5 추적(SDD §15).
- **키 로테이션 수동** — JWKS·kid로 구조는 마련했으나 자동화(이중 키 게시·전환 스케줄)는 후속.
