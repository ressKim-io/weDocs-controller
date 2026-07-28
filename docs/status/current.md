# 현재 상태 — 재개 SSOT

> **이 파일이 "지금 어디까지 왔고 다음에 뭘 하나"의 유일한 출처다.**
> CLAUDE.md는 이 파일을 가리키는 포인터만 갖는다(진척 이력을 CLAUDE.md에 두지 않는 이유 = 공식 가이드의 "자주 바뀌는 정보 제외" + 그 편집 지점이 곧 드리프트 지점이었다는 실증).
> 완료 이력 = [`history.md`](history.md) · 상세 실행 계획 = `docs/plans/`

**최종 갱신**: 2026-07-28

---

## 지금

**M2 Phase 2(인증/인가) — 2a·2b 머지 완료, 남은 것은 2c뿐.**

> 2026-07-28 사이드 트랙 완료 — Claude 상시 로드 컨텍스트 1,975 → 300줄(−85%) + 예산 게이트 3중 배선.
> 이후 `.claude/**`·`CLAUDE.md`를 편집하면 `PostToolUse` 훅이 예산을 즉시 검사한다.
> 회고 = [dev-logs/2026-07-28-claude-context-budget.md](../dev-logs/2026-07-28-claude-context-budget.md)

M1(실시간 수렴) 완료. M2는 doc-service 신설(Phase 1 전체 완료) → 인증/인가(Phase 2, 진행 중) → 엔진 저장·복원·outbox·E2E(Phase 3~6) 순.

| Phase | 상태 | 산출 |
|---|---|---|
| 2a-1 gateway 인증 | ✅ 머지 | backend `583b065` |
| 2a-2 gateway 인가 + viewer write-drop | ✅ 머지 | backend `4cb750d` |
| 2b engine role 강제 | ✅ 머지 | engine `4d9c39e` |
| **2c frontend 토큰** | **← 다음** | — |

## 다음 액션 — Phase 2c

frontend 레포, branch + PR + 건별 승인.

1. `WebsocketProvider`의 `protocols` 옵션으로 로그인 JWT 전달. ⚠️ **y-websocket의 subprotocol 지원을 spec 사전검증**(`workflow.md` §신규 도구 — 추측 금지).
2. 데모 `?room=demo` → **실제 페이지 UUID화**. 2a-2 D1의 이월 — doc-service가 `doc_id`/`user_id`를 UUID로 파싱하므로 비UUID는 gRPC 왕복 없이 403.
3. E2E 스모크: editor 양방향 / viewer read-only / 무토큰 실패.

**작업량 변수**: 기존 무인증 수렴 E2E가 전부 토큰 경로로 바뀐다 — 회귀 정비가 실제 시간을 좌우한다.
**⚠️ 프론트 E2E는 CI 밖이다**(engine+gateway 실기동 필요) → 로컬에서 직접 띄워 확인해야 한다.

상세 SSOT = [`plans/2026-07-19-m2-phase2-auth-authz.md`](../plans/2026-07-19-m2-phase2-auth-authz.md) §재개 지점

## 이후

Phase 3 엔진 저장 → 4 복원 → 5 outbox → 6 E2E. 본류 plan = [`plans/2026-06-30-m2-persistence-session.md`](../plans/2026-06-30-m2-persistence-session.md)

⚠️ **Phase 3은 `build_client` flip부터가 아니다** — 2b가 이미 `true`로 선반영했다. `SaveSnapshot` 호출 배선부터 시작한다.

---

## 열린 트랙 (완료 시 여기부터 확인)

> **이 표가 "무엇이 나를 pending으로 주장하는가"의 답이다.** 어떤 작업을 끝냈으면 **먼저 이 표를 훑어** 그 항목을 pending으로 들고 있는 plan이 있는지 확인한다. 이 장치가 없어서 `plan-audit-improvements`의 T4-3(서비스 CI)이 한 달간 미체크로 남았다(2026-07-28 발견).

| plan | status | 실제 남은 것 |
|---|---|---|
| [m2-persistence-session](../plans/2026-06-30-m2-persistence-session.md) | in-progress | M2 Phase 2c → 3~6 |
| [m2-phase2-auth-authz](../plans/2026-07-19-m2-phase2-auth-authz.md) | in-progress | 2c만 |
| [plan-audit-improvements](../plans/2026-06-30-plan-audit-improvements.md) | in-progress | T4 잔여 4건(T4-1 NFR/DoD 트래커 · T4-2 관측 콜사이트 · T4-4 ADR 0002~0009 승격 · T4-5 ①②③⑤). **T4-3 서비스 CI는 2026-07-28 완료** |


> **2026-07-28 역방향 점검**: 위 3건은 전부 M2 트랙이라 이번 Claude 설정 작업과 무관.
> [claude-context-budget](../plans/2026-07-28-claude-context-budget.md)는 `done`으로 클로징했고 새로 여는 트랙 없음.
그 외 plan은 전부 `done`.

## 이월된 findings (구현 시 소거)

- **2b 크래프트 게이트 Minor 4건** — `extract_role` 거절 로그에 `doc_id`·`trace_id` 없음 / `Cargo.toml` dev-dep 주석의 feature 주장이 사실과 다름 / `let _ = send` 근거 주석 / plan이 명시한 `INVALID_ROLE_MSG` 상수 미도입. 상세 = phase2 plan §2b.
- **1c PR② 게이트 findings** — 상세 = [`plans/2026-07-12-m2-phase1c-rest-jwt.md`](../plans/2026-07-12-m2-phase1c-rest-jwt.md) §PR② (HIGH 2건은 PR #10 `a40bae5`에서 해소됨).

---

## 알아둘 것 (자주 헷갈리는 사실)

- **2b의 방어 범위** = 게이트웨이 **회귀·계약 위반**이지 "엔진 직접 gRPC 우회" 차단이 **아니다**. `role`은 클라이언트 통제 메타라 악의적 직접 호출자는 `editor`를 자칭해 통과한다 — 그 차단은 M5(mTLS STRICT·NetworkPolicy) 몫.
- **proto 태그** = `proto-v0.2.0` **원격 push 완료**(`99213c3`). engine/backend CI가 이 ref를 핀한다 → proto 계약이 바뀌면 태그 bump + 양 레포 워크플로 `PROTO_REF` 갱신.
- **CI** = 4레포 전부 빌드·테스트 게이트 보유(2026-07-28). PR 초록이 이제 실제 검증을 뜻한다. 단 **프론트 E2E는 제외**.
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
