# .claude — 에이전트 / 스킬 / 룰

`ress-claude-agents`(개인 컬렉션, 2026-05)에서 이 프로젝트(폴리글랏 + proto SSOT + CRDT +
Istio Ambient + 폴리글랏 OTel + Kafka + RAG)에 맞는 자산만 선별 도입했다.
프로젝트 가드레일은 루트 [`../CLAUDE.md`](../CLAUDE.md).

| 자산 | 개수 | 위치 |
|---|---|---|
| agents (서브에이전트) | 20 | `agents/` (+`rust-expert` ★) |
| skills — tier 1 (자동 발견) | 6 | `skills/<name>/SKILL.md` |
| skills — tier 2 (수동 레퍼런스) | 194 / 17 카테고리 | `skills/<category>/*.md` |
| rules (코딩·보안·워크플로우) | 28 | `rules/` |
| templates (작성 표준) | 10 | `templates/` |

## 로딩 비용 — 무엇이 언제 컨텍스트에 들어오나

| 자산 | 상시 로드 | 조건부 | 온디맨드 |
|---|---|---|---|
| `../CLAUDE.md` | 전문 | — | — |
| `rules/*.md` | `paths:` **없는** 것만 전문 | `paths:` 있으면 매칭 파일을 열 때 | — |
| `skills/<name>/SKILL.md` | 이름 + description | — | 본문은 호출 시 |
| `skills/<category>/*.md` | 없음 (0) | — | 경로로 `Read` 할 때만 |
| `agents/*.md` | description | — | 본문은 호출 시 |

- 예산 게이트: `scripts/claude_context_budget.py` + `.github/workflows/claude-context-budget.yml`
  + `settings.json`의 `PostToolUse` 훅. 기준·근거는 [`docs/plans/2026-07-28-claude-context-budget.md`](../docs/plans/2026-07-28-claude-context-budget.md).
- `@import`는 **컨텍스트를 줄이지 않는다**(공식: imports load at launch). 쓰지 않는다.

## skills 2계층 — 어느 쪽에 둘지

**tier 1 (`<name>/SKILL.md`, 자동 발견)** — 모델이 스스로 골라 써야 하는 **절차**.
이름+description이 상시 로드되므로 **≤12개로 유지**(리스팅 예산 = 컨텍스트의 1%,
초과하면 덜 쓰는 스킬 설명부터 조용히 잘린다). 현재 6개:
`git-conventions` · `context-and-effort` · `documentation-templates` · `clean-code` ·
`crdt-yrs` ★ · `crdt-convergence-testing` ★

**tier 2 (`<category>/*.md`, 수동 Read)** — 룰·에이전트가 경로로 참조하는 **지식 레퍼런스**.
자동 발견 대상이 아니고 컨텍스트 비용 0. 194개를 tier 1으로 올리면 리스팅이 넘쳐
tier 1의 이점 자체가 사라지므로 **일괄 승격하지 않는다.**

> 문서·룰에서 tier 2를 가리킬 때는 `/이름`이 아니라 **경로**로 쓴다 — `/이름`은 실행되지 않는다.

## 선별 기준 (2달 지난 컬렉션 → fit 판단)
- **제외**: `go`(이 프로젝트 Go 없음), `frontend`(별도 레포), `business`/`payment`/`legal`/`migration`(비범위)
- **카테고리 내 prune**: AWS EKS·Lambda·crossplane·ec2 (homelab KinD라 무관), finops 8종 (비범위), dx 온보딩/팀토폴로지/메트릭 (솔로 포트폴리오라 무관)
- **agent prune**: `platform-engineer`(Backstage/IDP — 신호 0, 2026-07-28 제거)
- **rule prune**: `cloud-cli-safety`(참조 카탈로그 부재 + AWS/GCP CLI 미사용, 2026-07-28 제거)
- **신규 작성(컬렉션에 Rust 없음)**: `agents/rust-expert` + `crdt-yrs`·`crdt-convergence-testing` — 2026-06 웹검색(yrs 0.27·tonic 0.12+·proptest) 기반으로 SKILL/AGENT-SPEC 규격대로 직접 작성. 이 프로젝트 ★핵심(CRDT/Rust)이라 필수.

## skill 카테고리 (tier 2)
`ai · architecture · cicd · dx · infrastructure · kubernetes · messaging · msa · observability · platform · python · security · service-mesh · spring · sre · testing`

## 더 필요하면
원본 클론에서 추가 도입 가능: `operations`(runbook/postmortem — M5), `frontend`(frontend 레포 스캐폴딩 시),
**commands(슬래시 명령 43종 — 미도입)**, workflows(시나리오 번들).

> 일부 룰이 `/phase-start`·`/review-pr`·`/log-trouble`·`/consolidate-devlogs` 등을 부르는데
> **그 커맨드들은 위 미도입 목록에 있다.** 해당 룰 상단에 주석으로 표시해 뒀다 — 절차는 유효하니 수동 수행.
