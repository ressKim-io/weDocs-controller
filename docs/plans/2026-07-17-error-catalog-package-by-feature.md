---
date: 2026-07-17
slug: error-catalog-package-by-feature
status: in-progress
related:
  - plans/2026-07-12-m2-phase1c-rest-jwt.md
  - plans/2026-07-03-secure-coding-retrofit.md
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0018-error-catalog.md
  - adr/0019-package-by-feature-java.md
  - adr/0020-data-access-conventions.md
---

# 크래프트 표준 확장(에러 카탈로그·package-by-feature) + doc-service 구조 리팩토링

## Context

사용자 문제 제기: 코드 구조/규칙을 초기에 안 잡아서 읽기 힘들다 — ① 표준·모범사례를 찾아 skill/구조로 적용, ② 아키텍처 패턴(정적 팩토리 등) 적용, ③ JPA 단순화·FK 결합 최소·샤딩 확장성·QueryDSL 판단, ④ Claude 모델 티어링(리뷰=sonnet) 판단. 그 후 기존 코드 리팩토링.

**실측 결과 (탐색 완료, 2026-07-17)**: 메서드 길이(최장 24줄)·정적 팩토리·ID-only 연관(`@ManyToOne` 0건)은 **이미 양호**. 진짜 문제는:

- `service/` god-package 22파일 (서비스 7 + 가드 2 + 값객체 + **leaf 예외 12클래스**)
- 에러 매핑 이원화: HTTP `GlobalExceptionHandler`(카테고리 type URI `errors/not-found` 등) vs gRPC `DocServiceImpl.failNotFound`(하드코딩 "page not found") — enum 카탈로그 없음
- `DocMetaService.java:28` raw `IllegalStateException`(내부 id 보간, 계층 우회)
- 샤딩 실결합 = DB 스키마 FK `ON DELETE CASCADE`(Flyway V1). QueryDSL 필요 복잡 쿼리는 아직 없음
- 표준 갭: error-handling.md에 카탈로그 룰 없음, layering-readability.md에 패키지 조직 룰 없음, spring.md `ErrorResponse(code,message,timestamp)` 조항이 ProblemDetail 실무와 모순, effort-guide/token-budget은 Opus 4.7 기준 stale
- 모델 티어링은 이미 현업 패턴(리뷰·언어 expert=sonnet / architect·tech-lead·debugging·rust=opus+max / git-workflow=haiku)

## 사용자 확정 결정 (2026-07-17)

1. **순서**: ① 표준(controller) → ② 1c findings 소PR → ③ 구조 리팩토링 PR ×3 → ④ secure-coding retrofit → ⑤ Phase 2
2. **패키지**: doc-service **package-by-feature** 재편 (feature 내부 평면, 계층 서브패키지 금지)
3. **에러**: **카테고리 예외 4~5종 + per-service ErrorCode enum** (leaf 12클래스 → enum 흡수, HTTP·gRPC 매핑 enum 일원화)
4. **모델**: 배정 현행 유지 + stale 문서(effort-guide/token-budget) 현행 세대로 갱신 + "리뷰=sonnet으로 충분" 판단 문서화

---

## Step ① — controller 표준 작업 (main 직접, 논리 커밋 분할)

### ①-1 WebFetch 사전 검증 (deep-thinking 룰 — 룰 작성 전)

RFC 9457(type/detail 의미) · Spring ProblemDetail 현행 문서 · Google AIP-193 · gRPC status codes(FAILED_PRECONDITION vs ABORTED vs ALREADY_EXISTS) · Spring Modulith/package-by-feature 출처 · **Anthropic 현행 모델 라인업·effort 지원표·캐시 수치**(effort-guide 갱신용 — 단정 금지, 확인 불가 항목은 수치 삭제)

### ①-2 게이트 시뮬레이션 (룰 커밋 전)

신규 체크리스트 행을 backend HEAD doc-service에 실행(java-expert). **기대 발화 4종**: leaf 예외 12클래스 / DocMetaService raw IllegalStateException / 이중 매핑(advice 상태 하드코딩 + failNotFound) / 전역 계층 패키지. **오탐 0 확인**: `parseUuidOrFail`(경계 검증) · Bean Validation 400 · 프레임워크 예외 · ws-gateway(비대상).

### ①-3 error-handling.md P7 + spring.md 정합 (커밋)

