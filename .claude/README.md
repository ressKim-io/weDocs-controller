# .claude — 에이전트 / 스킬 / 룰

`ress-claude-agents`(개인 컬렉션, 2026-05)에서 이 프로젝트(폴리글랏 + proto SSOT + CRDT +
Istio Ambient + 폴리글랏 OTel + Kafka + RAG)에 맞는 자산만 선별 도입했다.
프로젝트 가드레일·룰 연결은 루트 [`../CLAUDE.md`](../CLAUDE.md) 참조.

| 자산 | 개수 | 위치 |
|---|---|---|
| agents (서브에이전트) | 21 | `agents/` (+`rust-expert` ★) |
| skills (on-demand 지식) | 199 / 17 카테고리 | `skills/` (+`rust/`) |
| rules (코딩·보안·워크플로우) | 24 | `rules/` |
| templates (작성 표준) | 9 | `templates/` |

## 선별 기준 (2달 지난 컬렉션 → fit 판단)
- **제외**: `go`(이 프로젝트 Go 없음), `frontend`(별도 레포), `business`/`payment`/`legal`/`migration`(비범위)
- **카테고리 내 prune**: AWS EKS·Lambda·crossplane·ec2 (homelab KinD라 무관), finops 8종 (비범위), dx 온보딩/팀토폴로지/메트릭 (솔로 포트폴리오라 무관)
- **stale 플래그**: `rules/token-budget.md`·`effort-guide.md` = Opus 4.7 기준 → 자동 적용 제외(루트 CLAUDE.md 참고), AGENTS.md(메타레포용)는 미도입
- **신규 작성(컬렉션에 Rust 없음)**: `agents/rust-expert` + `skills/rust/`(`crdt-yrs`·`crdt-convergence-testing`) — 2026-06 웹검색(yrs 0.27·tonic 0.12+·proptest) 기반으로 SKILL/AGENT-SPEC 규격대로 직접 작성. 이 프로젝트 ★핵심(CRDT/Rust)이라 필수.

## skill 카테고리
`ai · architecture · cicd · dx · infrastructure · kubernetes · messaging · msa · observability · platform · python · rust · security · service-mesh · spring · sre · testing`

> 형식 주의: 대부분 flat `.md` **지식 파일**이라 Claude Code의 자동 발견(`SKILL.md`) 대상이 아님 — 룰/에이전트가 참조하는 레퍼런스로 동작.

## 더 필요하면
원본 클론에서 추가 도입 가능: `operations`(runbook/postmortem — M5), `frontend`(frontend 레포 스캐폴딩 시), commands(슬래시 명령 43종), workflows(시나리오 번들).
