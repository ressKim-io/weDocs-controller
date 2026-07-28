# Synapse Controller — 작업 가이드 (Claude Code)

이 레포는 5-repo 폴리레포의 **컨트롤 플레인**(proto SSOT · infra · CI · docs)이다.
실제 서비스 코드는 별도 레포에 있다 — **현재 존재**: `frontend` / `backend`(ws-gateway + doc-service) / `crdt-engine`. **미생성(예정)**: `ai-service`(M4).

## 진입점
`docs/PRD.md` (무엇·왜) → `docs/SDD.md` (어떻게) → `docs/adr/` (결정 로그).

## 불변 규칙 (가드레일) — SDD §14
1. **proto는 여기서 시작.** 모든 계약 변경은 `proto/`에서 → `buf lint` + `buf breaking` 통과 → 다운스트림 buf 원격 git input ref bump(ADR-0010, **submodule 아님**) → 3언어 재생성. 다운스트림 레포에서 proto를 직접 고치지 않는다.
2. **AI Service는 CRDT 의존성을 가질 수 없다.** AI는 stateless 텍스트 in/out. (설계 위반)
3. **게이트웨이는 native call(JNI)을 도입하지 않는다.** VT pinning 방지.
4. **서비스 간 호출은 gRPC + OTel propagator를 통과한다.** W3C `traceparent` 통일.
5. **CRDT Engine은 "엔진"이다.** 단순 yrs 래퍼 PR은 반려 — 최적화 + `criterion` 벤치마크 동반.
6. **M1 머지 전 `proptest` 수렴 테스트 통과 필수.**
7. **크래프트 게이트 통과 없이 머지 금지.** 서비스 코드 PR은 크래프트 표준 6종 `[B]` 체크리스트(Gate 3 렌즈 🦀/☕) 통과 필수.
8. **무검증 입력·무상한 자원 금지.** 외부 입력은 경계 검증 후 도메인 타입으로, 신규 상태·수신 경로는 상한·수명 동반(`secure-coding.md` P1/P2).

## 언어 배정 (왜)
- I/O 바운드 → **Java 25 Virtual Thread** (ws-gateway, doc-service)
- AI 생태계 → **Python** (ai-service, indexer)
- CPU 바운드 + 정확성 critical → **Rust** (crdt-engine)

## 이 레포에서 자주 하는 일
- proto 편집 → `buf lint proto && buf breaking proto --against '.git#branch=main,subdir=proto'`
- 코드 생성(검증용) → `buf generate` (→ `gen/`, gitignored)
- infra → `infra/` (kustomize · istio ambient · argocd)

## 현재 상태 · 재개

**진행 중 = M2 Phase 2c(frontend 토큰).** 상세는 반드시 아래를 먼저 읽어라 — 이 파일엔 진척 이력을 두지 않는다.

- **재개 SSOT** = `docs/status/current.md` — 지금 위치·다음 액션·열린 트랙·이월 findings·자주 헷갈리는 사실
- 완료 이력 = `docs/status/history.md` (세션 시작에 불필요)
- 실행 계획 = `docs/plans/` · 교훈 = `docs/dev-logs/`

> **왜 여기 안 쓰나**: 공식 가이드가 CLAUDE.md에서 배제하라는 항목이 "information that changes frequently"다. 실제로 이 파일의 80%가 진척 이력이던 시절, 그 편집 지점이 곧 드리프트 지점이었다(2026-07-28 정합 — `docs/dev-logs/2026-07-28-claude-md-restructure.md`).

---

## 엔지니어링 표준 (도입: `ress-claude-agents`, 2026-05 기준)

개인 에이전트 컬렉션에서 이 프로젝트에 맞는 것만 도입 (제외: Go, frontend, business/payment/legal — 비범위).

### 룰 로딩 (여기서 선언하지 않는다)
`.claude/rules/`의 `paths:` frontmatter가 곧 스코프다 — `paths:` 없으면 상시, 있으면 매칭 파일을 열 때.
`@import`는 **컨텍스트를 줄이지 않는다**(공식: "imports … load at launch") — 상시로 만들 뿐이라 두지 않는다.

### 상황별 룰 (해당 작업 시 `.claude/rules/` 참조 — `paths:` frontmatter로 스코프됨)
- `code-review.md`·`deep-thinking.md` — 리뷰 품질 / 검증 깊이
- `java.md`·`spring.md` — ws-gateway, doc-service
- `error-handling.md`·`concurrency.md`·`layering-readability.md`·`observability.md`·`design-patterns.md`·`secure-coding.md` — 언어 무관 크래프트 표준 세트 6종(P1~N 원칙 + Java/Rust 실현 + `[B]`/`[A]` 체크리스트). `code-review.md` 크래프트 렌즈(🦀/☕)가 전부 실행
- `istio.md`·`k8s-manifest.md` — infra/istio, infra/k8s, argocd
- `monitoring.md` — OTel/PromQL/Grafana (폴리글랏 trace showcase)
- `version-compatibility.md` — K8s/Istio/ArgoCD/OTel 버전 매트릭스
- `config-contract-audit.md`·`documentation.md`·`phase-workflow.md`·`terraform.md`·`professional-writing.md`·`devlog-lifecycle.md`
- `token-budget.md` — 세션 운영(상시). 모델/effort/캐시 **수치**는 `/context-and-effort` 스킬

### 서브에이전트 (`Agent` 도구, `subagent_type`)
**Rust/CRDT `rust-expert`** ★(엔진 핵심) / 언어 `java-expert`·`python-expert` / 리뷰 `code-reviewer`·`cicd-reviewer`·`dockerfile-reviewer` / 아키텍처 `architect-agent`(proto·계약)·`saga-agent`(outbox) / 메시 `service-mesh-expert`(Istio Ambient) / 관측 `otel-expert`·`observability-reviewer` / K8s·GitOps `k8s-troubleshooter`·`k8s-reviewer`·`gitops-reviewer`·`platform-engineer` / 데이터 `database-expert`·`redis-expert` / 메시징 `messaging-expert` / 기타 `debugging-expert`·`git-workflow`·`tech-lead`

지식 참조: `.claude/skills/<category>/` (on-demand, 17개 카테고리 — `rust/`에 `crdt-yrs`·`crdt-convergence-testing` 신규). 신규 작성 표준: `.claude/templates/`.

---

## 커밋·push 규칙 (이 레포 전용 오버라이드)

> **브랜치·push 정책의 유일한 권위는 이 절이다.** `user-approval.md`("push는 승인 후")를 controller에 한해
> 오버라이드한다 — 솔로 컨트롤 플레인이라 PR 게이트가 불필요. 형식(커밋 타입표·PR 템플릿)은 `/git-conventions`.

- ✅ **controller는 `main`에 직접 commit·push 허용** — push마다 별도 승인 안 받아도 됨(사용자 사전 승인됨).
- ✅ **커밋은 논리 단위로 분할** — 한 커밋에 몰지 말 것. 영역별(proto / docs / infra / ci / claude …) Conventional Commit.
- ⛔ **서비스 레포는 예외 아님** — `backend` / `ai-service` / `crdt-engine` / `frontend`는 브랜치 + PR + 건별 승인.
- ⛔ **force push 금지** (`--force-with-lease`도 main엔 금지) · **시크릿 커밋 금지**(`.env`·`*.pem`·`*.key`·크리덴셜)
- ⛔ **`git add .` 지양** — 파일을 명시적으로 스테이징한다.
- ⛔ **`Co-Authored-By` trailer 금지** — 사용자가 명시 요청한 경우만. (`.claude/settings.json`의 `attribution`이 강제)