- **P7**: 서비스(pod)별 `ErrorCode` enum이 slug(kebab)·message(고정 영어, PII/id 보간 금지)·HttpStatus·gRPC Status.Code 보유. 던지기는 카테고리 예외 4~5종(NotFound/Conflict/Forbidden/Unauthorized/InvariantViolation)만 — leaf 예외 증식 금지. HTTP/gRPC 매핑 SSOT = enum 필드(핸들러 하드코딩 금지).
- P2 정합 한 줄 보강: 카탈로그 enum은 "불투명 코드"가 아님 — 카테고리 타입 매칭 + 자기서술 slug = P2의 실현.
- 코드 체계: `DOC-001`류 번호 **기각**(anti-opaque 충돌), 도메인 slug 채택. ProblemDetail: type = `https://wedocs.io/errors/<slug>`(코드 단위로 세분화), property `code` 추가. 5xx는 detail 고정 "unexpected error"(message 미노출).
- 체크리스트 행: `[B]` 도메인 실패 = 카테고리 예외+enum 엔트리만(raw RuntimeException/leaf 신설 금지) · `[B]` HTTP/gRPC 매핑 enum status 경유 · `[A]` 메시지 고정 문구·보간 금지. 경계 입력검증(INVALID_ARGUMENT·Bean Validation)은 명시 제외(오탐 방지).
- **spring.md**: `ErrorResponse(code,message,timestamp)` 조항·샘플 → ProblemDetail + `code` property로 교체, error-handling P7로 위임.

### ①-4 layering-readability.md P7 + git.md (커밋)

- **P7**: 패키지는 기능(도메인) 기준. 전역 `api/`·`service/`·`repository/` 통 패키지 금지. feature 패키지가 자기 api·service·domain·repository를 **평면**으로 보유(package-private 은닉 근거). 공용 최소만 `common/<관심사>/`, 크로스-feature 전송 어댑터(gRPC)는 top-level 허용. 예외·ErrorCode 거처 = `common/error/`.
- 행: `[B]` 신규 프로덕션 파일은 feature 패키지 위치(전역 계층 패키지 신설·비대화 금지) · `[A]` 교차 feature repository 직접 주입 지양(현행 PermissionService→WorkspaceMemberRepository가 걸리므로 [B] 아님).
- **git.md** §Size Limit 단서 1행: move-only 리팩토링 PR은 `git diff -M90%` rename 제외 실질 diff ≤ 400줄로 산정, PR 본문에 선언+검증 명령 명시.

### ①-5 ADR 신설 + README 인덱스 (커밋)

- **ADR-0018 에러 카탈로그 컨벤션**: 대안 비교(번호 코드 / 단일 BusinessException / per-leaf 예외 유지 — 각 기각 사유), wire 포맷, doc-service 12 leaf→11 enum 매핑표.
- **ADR-0019 Java 서비스 package-by-feature**: §③-3 목표 트리 + 배치 근거(guards=소유 feature, JwtTokenService=auth, converter=enum 동거, DTO=feature 평면) + ws-gateway는 비대상(파이프라인형 소형) + Modulith 도입 비목표.
- **ADR-0020 데이터 접근 컨벤션**(슬림): 연관=UUID FK 컬럼만(`@ManyToOne` 금지, 현행 명문화) / DB FK·CASCADE **유지**, 제거는 샤딩 트리거 시 별도 ADR / QueryDSL 채택 기준 = 파생쿼리·JPQL 불가 요구 2건+ 누적 시(지금 채택 안 함).
- 신규 skill은 **만들지 않음** — 게이트 2~3회 운용 후 [A] 처방 구체성 부족하면 그때 신설.

### ①-6 effort-guide·token-budget 갱신 + CLAUDE.md (커밋)

- 두 파일의 Opus 4.7 기준 수치·모델표 전부 현행 세대로 교체(①-1 검증값만 기입). 모델 배정 변경 없음.
- effort-guide에 **티어링 판단 기록**: "리뷰 에이전트 sonnet 유지 — 게이트가 [B]/[A] 기계적 체크리스트 실행이라 sonnet으로 충분, frontier 판단은 opus+max 에이전트로 에스컬레이션."
- CLAUDE.md: stale 경고 제거·두 파일 상황별 룰 편입 / §현재 상태 불릿 + "다음=" ①~⑤ 순서 갱신 / L4 "doc-service 미생성" stale 수정.

### ①-7 meta dev-log (커밋, devlog-lifecycle)

---

## Step ② — backend `fix/m2-1c-gate-findings` 소PR (행동 수정)

상세 스펙 SSOT = `plans/2026-07-12-m2-phase1c-rest-jwt.md` §PR② findings. **소속 확정**:

- **② 포함**: HIGH-1(아카이브 자손 고아) · HIGH-2(move 락 이전 L1 stale + 2-tx 레이스 테스트) · MED-4(테스트 헬퍼 → RestTestSupport 승격, 선행 prep — ②의 신규 테스트가 소비) · MED-5/6(MEMBER 액터·공유 editor 테스트) · MED-7(lock timeout+풀 설정) · LOW 테스트군(share 404·무토큰 401·enum/UUID 400·락 직렬화·listMine 주석)
- **③으로 이월**: MED-3(requireSharableBy 중복) · LOW canRead()=allowed() · LOW MAX_ANCESTOR_DEPTH 중복 — 순수 중복 제거이므로 ③-2 소속
- ⚠️ ②의 에러 응답 단언은 **status 중심**으로 작성(type URI·detail은 ③-1이 재정의 — 교차 churn 방지)

