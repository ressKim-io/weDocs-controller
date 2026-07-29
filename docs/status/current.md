# 현재 상태 — 재개 SSOT

> **이 파일이 "지금 어디까지 왔고 다음에 뭘 하나"의 유일한 출처다.**
> CLAUDE.md는 이 파일을 가리키는 포인터만 갖는다(진척 이력을 CLAUDE.md에 두지 않는 이유 = 공식 가이드의 "자주 바뀌는 정보 제외" + 그 편집 지점이 곧 드리프트 지점이었다는 실증).
> 완료 이력 = [`history.md`](history.md) · 상세 실행 계획 = `docs/plans/`

**최종 갱신**: 2026-07-29

---

## 지금

**M2 Phase 2(인증/인가) — 2a·2b·2c-C1·2c-C2 머지 완료, 남은 것은 2c-C3뿐.**

> 2026-07-28 사이드 트랙 완료 — Claude 상시 로드 컨텍스트 1,975 → 300줄(−85%) + 예산 게이트 3중 배선.
> 이후 `.claude/**`·`CLAUDE.md`를 편집하면 `PostToolUse` 훅이 예산을 즉시 검사한다.
> 회고 = [dev-logs/2026-07-28-claude-context-budget.md](../dev-logs/2026-07-28-claude-context-budget.md)

M1(실시간 수렴) 완료. M2는 doc-service 신설(Phase 1 전체 완료) → 인증/인가(Phase 2, 진행 중) → 엔진 저장·복원·outbox·E2E(Phase 3~6) 순.

