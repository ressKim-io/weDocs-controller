---
date: 2026-07-12
slug: m2-phase1c-rest-jwt
status: in-progress
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0014-auth-authz-boundary.md
  - adr/0017-jwt-rs256-jwks.md
  - prd/4-data-and-permission-model.md
  - dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md
---

# M2 Phase 1c — doc-service REST + JWT 발급 (RS256/JWKS)

> M2 세션 plan([2026-06-30-m2-persistence-session.md](2026-06-30-m2-persistence-session.md))의 Phase 1c 하위 실행 plan.
> 이 파일이 영구 SSOT. harness plan: `~/.claude/plans/synchronous-painting-rossum.md`(휘발성).
> 실제 코드는 **weDocs-backend 레포**에서 branch+PR+건별 승인. controller(이 plan·ADR-0017)만 main 직접.

## Context

M2 Phase 1a(스키마·엔티티)·1b(gRPC 4 RPC)는 머지 완료. doc-service엔 아직 **클라이언트向 진입점이 없다** — 계정도, 토큰도, 페이지를 만들 방법도 없다. 1c는 SDD §3.3의 REST 표면(인증·워크스페이스·멤버·페이지 트리)과 ADR-0014의 "JWT 발급=doc-service"를 구현해, Phase 2(gateway 검증)·Phase 6(권한 E2E)의 전제를 만든다.

**proto 변경 없음**(REST는 클라이언트向, ADR-0014). **DB 스키마 변경 없음**(V1 7테이블에 모든 컬럼 존재 — 신규 Flyway 마이그레이션 0).

### 사용자 확정 결정 (2026-07-12)

| 결정 | 채택 | 근거 |
|---|---|---|
| JWT 서명 | **RS256 비대칭** + **JWKS 공개 엔드포인트**(`/.well-known/jwks.json`) | 사용자: "단순 빠른 것 말고 근본적 보안". doc-service만 개인키 보유, 검증자(gateway Phase 2, Istio `RequestAuthentication` M5)는 `jwksUri`로 공개키만. 상세 = [ADR-0017](../adr/0017-jwt-rs256-jwks.md) |
| 범위 확장 | **회원가입 API** + **페이지 공유 API** 포함 | signup 없으면 로그인 불가·E2E 불가. 공유 API 없으면 PagePermission을 채울 경로 없음(PRD §5 MLP) |
| PR 분할 | **2 PR** — PR① 인증 기반 → PR② 리소스 REST | 규모(프로덕션+테스트 ~1,800줄)가 1 PR 리뷰 한계 초과 |

## PR① `feature/m2-doc-service-auth-jwt` — 인증 기반 + signup/login

**의존성**(1a 함정 원칙 — 전용 스타터만, 베어 라이브러리 금지): `spring-boot-starter-webmvc` · `spring-boot-starter-security` · `spring-boot-starter-security-oauth2-resource-server`(Nimbus JOSE — 발급 `NimbusJwtEncoder`/검증 `NimbusJwtDecoder` 겸용) · `spring-boot-starter-validation`. ⚠️ Boot 4.1 BOM에 신·구 좌표 공존(`starter-web`↔`starter-webmvc` 등) — 구현 첫 단계에서 dependency 해소 실측으로 신좌표 확인.