## Step ③ — backend 리팩토링 PR 3분할 (전부 doc-service, ws-gateway 불가침, 순차)

공통: branch → colima 테스트 green → 크래프트 게이트(java-expert 6종+신규 행, code-reviewer) → 결과 사용자 표시 → **건별 승인** push/PR/squash 머지. 행동 변경 금지(③-1 선언 wire 변경 제외).

### ③-1 `refactor/doc-service-error-catalog` (~±270)

`io.wedocs.doc.common.error` 신설: `DocErrorCode` enum(slug·message·HttpStatus·grpc Code) + 카테고리 5종(`DomainException` 루트 유지, 생성자에서 카테고리↔status 정합 assert) + `GlobalExceptionHandler` 이동·단순화(`@ExceptionHandler(DomainException.class)` 중심, type=slug 단위, `code` property, 5xx detail 고정).

| enum | HTTP | gRPC | 흡수 대상 |
|---|---|---|---|
| PAGE_NOT_FOUND / WORKSPACE_NOT_FOUND / USER_NOT_FOUND | 404 | NOT_FOUND | *NotFoundException 3종 |
| EMAIL_ALREADY_USED / DUPLICATE_MEMBER | 409 | ALREADY_EXISTS | 중복 2종 |
| PAGE_CYCLE / PAGE_DEPTH_CAP_EXCEEDED / CROSS_WORKSPACE_PARENT | 409 | FAILED_PRECONDITION | PageCycleException(팩토리 2)·CrossWorkspaceParent |
| INSUFFICIENT_PERMISSION | 403 | PERMISSION_DENIED | ForbiddenException |
| INVALID_CREDENTIALS | 401 | UNAUTHENTICATED | InvalidCredentialsException |
| INVARIANT_BROKEN | 500 | INTERNAL | DocMetaService raw IllegalStateException |

- 서비스 7곳 throw 교체, `DocMetaService:28` → `InvariantViolationException(code, internalDetail)`(owner 임시 매핑 hack 자체는 비범위), `DocServiceImpl`: `catch(DomainException) → Status.fromCode(e.code().grpc()).withDescription(code.message())` 헬퍼로 failNotFound 대체(parseUuidOrFail·failInternal 유지), leaf 12파일 삭제.
- 테스트: type URI 단언 갱신(현행 카테고리 slug → 코드 slug) + `$.code` 단언 추가 + `DocErrorCodeTest`(파라미터라이즈 매핑 검증). 메시지의 uuid 보간 제거로 detail 단언 영향 실행 시 확인.
- **선언 wire 변경**(PR 본문 명시, 소비자=자사 frontend 미소비): type URI 세분화 · `code` property 추가 · detail id 보간 제거.

### ③-2 `refactor/doc-service-dedup` (~150줄)

MED-3: requireSharableBy → `WorkspaceAccessGuard.requireOwner` 재사용 / canRead() → allowed() 위임 / MAX_ANCESTOR_DEPTH 단일 선언 공유. 기존 테스트 green으로 행동 불변 검증.

### ③-3 `refactor/doc-service-package-by-feature` (move-only)

목표 트리(ADR-0019 수록, feature 내부 평면):

```
auth/       AuthController·JwksController·Signup/Login/Token/UserResponse dto·AuthService
            ·User·SystemRole(+Converter)·UserRepository·기존 auth/* 8파일(제자리)
workspace/  WorkspaceController·dto 4·WorkspaceService·WorkspaceAccessGuard
            ·Workspace·WorkspaceMember(+Id)·WorkspaceRole(+Converter)·repo 2
page/       PageController·PageSharingController·dto 5·PageTreeService·PageSharingService
            ·PermissionService·PageAccessGuard·EffectivePermission·DocMetaService
            ·Page·PagePermission(+Id)·PagePermissionLevel(+Converter)·repo 2
snapshot/   SnapshotService·PageSnapshot·PageSnapshotRepository
grpc/       DocServiceImpl·GrpcServerLifecycle (제자리 — 크로스-feature 어댑터)
common/error/ (③-1에서 이미 최종 위치) · common/jpa/ Base*Entity·JpaAuditingConfig · common/validation/ MaxUtf8Bytes*
```