| Phase | 상태 | 산출 |
|---|---|---|
| 2a-1 gateway 인증 | ✅ 머지 | backend `583b065` |
| 2a-2 gateway 인가 + viewer write-drop | ✅ 머지 | backend `4cb750d` |
| 2b engine role 강제 | ✅ 머지 | engine `4d9c39e` |
| 2c-C1 doc-service effective role 노출 | ✅ 머지 | backend `4c1678e` (PR #19) |
| 2c-C2 frontend 인증 셸 | ✅ 머지 | frontend `de002f5` (PR #5) |
| **2c-C3 frontend 페이지 선택 + 에디터 + E2E** | **← 다음** (Phase 2의 마지막 조각) | — |

## 다음 액션 — Phase 2c (C3)

**상세 SSOT = [`plans/2026-07-28-m2-phase2c-frontend-auth.md`](../plans/2026-07-28-m2-phase2c-frontend-auth.md) §재개 지점.**
착수 탐색(2026-07-28)에서 2c가 "토큰 전달 한 줄"이 아님이 드러나 **별도 plan으로 분리**했다.

2c는 신규 기능이 아니라 **복구**다(2a/2b가 서버측을 세우며 끊긴 클라이언트 경로를 잇는 일). 세 조각 중 둘이 끝났다:

| 원래 문제 | 상태 |
|---|---|
| 프론트에 **로그인이 없다**(토큰 출처 없음) | ✅ **C2가 해소** — 로그인/회원가입 + 메모리 토큰 스토어 |
| **viewer가 자기 역할을 모른다** → 타이핑이 게이트웨이에서 조용히 drop되고 로컬 `Y.Doc`만 divergent(새로고침 시 유실). UX가 아니라 **정합성 버그** | ⚠️ **절반** — C1이 서버측 노출(`myRole`·`canEdit`) 완료, **프론트 소비는 C3-4** |
| **페이지 UUID 획득 경로가 없다**(1c REST 미소비) + 기본 room `demo`가 비UUID → 403 | ❌ **C3가 할 일** — 워크스페이스/페이지 목록 + `DEFAULT_ROOM` 제거 |

→ 즉 **C3 = 남은 두 줄을 잇는 작업**이다. 기존 수렴 E2E도 여기서 함께 복구된다.

순서: ~~C1 backend(role 노출)~~ ✅ → ~~C2 frontend(인증 셸)~~ ✅ → **C3 frontend**(페이지 선택 + 에디터 + E2E).
서비스 레포는 branch + PR + 건별 승인.

**C3는 3 PR로 분할한다**(2026-07-29 결정 D4): ① REST 소비 계층 → ② 화면 배선 → ③ E2E+문서.
한 PR이면 850줄+라 리뷰가 불가능하고, C2가 966줄로 상한을 넘긴 선례를 반복하게 된다.

⚠️ **지금 앱은 로그인까지만 된다** — 에디터는 여전히 `demo` room으로 403이다. 의도된 중간 상태이고
C3-3(DEFAULT_ROOM 제거 + 페이지 선택)에서 해소된다. **회귀로 오판하지 말 것.**

⚠️ **C3 파일 배치는 `src/page/api.ts`·`src/workspace/api.ts`다** — `src/api/*`가 아니다.
C2 게이트에서 `src/api/`가 layering P7(전역 계층 통패키지 금지) 위반으로 반려돼 feature 평면으로
재배치했다. 전송은 기존 `src/common/http/client.ts`의 `apiRequest`를 재사용한다.

**⚠️ 프론트 E2E는 CI 밖**(로컬 실기동) — 사전조건이 engine+gateway 2개 → **+postgres+doc-service = 4프로세스**로 늘어난다.

## 이후

Phase 3 엔진 저장 → 4 복원 → 5 outbox → 6 E2E. 본류 plan = [`plans/2026-06-30-m2-persistence-session.md`](../plans/2026-06-30-m2-persistence-session.md)

⚠️ **Phase 3은 `build_client` flip부터가 아니다** — 2b가 이미 `true`로 선반영했다. `SaveSnapshot` 호출 배선부터 시작한다.

---

## 열린 트랙 (완료 시 여기부터 확인)

> **이 표가 "무엇이 나를 pending으로 주장하는가"의 답이다.** 어떤 작업을 끝냈으면 **먼저 이 표를 훑어** 그 항목을 pending으로 들고 있는 plan이 있는지 확인한다. 이 장치가 없어서 `plan-audit-improvements`의 T4-3(서비스 CI)이 한 달간 미체크로 남았다(2026-07-28 발견).

| plan | status | 실제 남은 것 |
|---|---|---|
| [m2-persistence-session](../plans/2026-06-30-m2-persistence-session.md) | in-progress | M2 Phase 2c → 3~6 |
| [m2-phase2-auth-authz](../plans/2026-07-19-m2-phase2-auth-authz.md) | in-progress | 2c만 — 상세는 아래 분리 plan이 소유 |
| [m2-phase2c-frontend-auth](../plans/2026-07-28-m2-phase2c-frontend-auth.md) | in-progress | **C3만** — frontend 1~2 PR. C0·C1·C2 완료(C1 = backend #19, C2 = frontend #5) |
| [plan-audit-improvements](../plans/2026-06-30-plan-audit-improvements.md) | in-progress | T4 잔여 4건(T4-1 NFR/DoD 트래커 · T4-2 관측 콜사이트 · T4-4 ADR 0002~0009 승격 · T4-5 ①②③⑤). **T4-3 서비스 CI는 2026-07-28 완료** |


> **2026-07-28 역방향 점검**: 위 3건은 전부 M2 트랙이라 이번 Claude 설정 작업과 무관.
> [claude-context-budget](../plans/2026-07-28-claude-context-budget.md)는 `done`으로 클로징했고 새로 여는 트랙 없음.
그 외 plan은 전부 `done`.

## 이월된 findings (구현 시 소거)

- **2b 크래프트 게이트 Minor 4건** — `extract_role` 거절 로그에 `doc_id`·`trace_id` 없음 / `Cargo.toml` dev-dep 주석의 feature 주장이 사실과 다름 / `let _ = send` 근거 주석 / plan이 명시한 `INVALID_ROLE_MSG` 상수 미도입. 상세 = phase2 plan §2b.
- **1c PR② 게이트 findings** — 상세 = [`plans/2026-07-12-m2-phase1c-rest-jwt.md`](../plans/2026-07-12-m2-phase1c-rest-jwt.md) §PR② (HIGH 2건은 PR #10 `a40bae5`에서 해소됨).
- **`WorkspaceService.listMine`에 조회 상한 없음** (backend, secure-coding P2) — 2026-07-29 C3-1 게이트에서 발견.
  같은 서비스의 `PageTreeService.list`는 `MAX_PAGE_LIST`(1,000)로 자르는데 워크스페이스 목록만 무상한이다.
  **클라에서 자르지 않는다** — 자르면 "내 워크스페이스가 안 보인다"는 무증상 버그가 되고 서버의 무상한
  조회는 그대로 남는다. 상한은 조회가 있는 곳에 둔다 → 다음 backend PR에 동승.

---

## 알아둘 것 (자주 헷갈리는 사실)

- **2b의 방어 범위** = 게이트웨이 **회귀·계약 위반**이지 "엔진 직접 gRPC 우회" 차단이 **아니다**. `role`은 클라이언트 통제 메타라 악의적 직접 호출자는 `editor`를 자칭해 통과한다 — 그 차단은 M5(mTLS STRICT·NetworkPolicy) 몫.
- **proto 태그** = `proto-v0.2.0` **원격 push 완료**(`99213c3`). engine/backend CI가 이 ref를 핀한다 → proto 계약이 바뀌면 태그 bump + 양 레포 워크플로 `PROTO_REF` 갱신.
- **CI** = 4레포 전부 빌드·테스트 게이트 보유(2026-07-28). PR 초록이 이제 실제 검증을 뜻한다. 단 **프론트 E2E는 제외**.
  ⚠️ **"게이트 보유"와 "게이트 초록"은 다르다** — frontend `security-scan/npm-audit`은 `ci.yml` 신설 시점부터
  main에서 계속 red였는데(vite 8.1.0 전이 의존 postcss) `ci.yml`이 초록이라 가려져 있었다(2026-07-29 발견·해소).
  **새 게이트를 붙였으면 기존 게이트의 main 상태도 함께 확인한다.**
- **doc-service 에러 계약** — 도메인 예외만 RFC 9457 확장 멤버 `code`를 갖는다. **Bean validation 400에는 없다**
  (프레임워크 경로). 실측 확인 2026-07-29 → 클라이언트는 `code` 부재를 전제한 폴백이 필요하고,
  분기는 `code`/`status`로만 한다(`detail` 파싱은 서버가 금지).
- **`POST /api/auth/signup`은 토큰을 주지 않는다** — 201 + `UserResponse`뿐. 세션이 필요하면 login을 이어 부른다.
- **프론트엔드 파일 배치 = feature 평면** — `src/<feature>/…` + `src/common/<관심사>/…`.
  `src/api/`·`src/service/` 류 전역 계층 통패키지는 크래프트 게이트 layering P7이 **이름까지 지목해 금지**한다
  (C2에서 실제 반려됨). "Java 패키지 규칙"으로 읽히지만 프론트 관행에도 그대로 발화한다.
- **doc-service 구조** = package-by-feature(ADR-0019). 신규 코드는 feature 패키지(auth/workspace/page/snapshot) 평면에, 공용은 `common/`. 도메인 에러는 카탈로그(`DocErrorCode` enum + 카테고리 예외, ADR-0018)로만.
- **테스트 환경** — backend doc-service 테스트는 colima 필요(`DOCKER_HOST`/`TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE`), ws-gateway는 불요(in-process fake).
- **승인 경계** — 서비스 레포(backend/crdt-engine/frontend)는 branch+PR+**건별 승인**(push·PR 생성·머지 각각). controller만 main 직접.
- **크래프트 룰은 레포 경계를 안 넘는다**(실측 2026-07-28) — controller에서 `--add-dir`로 서비스 레포를 열어도 `paths:` 스코프 룰 10종(java·spring·error-handling·concurrency·secure-coding·design-patterns·layering-readability·observability·clean-code·security)은 **로드되지 않는다**. 상시 5개와 settings 권한/훅·에이전트는 따라온다. → 크래프트 `[B]` 게이트는 반드시 **에이전트로** 실행. 상세 = [dev-log](../dev-logs/2026-07-28-rules-do-not-cross-repo.md)

## 교훈 dev-log (같은 함정 재발 시)

| 주제 | dev-log |
|---|---|
| CI 갭·게이트 실효성 증명 | [2026-07-28-build-test-ci-gap](../dev-logs/2026-07-28-build-test-ci-gap.md) |
| 상시 컨텍스트 예산(−85%)·게이트 배선 | [2026-07-28-claude-context-budget](../dev-logs/2026-07-28-claude-context-budget.md) |
| 룰이 레포 경계를 안 넘음 | [2026-07-28-rules-do-not-cross-repo](../dev-logs/2026-07-28-rules-do-not-cross-repo.md) |
| gitleaks fingerprint ↔ squash 함정 | [2026-07-17](../dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md) |
| VT pinning 측정(맞는 결론·틀린 근거) | [2026-07-20](../dev-logs/2026-07-20-vt-pinning-grpc-blocking-stub.md) |
| gateway 관측 계약·WIP 드리프트 | [2026-07-19](../dev-logs/2026-07-19-m2-gateway-authn-observability.md) |
| Spring Boot 4.x·Jackson 3 함정 | [2026-07-13](../dev-logs/2026-07-13-m2-doc-service-1c-boot4-traps.md) |
| 에러 카탈로그·package-by-feature | [2026-07-18](../dev-logs/2026-07-18-m2-refactor-track-backend.md) |
