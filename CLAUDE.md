# Synapse Controller — 작업 가이드 (Claude Code)

이 레포는 5-repo 폴리레포의 **컨트롤 플레인**(proto SSOT · infra · CI · docs)이다.
실제 서비스 코드는 별도 레포(`frontend` / `backend` / `ai-service` / `crdt-engine`)에 있다.

## 진입점
`docs/PRD.md` (무엇·왜) → `docs/SDD.md` (어떻게) → `docs/adr/` (결정 로그).

## 불변 규칙 (가드레일) — SDD §14
1. **proto는 여기서 시작.** 모든 계약 변경은 `proto/`에서 → `buf lint` + `buf breaking` 통과 → 다운스트림 submodule 업데이트 → 3언어 재생성. 다운스트림 레포에서 proto를 직접 고치지 않는다.
2. **AI Service는 CRDT 의존성을 가질 수 없다.** AI는 stateless 텍스트 in/out. (설계 위반)
3. **게이트웨이는 native call(JNI)을 도입하지 않는다.** VT pinning 방지.
4. **서비스 간 호출은 gRPC + OTel propagator를 통과한다.** W3C `traceparent` 통일.
5. **CRDT Engine은 "엔진"이다.** 단순 yrs 래퍼 PR은 반려 — 최적화 + `criterion` 벤치마크 동반.
6. **M1 머지 전 `proptest` 수렴 테스트 통과 필수.**

## 언어 배정 (왜)
- I/O 바운드 → **Java 25 Virtual Thread** (ws-gateway, doc-service)
- AI 생태계 → **Python** (ai-service, indexer)
- CPU 바운드 + 정확성 critical → **Rust** (crdt-engine)

## 이 레포에서 자주 하는 일
- proto 편집 → `buf lint proto && buf breaking proto --against '.git#branch=main,subdir=proto'`
- 코드 생성(검증용) → `buf generate` (→ `gen/`, gitignored)
- infra → `infra/` (kustomize · istio ambient · argocd)

## 현재 상태
**M0** (기획·proto·스캐폴딩). 다음 리스크 최우선 작업 = **M1**: Yjs↔yrs 상호운용 + bidi 스트림으로 "두 브라우저 동시 편집 수렴" 증명 (crdt-engine + 얇은 ws-gateway + 최소 frontend 수직 슬라이스).

---

## 엔지니어링 표준 (도입: `ress-claude-agents`, 2026-05 기준)

개인 에이전트 컬렉션에서 이 프로젝트에 맞는 것만 도입 (제외: Go, frontend, business/payment/legal — 비범위).

### 항상 적용 (import)
@.claude/rules/clean-code.md
@.claude/rules/workflow.md
@.claude/rules/security.md
@.claude/rules/testing.md
@.claude/rules/debugging.md
@.claude/rules/user-approval.md

### 상황별 룰 (해당 작업 시 `.claude/rules/` 참조 — `paths:` frontmatter로 스코프됨)
- `git.md`·`code-review.md`·`deep-thinking.md` — 커밋/PR/품질 (보편)
- `java.md`·`spring.md` — ws-gateway, doc-service
- `istio.md`·`k8s-manifest.md` — infra/istio, infra/k8s, argocd
- `monitoring.md` — OTel/PromQL/Grafana (폴리글랏 trace showcase)
- `version-compatibility.md` — K8s/Istio/ArgoCD/OTel 버전 매트릭스
- `config-contract-audit.md`·`documentation.md`·`phase-workflow.md`·`cloud-cli-safety.md`·`terraform.md`·`professional-writing.md`·`devlog-lifecycle.md`

> ⚠️ **stale (미import)**: `token-budget.md`·`effort-guide.md`는 **Opus 4.7 기준**(현재 4.8). 카운트·effort 단계가 현행과 달라 자동 적용 제외 — 참고만.

### 서브에이전트 (`Agent` 도구, `subagent_type`)
**Rust/CRDT `rust-expert`** ★(엔진 핵심) / 언어 `java-expert`·`python-expert` / 리뷰 `code-reviewer`·`cicd-reviewer`·`dockerfile-reviewer` / 아키텍처 `architect-agent`(proto·계약)·`saga-agent`(outbox) / 메시 `service-mesh-expert`(Istio Ambient) / 관측 `otel-expert`·`observability-reviewer` / K8s·GitOps `k8s-troubleshooter`·`k8s-reviewer`·`gitops-reviewer`·`platform-engineer` / 데이터 `database-expert`·`redis-expert` / 메시징 `messaging-expert` / 기타 `debugging-expert`·`git-workflow`·`tech-lead`

지식 참조: `.claude/skills/<category>/` (on-demand, 17개 카테고리 — `rust/`에 `crdt-yrs`·`crdt-convergence-testing` 신규). 신규 작성 표준: `.claude/templates/`.

---

## 커밋·push 규칙 (이 레포 전용 오버라이드)

> 일반 룰 `git.md`("main 직접 push 금지")·`user-approval.md`("push는 승인 후")를 **이 controller 레포에 한해** 오버라이드한다. controller는 솔로 컨트롤 플레인이라 PR 게이트가 불필요.

- ✅ **controller는 `main`에 직접 commit·push 허용** — push마다 별도 승인 안 받아도 됨(사용자 사전 승인됨).
- ✅ **커밋은 논리 단위로 분할** — 한 커밋에 몰지 말 것. 영역별(proto / docs / infra / ci / claude …) Conventional Commit.
- ⛔ **서비스 레포는 예외 아님** — `backend` / `ai-service` / `crdt-engine` / `frontend`는 일반 룰 적용(브랜치 + PR + 승인).
- 그 외(force push 금지, 시크릿 커밋 금지, `git add .` 지양·명시적 스테이징)는 `git.md` 그대로.