- 테스트 미러 이동 + `RestTestSupport` public 승격(교차 패키지화). 로직 0 변경, 허용 diff = package/import 행 + 최소 가시성 승격(PR 본문 전수 열거). base package 불변 → 컴포넌트 스캔·JPA·Flyway 무영향.
- 검증: `git diff -M90% main...HEAD`로 전 파일 rename 확인 + 비-rename 실질 diff가 가시성 승격뿐임을 grep으로 증명(①-4 git.md 단서 이행).

---

## 검증

```bash
# backend (colima 필수)
DOCKER_HOST=unix://$HOME/.colima/default/docker.sock \
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
./gradlew :doc-service:test   # ② 이후 102+건, ③ 각 PR green
```

- ③ 각 PR: 게이트 리뷰 결과가 ①-2 기대 발화 목록을 **소거**했는지 대조.
- ① 룰: WebFetch 출처+검증일 병기, 게이트 시뮬레이션 발화/오탐 기록.
- 마감: plan `done` + CLAUDE.md 재개지점("다음 = ④ retrofit → ⑤ Phase 2") + dev-log.

## 실행 체크리스트

- [x] ①-0 이 plan 커밋 (`6949c1f`)
- [x] ①-1 WebFetch 검증 완료(2026-07-17): RFC 9457·Spring ProblemDetail·AIP-193·gRPC status·Modulith·Anthropic 모델/effort/캐시 — 전부 설계 정합 확인
- [x] ①-2 게이트 시뮬레이션 (backend `290bf69`, java-expert): 기대 발화 전부 fire·오탐 0·문구 결함 4건 교정 반영(성격 기준 fail-fast·안전망 허용·어댑터 예시·LR-2 backstop), OR 완화 제안은 기각
- [x] ①-3 커밋: error-handling P7 + spring.md 정합 (`9d508f5`)
- [x] ①-4 커밋: layering-readability P7 + git.md move-only 단서 (`317f028`)
- [x] ①-5 커밋: ADR-0018·0019·0020 + README 인덱스(0017 누락 행 포함) (`b3e7083`)
- [x] ①-6 커밋: effort-guide·token-budget 현행화 + CLAUDE.md (`5c4a1a2`)
- [x] ①-7 커밋: meta dev-log = `dev-logs/2026-07-17-error-catalog-package-standards.md`
- [x] ② 구현+게이트 완료(push·PR 승인 대기): `fix/m2-1c-gate-findings` 로컬 커밋 6개(`5048a31`~`389d9fa`), **113건 green**. HIGH-1(도달성 BFS, active-only 예산)·HIGH-2(인가→락→clear, InOrder 결정적 가드)·MED-4/5/6/7·LOW 전부 반영. 게이트 2-렌즈: java-expert [B] 0 · code-reviewer Critical 1(레이스 테스트 판별력 — 실증)+Major 4+Minor 6 → **전부 반영**(MJ-2의 projection 제안은 HIGH-2 재도입이라 기각). MED-3·MAX_ANCESTOR_DEPTH·canRead 위임은 ③-2 몫(계획대로 이월)
- [ ] ② push → PR → 머지 (건별 승인 필요)
- [ ] ③-1 refactor/doc-service-error-catalog → green → 게이트 → 승인 → PR → 머지
- [ ] ③-2 refactor/doc-service-dedup → green → 게이트 → 승인 → PR → 머지
- [ ] ③-3 refactor/doc-service-package-by-feature → 검증 프로토콜 → green → 게이트 → 승인 → PR → 머지
- [ ] 마감: plan done + CLAUDE.md 재개지점 + dev-log

## 재개 지점 (Resume)

마지막 완료 = **Step ① 전체 + Step ② 구현·게이트·리뷰 반영**(backend 로컬 브랜치 `fix/m2-1c-gate-findings` 커밋 6개, 113건 green — 미push). 다음 = **② push·PR 사용자 승인 → 머지 → ③-1 `refactor/doc-service-error-catalog`**. 주의 = ③-1은 머지된 ② 위에서 분기 · ③ 각 PR도 게이트+건별 승인 · ②의 status 중심 단언 유지 확인(type URI는 ③-1이 재정의).

## 범위 밖

QueryDSL/jOOQ 채택 · DB FK/CASCADE 제거(Flyway 무변경) · ws-gateway 구조 변경 · Spring Modulith 도입 · DocMetaService owner 임시 매핑(created_by) 해소 · 에이전트 모델 배정 변경 · 신규 skill 신설 · 가시성 축소 스윕 · ③에서의 행동 변경(③-1 선언 wire 변경 제외)

## 리스크

- ③-1 type URI 변경 ↔ ② 신규 단언 교차 → ②는 status 중심 단언으로 회피
- squash 머지: gitleaks는 allowlist 전환 완료라 fingerprint 함정 재발 없음
- Boot 4.x 함정 3종(1c dev-log) 숙지
- 롤백: 전 PR squash → 단일 revert. ① 커밋은 docs-only.