**키 관리**: `JwtProperties`(@ConfigurationProperties `wedocs.doc-service.jwt.*`: `private-key-location`(Spring `Resource`)·`ttl` 24h(ADR-0014)·`issuer`) / `JwtKeys`(PEM PKCS#8 로드, 미설정 시 **임시 RSA 2048 생성+WARN** — dev 전용, prod는 M5 Secret 주입, 근거 주석+SDD §15 추적) / `kid`=RFC 7638 thumbprint / 발급 claims `sub`·`iss`·`iat`·`exp`·`system_role`(PII 최소화 — email/이름 미포함) / 자가 검증=메모리 공개키 직결 `JwtDecoder` / `JwksController`(`GET /.well-known/jwks.json`, 공개키만 — `"d"` 부재 테스트).

**보안 배선**: `SecurityConfig` stateless+기본 거부(`anyRequest().authenticated()`), permitAll=`/api/auth/**`·jwks, CSRF disable(근거: 쿠키 미사용 Bearer 전용), CORS localhost dev 화이트리스트(P5, `*` 금지) / `PasswordEncoder`=`DelegatingPasswordEncoder`(bcrypt) / `@CurrentUserId UUID` resolver(경계 1회 변환, design-patterns P6).

**Auth API + 예외 기반**: `POST /api/auth/signup`(201, `User.register` 정적 팩토리, 중복 409, password `@Size(min=8,max=72)`=bcrypt 72바이트 한계) / `POST /api/auth/login`(200 {accessToken,tokenType,expiresInSeconds}, **미존재 email=비번 불일치=동일 401** — 계정 존재 비노출 P4) / 예외 계층: `DomainException`(abstract) ← `ResourceNotFoundException`(404)·`DuplicateResourceException`(409)·`InvalidCredentialsException`(401)·`ForbiddenException`(403), 기존 `PageNotFoundException`은 `extends ResourceNotFoundException` 편입 / `GlobalExceptionHandler`=**ProblemDetail**(RFC 9457) 일관.

**테스트(TDD)**: `JwtTokenServiceTest`(라운드트립·claims·만료) · `JwtKeysTest`(PEM vs 임시) · `AuthFlowIntegrationTest`(Testcontainers+MockMvc: signup→login→보호 접근, 중복 409, 동일 401, 무토큰 401, jwks 공개키만) + 기존 32개 회귀 green(test yml 완전 대체 함정 재확인).

## PR② `feature/m2-doc-service-rest-pages` — 리소스 REST (PR① 머지 후 분기)

```
POST   /api/workspaces {name}                        201  인증만 — 생성자를 owner 멤버로 같은 tx 등록
GET    /api/workspaces                               200  내 멤버십 워크스페이스 목록
POST   /api/workspaces/{id}/members {email}          201  ws owner만. 대상 미존재 404, 중복 409
GET    /api/workspaces/{id}/pages                    200  멤버만. flat 목록(트리는 클라 조립), 조회 cap 명시(P2)
POST   /api/pages {workspaceId, parentId?, title}    201  parent 있으면 parent에 ≥editor, 루트면 ws 멤버
GET    /api/pages/{id}                               200  유효권한 ≥viewer — 아니면 404(존재 비노출, 1b 원칙)
PATCH  /api/pages/{id} {title}                       200  ≥editor
POST   /api/pages/{id}/move {parentId?, position}    200  ≥editor + 사이클 검사 + 동일 workspace 강제
DELETE /api/pages/{id}                               204  아카이브(D-4: editor 허용. 영구삭제 비범위)
PUT    /api/pages/{id}/permissions/{userId} {level}  204  ws owner만(PRD §4.3). 대상=존재 유저(비멤버 공유 허용 — PRD §4.2 1순위)
DELETE /api/pages/{id}/permissions/{userId}          204  ws owner만
```

**핵심 설계**: 인가=기존 1b `PermissionService.resolve()` 재사용(권한 해석 단일 소유), `EffectivePermission`에 `canRead()`/`canEdit()` 부착(Tell Don't Ask) / 가드: `PageAccessGuard`(no-read→404 비노출, viewer edit→403)·`WorkspaceAccessGuard`(비멤버→404, owner 요구→403) / **트리 이동**(PRD §3): 단일 tx에서 **workspace 행 `PESSIMISTIC_WRITE` lock**으로 워크스페이스 내 이동 직렬화(동시 교차 이동 사이클까지 차단 — 이동은 드묾, 조대 락 수용, 근거 주석) → 새 parent에서 상향 `MAX_ANCESTOR_DEPTH=64` 캡 탐색(fail-closed), 자기/자손이면 `PageCycleException`(409) / 도메인 행위: `Page.moveTo`/`Page.archive`/`Workspace.create`/`WorkspaceMember.owner|member` 정적 팩토리 / 서비스: `WorkspaceService`·`PageTreeService`·`PageSharingService`(단일 책임 분리), 클래스 `@Transactional(readOnly=true)`+쓰기 오버라이드.

**테스트(TDD)**: `PageTreeServiceTest`(사이클 단위) · `WorkspaceIntegrationTest` · `PageTreeIntegrationTest`(생성/이동/사이클 거부/교차 ws 거부/아카이브 제외) · `PageSharingIntegrationTest`(비멤버 공유 GET 성공·PATCH 403, 상속, 회수) + 인가 매트릭스.

## 크래프트 게이트 [B] 사전 매핑

- **P1**: 전 요청 DTO record + Bean Validation(길이·형식·`@Email`), UUID 경계 변환
- **P2**: 페이지 목록 cap · signup 무상한 계정 = rate-limit 인그레스 몫(M5) 근거 주석+SDD §15 추적([A])
- **P3**: 기본 거부 + 엔드포인트마다 가드 · IDOR=404 비노출
- **P4**: ProblemDetail 분류만 · login 단일 401 · JWKS 개인키 부재 테스트
- **P5**: CSRF/CORS/임시키 근거 주석 · 아웃바운드 gRPC 없음(deadline 해당 없음)
- **계층/패턴**: Controller→Service→Repo · 엔티티 API 비노출 · 정적 팩토리 · 빈 `new` 금지

## 실행 체크리스트

- [x] controller: 이 plan 커밋(planned, `2bc3235`) + ADR-0017 작성·커밋(`6960d01`)
- [x] PR① 브랜치 분기 + 의존성 신좌표 실측 검증 커밋 (`60db0ec`)
- [x] PR① Stage A — JwtKeys/JwtProperties/JwtTokenService (TDD, `eadaf38`)
- [x] PR① Stage B — SecurityConfig + PasswordEncoder + CurrentUserId resolver + JwksController (TDD, `496a61f`)
- [x] PR① Stage C — 예외 계층 + GlobalExceptionHandler + AuthService/AuthController (TDD, `a8b8c6e`) + TC 2.x deprecated 전수 정리(`3b89975`)
- [x] PR① 전체 테스트 green + 크래프트 게이트(java-expert+code-reviewer 병렬) + 반영(`bfdf5f4`) — [B] 1건(비밀번호 72바이트 vs @Size 문자 수→한글 500)·MEDIUM 5건(레이스 409·이메일 정규화·test yml 미러·wireValue 단일화·리졸버 테스트)·[A]/LOW 7건 반영, 최종 53건 green
- [x] PR① 사용자 승인 후 push·[PR #7](https://github.com/ressKim-io/weDocs-backend/pull/7) 오픈 (2026-07-13)
- [x] PR① 리뷰 반영 → 승인 후 **머지 완료** (2026-07-13, squash `a7e3a27`)
- [x] **선행: backend main security-scan 적신호 해소 ✅** (2026-07-17, [PR #8](https://github.com/ressKim-io/weDocs-backend/pull/8) squash 머지 `2290ce0`) — fingerprint→allowlist 전환. 4레포 전 트리거 green. plan = [2026-07-17-gitleaks-false-positive-baseline.md](2026-07-17-gitleaks-false-positive-baseline.md)(done)
- [ ] PR② 브랜치 분기(①머지 후) — 가드/도메인 행위 (TDD)
- [ ] PR② Workspace REST (TDD)
- [ ] PR② Page tree REST + move 사이클 검사 (TDD)
- [ ] PR② Page sharing REST (TDD)
- [ ] PR② 전체 테스트 green + 크래프트 게이트 + 수정
- [ ] PR② 사용자 승인 후 push·PR 오픈 → 리뷰 반영 → 승인 후 머지
- [ ] 마감: plan done + M2 세션 plan 재개지점 갱신(다음=secure-coding retrofit→Phase 2) + CLAUDE.md 갱신 + dev-log(신규 함정 시)

## 검증

- 단위: `./gradlew :doc-service:test --tests "*JwtTokenServiceTest"` 등(DB 불필요)
- 통합: `./gradlew :doc-service:test`(Testcontainers) — 신규 + 기존 32개 전부 green
- 빌드: `make proto-gen && ./gradlew :doc-service:build`
- 수동 스모크: `bootRun` 후 curl — signup→login→ws 생성→페이지 생성→이동 사이클 거부(409)→jwks.json
- 게이트: PR마다 크래프트 6종 [B] 체크리스트(java-expert)+code-reviewer → findings 사용자 표시 후 반영

## 범위 밖

- gateway JWT 검증·WS 인증(`Sec-WebSocket-Protocol`)·viewer write-drop = **Phase 2**
- 엔진 스냅샷 저장/복원 = Phase 3/4 · outbox 배선(페이지 변경 insert 포함) = Phase 5
- refresh token(재로그인 대체, ADR-0014 24h TTL) · 키 로테이션 자동화 · admin 전용 API(ADR-0016) · rate limiting(M5 인그레스) · 페이지 영구삭제 · 멤버 role 변경/제거 API

## 머지 후 발견 — gitleaks 오탐 2건 + fingerprint 무효화 (2026-07-17 확인)

PR① 머지(`a7e3a27`) 직후 **backend main의 security-scan이 적신호**. 실제 키 유출은 **없음** — 커밋된 키 자료 0, 전부 PEM 마커 문자열 리터럴 오탐.

| # | 위치 | 실체 | 판정 |
|---|---|---|---|
| 1 | `JwtKeys.java:60-75` | PKCS#8 파서의 `.replace("-----BEGIN PRIVATE KEY-----", "")` + 에러 메시지(L75) | 오탐 — 키 자료 없음 |
| 2 | `JwtKeysTest.java:61-77` | fail-fast 테스트 더미(`"not-a-key"`) + 런타임 생성 키 조립 헬퍼(L77) | 오탐 — 키는 테스트 런타임 생성 |

**근본 원인 = squash 머지가 fingerprint를 재작성**. gitleaks fingerprint는 `<commit>:<path>:<rule>:<line>` 구조인데, `.gitleaksignore`에 브랜치 커밋 `eadaf38`로 핀했다 → squash로 main 커밋이 `a7e3a27`이 되며 **엔트리 즉시 사망**. PR CI는 green(fingerprint 일치) → 머지 직후 main red. **게이트가 false pass를 준 것** — 커밋 핀 방식은 squash 머지 레포에서 구조적으로 깨진다.

부수 확인: `.gitleaksignore`는 #2만 덮었고 #1은 미등록(PR 스캔은 커밋별 diff라 미검출, main의 squash 통합 diff에서 발현).

**동종 사례 — controller 자신도 적신호**: 주간 schedule 스캔(전체 히스토리)이 **최초 실행부터 계속 red**(2026-07-05·07-12). `.claude/agents/gitops-reviewer.md:242`(`password: <base64>` 예시)·`.claude/skills/service-mesh/istio-core.md:243`(산문) `generic-api-key` 오탐 2건, 출처 커밋 `5ce132c`(2026-06-25). push 스캔은 마지막 커밋만 봐서 green → **주간 스캔 red를 아무도 못 봄**. engine·frontend는 green.

→ 교훈: 게이트를 배선했으면 **오탐 베이스라인까지 green으로 만들어야** 게이트다. red가 상시화되면 신호가 죽는다([craft-standards-gate-activation] 메모리의 "커밋 전 게이트 시뮬레이션" 원칙이 schedule 트리거에는 미적용됐던 갭).

## 재개 지점 (Resume)

> **마지막 완료**: PR① = [backend PR #7](https://github.com/ressKim-io/weDocs-backend/pull/7) **머지 완료**(2026-07-13, squash `a7e3a27` — 커밋 6개 `60db0ec`~`bfdf5f4` 압축, 크래프트 게이트 2-리뷰 반영, 53건 green). Boot 4.x 함정 3건 dev-log = [2026-07-13-m2-doc-service-1c-boot4-traps.md](../dev-logs/2026-07-13-m2-doc-service-1c-boot4-traps.md).
> **다음**: **PR② `feature/m2-doc-service-rest-pages` 분기** — 가드/도메인 행위→workspace→page tree/move→sharing (이 plan §PR② 참조. 설계 확정 — 신규 결정 불필요, 구현만). ~~선행 security-scan 적신호~~ = **해소 완료**(2026-07-17, PR #8 `2290ce0` — 4레포 전 트리거 green).
> **주의**: 서비스 레포는 건별 승인(push·PR). **Boot 4.x 함정 3건**: ① `@WebMvcTest` = `spring-boot-starter-webmvc-test` 별도 스타터 + 패키지 `org.springframework.boot.webmvc.test.autoconfigure`로 이동 ② Jackson 3 전환 — 패키지 `com.fasterxml.jackson`→`tools.jackson`, `asText()`→`asString()` ③ TC 2.x 신클래스 `org.testcontainers.postgresql.PostgreSQLContainer`는 비제네릭(self-type 제거). test application.yml은 main 완전 대체 — 신규 main 키는 test에도 명시(problemdetails 적용함). **신규**: `.gitleaksignore` 커밋 핀은 squash 머지에서 무효 — 오탐 억제는 경로/룰 기반으로.
