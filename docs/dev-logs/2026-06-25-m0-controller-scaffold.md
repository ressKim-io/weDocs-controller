---
date: 2026-06-25
category: meta
tier: 2
importance: major
status: resolved
tags: [m0, scaffold, proto, buf, crdt, agents, rules, session-handoff]
related:
  - adr/0001-language-strategy-b.md
  - adr/0010-proto-distribution-buf-git-input.md
---

# M0 — controller 스캐폴딩 + 에이전트 도입 + Rust/CRDT 자산 (세션 핸드오프)

## Context
- repo: `weDocs-controller` (Synapse 5-repo 폴리레포의 컨트롤 플레인) / 환경: 로컬(홈랩 타겟)
- 세션 목표: 빈 controller 레포에 PRD·SDD 반영 → SDD §12 골격 스캐폴딩 → 개인 에이전트 컬렉션 선별 도입 → Rust/CRDT 자산 보강 → proto 검증 → 커밋

## 한 일

### 1. 문서 (docs/)
- PRD·SDD를 `docs/`에 저장. **PRD를 SDD v2에 정렬**(6군데: Go→Java VT, 모노레포→폴리레포, +Python, trace `Java→Rust→Python`).
- 둘 다 길어서 **인덱스 + 분할**: `docs/PRD.md`(+§1) → `prd/{1-why-and-users,2-scope-nfr-dod}`, `docs/SDD.md` → `sdd/{1-architecture … 5-project-milestones-guardrails}`. 스크립트로 섹션 단위 무손실 분할.
- `docs/adr/0001-language-strategy-b.md` 분리.

### 2. 스캐폴딩 (SDD §12)
- `proto/` SSOT (common/crdt/doc/ai) + `proto/buf.yaml`(BASIC lint / FILE breaking) + 루트 `buf.gen.yaml`(java·python·rust).
- `infra/` (k8s kustomize base+homelab / istio ambient ns + 엔진 waypoint + consistentHash DR / argocd app-of-apps / terraform 스텁).
- `ci/` + `.github/workflows/proto-ci.yml` (buf 게이트). 루트 `README.md` · `CLAUDE.md` · `.gitignore`.

### 3. 에이전트/스킬/룰 도입 (`ress-claude-agents`, 2026-05)
- 선별 복사 → `.claude/`: **agents 21 · skills 199/17cats · rules 24 · templates 9**.
- 제외: go(이 프로젝트 Go 없음)·frontend(별도 레포)·business/payment/legal/migration. 카테고리 내 prune: AWS EKS·finops 8종·dx 온보딩.
- **stale 플래그**: `token-budget`·`effort-guide` = Opus 4.7 기준 → CLAUDE.md import 제외. AGENTS.md(메타레포용) 미도입.
- 핵심 룰 6개 `@import`로 CLAUDE.md 연결(자동 적용 확인됨).

### 4. Rust/CRDT 자산 신규 작성 (컬렉션에 Rust 없음, 2026-06 웹검색 기반)
- `agents/rust-expert`(opus/max) + `skills/rust/{crdt-yrs, crdt-convergence-testing}` — SKILL/AGENT-SPEC 규격.
- 확정 스택: **yrs 0.27.2**(Yjs wire 호환) · **tonic 0.12+/prost 0.13/tokio 1.x** · 수렴은 `proptest`(commutative/associative/idempotent) · `criterion` 벤치.

### 5. 검증 + 커밋
- **buf 1.71.0 설치** → `buf build/lint(BASIC)/format` 전부 통과(findings 0).
- 논리 단위 **5 커밋**(scaffold/proto/docs/infra/claude) + 이번 턴 rule·devlog. 286+ files tracked.

## 결정 (decisions)
- proto: **BASIC lint + 플랫 단일세그먼트 패키지**(`common`/`crdt`/`doc`/`ai`) + `java_package` 분리. (RPC 도메인 네이밍 유지 위해 STANDARD 미적용. 추후 `synapse.*.v1` 승격 가능)
- **5-repo 폴리레포**, proto SSOT=controller. infra는 controller 흡수.
- Rust 자산 self-authored(웹검색 근거).
- **controller는 main 직접 commit·push 허용**(이번 세션 신규 룰 — `CLAUDE.md` §커밋·push 규칙). 서비스 레포는 PR 유지.

## 다음 세션 할 일 (TODO, 우선순위)
1. **proto submodule 방식 확정** — git submodule은 서브디렉터리만 못 가져옴 → (a) proto 별도 repo vs (b) controller 전체 submodule. **다운스트림 블로커, M1 전 필수.** (`proto/README.md` ⚠️)
2. **제품명 확정** — 코드네임 `Synapse` vs 폴더 `weDocs`. 원격 repo명·proto java_package에 영향.
3. **M1 수직 슬라이스 착수** — `crdt-engine`(Rust) + 얇은 `ws-gateway`(Java) + 최소 `frontend`(React) 레포 골격 → **"두 브라우저 동시 편집 수렴"**(Yjs↔yrs + bidi). `rust-expert`+`crdt-yrs`+`crdt-convergence-testing` 활용. **M1 머지 전 proptest 수렴 통과 필수(가드레일).**
4. **SDD §15 미해결** 순차 확정: 엔진 장애 복원 / AI SLO / outbox(Debezium vs 앱레벨) / 인증 분리 시점 / consistent-hash 키 전달(`x-doc-id`).
5. (필요 시) 컬렉션에서 추가 도입: `operations`(M5 runbook/postmortem), `frontend` 스킬(FE 스캐폴딩 시), 슬래시 commands.

## 관련 자료
- `adr/0001-language-strategy-b.md` — 언어 전략 B
- `CLAUDE.md` §커밋·push 규칙 — 이번 세션 신규 룰
- `proto/README.md` — submodule 미해결(TODO #1)
- 원본 컬렉션: `git@github.com:ressKim-io/ress-claude-agents.git` (HEAD 2026-05-26)
