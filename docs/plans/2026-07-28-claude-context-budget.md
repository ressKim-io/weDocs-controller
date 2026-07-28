---
date: 2026-07-28
slug: claude-context-budget
status: done
related:
  - dev-logs/2026-07-28-claude-context-budget.md
  - dev-logs/2026-07-28-claude-md-restructure.md
  - plans/2026-07-28-build-test-ci-gap.md
  - plans/2026-06-30-plan-audit-improvements.md
---

# Claude Code 상시 컨텍스트 예산 정합

> controller 전용 작업 (main 직접 커밋 허용). 서비스 레포는 건드리지 않는다.
> 목표: 상시 로드 **1,975 → ~213줄 (−88%)** + 다시 무너지지 않게 **예산 게이트 배선**.

## Context

**왜**: 이 레포의 Claude Code 설정은 **매 세션 1,975줄 / 57,131자 / ~28,700토큰**을 상시 로드한다.
공식 권고(`CLAUDE.md` 200줄 이하)의 약 10배다. 문제는 토큰 비용이 아니라 **준수율**이다 —
프런티어 모델이 일관되게 따르는 지시는 ~150-200개가 한계이고, 무관한 내용이 섞이면
선별 무시가 아니라 **전체 무시**가 일어난다.

2026-07-28 `a9b1f7f`(CLAUDE.md 재구조화)로 CLAUDE.md 자체는 78줄까지 줄였지만,
**로딩 메커니즘을 오해한 채로** 정리해서 실제 상시 로드량은 거의 그대로였다. 이번 작업이 그 후속이다.

### 실측한 3가지 구조적 결함

**1. `@import` 7개 중 5개가 no-op, 2개는 역효과**

`CLAUDE.md:45-52`의 `### 항상 적용 (import)` 블록:

| import | 실제 효과 |
|---|---|
| `clean-code` `workflow` `security` `user-approval` `plan-logging` | **no-op** — `paths:`가 없어 어차피 자동 로드됨 |
| `testing`(151줄) `debugging`(195줄) | **역효과** — 자기 `paths:` 스코프를 무력화해 346줄을 상시로 끌어올림 |

공식 문서: *"Splitting into `@path` imports helps organization but doesn't reduce context,
since imported files load at launch."* / *"Rules without a `paths` field are loaded unconditionally."*

**2. 상시 로드의 ~40%가 다른 프로젝트 내용**

| 파일 | 이 레포와 무관한 내용 |
|---|---|
| `documentation.md` | 문서 14종 표 중 **9종의 디렉토리가 부재** (`load-test`/`finops`/`postmortem`/`cicd`/`sre`/`architecture`/`project`/`migration`/`dx`). §기존 문서 마이그레이션은 타 프로젝트 파일명(`kafka-adoption-decision.md` 등) |
| `user-approval.md` | "현재 해당 앱: 모든 **goti** ApplicationSet", ECR ImagePullBackOff 2026-03-22, `goti-queue-sungjeon-dev` |
| `deep-thinking.md` | Ongilro **Apple/Xcode 26/Privacy Manifest** 사고 서술 ~40줄 |
| `config-contract-audit.md` | Go **Viper** `SetDefault`/`AutomaticEnv` 패턴 — `.claude/README.md`가 "제외: go(이 프로젝트 Go 없음)"라 적어둔 바로 그것 |
| `git.md` | §Branch Protection이 `CLAUDE.md` §커밋·push 규칙과 **정면 모순** |

**3. 중복이 상시 로드 안에서 2중 계상**

- `workflow.md` §디버깅 순서 (4단계) ≡ `debugging.md` §디버깅 프로토콜 (4단계 동일)
- `workflow.md` §Context 효율화 ≡ `token-budget.md` §토큰 절약 실전
- `deep-thinking.md` 전체 ≡ `workflow.md` §신규 도구/버전 도입 시 spec 사전 검증
- `token-budget.md`가 "effort 매핑 SOT는 `effort-guide.md`"라 적어뒀는데 **둘 다 상시 로드**

### 검증 출처 (2026-07-28 WebFetch, ✅ verified)

| 출처 | 인용 |
|---|---|
| [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) | "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence." · `paths:` 없는 rule = launch 시 무조건 로드 · "@imports … doesn't reduce context" |
| [code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills) | `.claude/skills/<name>/SKILL.md` 레이아웃 · "Keep SKILL.md under 500 lines" · 리스팅 예산 = 컨텍스트의 1%, 초과 시 **덜 쓰는 스킬 설명부터 조용히 잘림** |
| [Anthropic steering 블로그](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) | 절차 → skill, 절대 금지 → hook · "If a rule only applies to `src/api/**`, scoping it with `paths:` keeps it out of context during unrelated work." |
| [zenn 사례연구](https://zenn.dev/yottayoshida/articles/claude-code-context-cost-structure?locale=en) | 1,358 → 807줄(−41%) 실측. 결론: "demoting rules to skills provides the most leverage" |
| [DEV: 100 subagents](https://dev.to/suraj_khaitan_f893c243958/i-built-100-claude-code-subagents-these-are-the-12-that-actually-earn-their-context-10nn) | 설명 필드 중복이 오라우팅 유발 |

### 사전 정정 (초기 분석 중 틀렸던 것 — `deep-thinking.md` §자기 강화 추정 루프 회피)

| 초기 주장 | 실제 | 근거 |
|---|---|---|
| "flat skill 레이아웃은 버그" | **의도된 설계** | `.claude/README.md`: "형식 주의: 대부분 flat `.md` 지식 파일이라 자동 발견(`SKILL.md`) 대상이 아님 — 룰/에이전트가 참조하는 레퍼런스로 동작" → 198개 일괄 마이그레이션은 리스팅 예산 초과로 **역효과**. 7개만 승격 |
| "`saga-agent`는 미사용" | **배정되어 있음** | `CLAUDE.md:66` "아키텍처 `architect-agent`(proto·계약)·`saga-agent`(outbox)" + `docs/status/current.md` Phase 5 outbox. 스택 스캔이 0을 낸 건 agent 설명 어휘가 Temporal 편향이라서 → 삭제 아닌 **리타게팅** |
| 크기를 `wc -c`로 측정 | **바이트지 문자가 아님** | 한글 ~1.58 byte/codepoint. 90,214바이트 = **57,131자**. 예산 임계값은 코드포인트 기준이어야 함 |

---

## 실행 체크리스트

### 1단계 — 기계적 (산문 0줄 수정, 커밋 단위 revert 가능)

- [x] **C0** `docs(plans):` 이 파일 커밋 (`planned` → `in-progress`)
- [x] **C1** `ci:` `scripts/claude_context_budget.py` 신설 — 임계값은 현재값+5%로 두어 무수정 통과
- [x] **C2** `chore(claude):` `CLAUDE.md` @import 블록 삭제 → **−346줄**
- [x] **C3** `chore(claude):` `paths:` 스코프 전환 → **−625줄**
- [x] **C4** `chore(claude):` `cloud-cli-safety.md` 삭제 + `user-approval.md` 상호참조 정정 (**동일 커밋**) → −43줄
- [x] **C5** `ci:` `.github/workflows/claude-context-budget.yml` + 임계값 1단계 하향 + `ci/README.md` 한계 명시
- [ ] **── 체크포인트: 1,975 → ~813줄 (−59%). 산문 미수정 ──**

### 2단계 — 내용

- [x] **C6** `chore(claude):` `.claude/settings.json` + `scripts/guard_destructive.py`
- [x] **C7** `refactor(claude):` `workflow.md` 119→35 (중복 2절 삭제) + `deep-thinking` 핵심 12줄 흡수 → ~−220줄
- [x] **C8** `refactor(claude):` `git.md`·`effort-guide.md` **`git mv`로 skill 이동**, `token-budget.md` 64→18 → ~−329줄
- [x] **C9** `refactor(claude):` `user-approval.md` 159→45, `plan-logging.md` 122→45 → ~−191줄
- [x] **C10** `chore(claude):` 에이전트 댕글링 참조 11건 + `platform-engineer` 제거 + 설명 리타게팅 3건
- [x] **C11** `docs(claude):` `.claude/README.md` skill 2계층 명시, 죽은 `/슬래시` 20건 → 경로 링크
- [x] **C12** `ci:` 임계값을 2단계 목표로 하향 — **래칫은 별도 커밋**
- [x] **C13** `docs:` `status: done` + dev-log + `docs/status/current.md` §열린 트랙 역방향 점검

---

## 파일별 처분 (상시 로드 15개 전부)

**핵심 원리**: 서비스 코드가 별도 레포이므로, 코드 룰에 `**/*.java` 등을 붙이면
**이 레포에서 토큰 0인데 파일은 디스크에 남는다** = 삭제와 동일한 절감 + 되돌리기 가능.
그래서 **삭제는 `cloud-cli-safety.md` 1건뿐**이다.

| 파일 | 현재 | 처분 | `paths:` / 이동처 | 근거 |
|---|---:|---|---|---|
| `workflow.md` | 119 | 유지 → **35** (+12) | — | EXPLORE/PLAN/…/COMMIT·Blast Radius는 파일 트리거가 없어 상시 필요. §디버깅 순서·§Context 효율화 삭제(중복) |
| `user-approval.md` | 159 | 유지 → **45** + hook | — | 최고 위험도. §포괄 위임 하에서도 건별 승인은 **원문 유지**(훅으로 표현 불가한 판단). goti/ECR/ArgoCD 복구 절차 → dev-log |
| `plan-logging.md` | 122 | 유지 → **45** | — | plan 작성 시점엔 매칭할 파일이 없어 상시 필요. frontmatter 규격 → `templates/plan.md.template`, 사고 서술 3건 → 기존 dev-log |
| `token-budget.md` | 64 | 유지 → **18** | 잔여 → skill | 세션 운영 규칙만 상시. tokenizer/캐시 수치는 stale-prone 레퍼런스 |
| `deep-thinking.md` | 136 | 핵심 12줄 → `workflow.md`, 본문 **`paths:` 보관** | `"**/docs/research/**"`, `"**/*verification*"` | 실행 핵심 = cutoff 자각→WebFetch · unverified 인용 금지 · verified/URL/날짜 마킹 |
| `git.md` | 140 | **`git mv` → skill** + 4줄 → CLAUDE.md | `.claude/skills/git-conventions/SKILL.md` | 커밋 타입표·브랜치명·PR 템플릿은 커밋할 때만 필요. **브랜치 정책 소유권을 CLAUDE.md로 일원화**(모순 해소) |
| `effort-guide.md` | 143 | **`git mv` → skill** | `.claude/skills/context-and-effort/SKILL.md` | 자기 소개가 "새 agent 작성 시 참조하는 조회표". 모델/가격표 = "자주 바뀌는 정보"(공식 배제 기준). `token-budget` 잔여와 **한 스킬로 병합** → SOT 분열 해소 |
| `documentation.md` | 154 | `paths:` + 재작성 → **~55** | `"**/docs/**"` | 14종 중 9종 부재. 실재: `adr design dev-logs onboarding plans prd retrospective sdd status`. **`**/*.md` 금지**(모든 룰·스킬 읽기에 발화) |
| `config-contract-audit.md` | 135 | `paths:` + trim → **~70** | `"**/*.yaml"` `"**/*.yml"` `"**/*.tf"` `"**/*.tfvars"` `"**/.env*"` | 발화면 실재: `infra/k8s/**/kustomization.yaml`·`infra/argocd/app-of-apps.yaml`·`buf.gen.yaml`·`.github/workflows/*.yml`. Go/Viper 절 제거 |
| `professional-writing.md` | 142 | **`paths:`** → 0 | `"**/portfolio/**"` `"**/docs/onboarding/**"` `"**/*포트폴리오*"` `"**/*이력서*"` `"**/*발표*"` | 자기 4행이 "일반 코드 주석이나 기술 문서에는 적용하지 않는다" = 이 레포의 100%. **`**/README.md` 의도적 제외**(README 8개 전부 기술 문서) |
| `clean-code.md` | 75 | **`paths:`** → 0 | `"**/*.java"` `"**/*.rs"` `"**/*.py"` `"**/*.ts"` `"**/*.tsx"` | 코드 룰인데 이 레포에 코드 없음. 이미 스코프된 `layering-readability`·`design-patterns`와 중복 |
| `security.md` | 119 | **`paths:` (삭제 아님)** → 0 | `security-appsec.md`로 rename, 코드 확장자 5종 | ⚠️ **동시에 `secure-coding.md`의 `paths:`에 `"**/.github/workflows/**"` 추가** — 안 하면 `secrets.GITHUB_TOKEN` 다루는 워크플로우 편집 시 보안 룰이 0이 됨 |
| `cloud-cli-safety.md` | 43 | **삭제 (유일)** | — | 참조 대상 `.claude/skills/operations/`가 **미존재**(README "더 필요하면 추가 도입" 목록). homelab KinD라 AWS/GCP CLI 없음. 실효 규칙(destructive 사전 승인·`--force` 금지)은 `user-approval.md`에 2줄 흡수 |
| `testing.md` | 151 | **@import 제거** + 글롭 타이트닝 | `"**/*Test.java"` `"**/*_test.rs"` `"**/test_*.py"` `"**/*.spec.ts"` `"**/tests/**"` `"**/src/test/**"` | 내용 변경 0. 현재 `**/*test*`가 `docs/plans/2026-07-28-build-test-ci-gap.md`에 오발화 |
| `debugging.md` | 195 | **@import 제거**, `paths:` 유지 | — | 내용 변경 0. `**/dev-logs/**`로 자주 발화하는 건 정상 동작 |

**예상 결과**: CLAUDE.md ~56 + workflow ~47 + user-approval ~45 + plan-logging ~45 + token-budget ~18
= **~211줄 / ~7,000자 / ~3,500토큰**

---

## CLAUDE.md 목표 (78 → ~56줄)

| 구간 | 조치 |
|---|---|
| 헤더·진입점·**§불변 규칙 8항**·언어 배정·자주 하는 일 (1–29) | **원문 유지** — 레포 고유·비자명·추론 불가 = 공식 문서가 정의하는 CLAUDE.md 그 자체 |
| §현재 상태·재개 (31–37) | **유지** — 포인터-only 설계는 이미 옳음(`a9b1f7f`) |
| `> 왜 여기 안 쓰나` 블록인용 (38) | `docs/dev-logs/2026-07-28-claude-md-restructure.md`로 이동 (사람용 근거지 지시 아님) |
| **`### 항상 적용 (import)` + @import 7줄 (45–52)** | **블록 통째 삭제**, 대체 없음 — 룰은 frontmatter로 자체 스코프 |
| `### 상황별 룰` 파일명 ~30개 (54–64) | `.claude/README.md`로 이동. 설정 파일 인벤토리는 지시가 아니라 **드리프트 지점**(지금도 삭제 예정인 `cloud-cli-safety.md`를 나열 중) |
| `### 서브에이전트` 21개 이름 (66–68) | `.claude/README.md`로 이동 — Claude Code가 이름+설명을 이미 자동 노출(5,063자 실측). 재기술은 순수 중복 |
| §커밋·push 규칙 (72–78) | **유지 + 강화** — `git.md`의 4개 불가침(force push 금지·시크릿 금지·`git add .` 지양·논리 단위 분할) 흡수 |

---

## Skills — 7개만 승격, ~190개는 그대로

승격 기준: 모델이 자율 호출해야 하는 **절차**이면서, 동시에 **삭제되는 상시 로드 텍스트를 대체**하는 것.

| 스킬 | 출처 | 이유 |
|---|---|---|
| `git-conventions` | `rules/git.md` (`git mv`) | 위 표 대체 |
| `context-and-effort` | `effort-guide.md` + `token-budget.md` 잔여 + `skills/dx/token-efficiency.md` | SOT 분열 해소 |
| `documentation-templates` | `skills/dx/` 이동 | `documentation.md:93`이 참조 |
| `clean-code` | `skills/dx/` 이동 | `clean-code.md` 푸터가 참조 |
| `phase-start` | `rules/phase-workflow.md` 게이트 | 룰 5곳에서 참조 |
| `crdt-yrs` · `crdt-convergence-testing` | `skills/rust/` 이동 | `rust-expert` 설명이 "skills/rust/crdt-yrs 로드"라 하는데 **현재 불가능**. 이 레포 ★핵심 |

리스팅 비용 7 × ~200자 ≈ **1,400자** / 예산 = 컨텍스트의 1%(1M ctx ≈ 35k자) → 안전.
198개 전부 승격하면 ~40k자로 **초과 → 덜 쓰는 스킬 설명부터 조용히 잘림**. 그래서 승격하지 않는다.

나머지 ~190개는 **구조 변경 없음**. 대신:
1. 룰의 죽은 `` `/x` `` **20건** → `Read` 가능한 경로 링크로 (예: `` `/clean-code` `` → `` `.claude/skills/dx/clean-code.md` ``)
2. `.claude/README.md`에 **2계층 모델 명문화**: tier1 = `<name>/SKILL.md`(자동 발견, ≤12개, 예산 관리 대상) / tier2 = `<category>/*.md`(수동 Read 레퍼런스)
3. 자산 표 `199 → 198` 실측치 정정

---

## Agents — 정확성 수정 위주 (설명 합계 5,063자 = 전체 문제의 ~9%)

**댕글링 참조 11건 제거** (설명만 수정, 본문 무변경):

| 부재 에이전트 | 참조 위치 |
|---|---|
| `business-decision-agent` | `architect-agent` `tech-lead` `templates/AGENT-SPEC.md` |
| `compliance-strategy-agent` | `architect-agent` `templates/AGENT-SPEC.md` |
| `cicd-security-reviewer` | `cicd-reviewer` |
| `container-security-reviewer` | `dockerfile-reviewer` |
| `frontend-expert` `go-expert` | `code-reviewer` `templates/AGENT-SPEC.md` |
| `k8s-security-reviewer` | `k8s-reviewer` `templates/AGENT-SPEC.md` |
| `grafana-agent` | `otel-expert` `skills/observability/observability-otel-migration.md` |
| `pilot-agent` | `service-mesh-expert` `debugging-expert` `skills/dx/dx-ai-agents.md` |
| `platform-strategy-agent` | `platform-engineer` |
| `database-expert-mysql` | `database-expert` |

→ **`.claude/templates/AGENT-SPEC.md`도 같이 고칠 것** (안 하면 다음 에이전트 작성 시 재발)

- **제거 1건**: `platform-engineer` (Backstage/IDP, 신호 0, 솔로 레포). 21 → 20
- **리타게팅 3건**: `saga-agent` → Temporal 빼고 "outbox·멱등성(M2 Phase 5)" 선두 / `messaging-expert` → Kafka 선두 / `database-expert` → MySQL 절 제거
- `k8s-troubleshooter`/`k8s-reviewer`/`gitops-reviewer`는 **첫 절만 서로 겹치지 않게** 정리 (오라우팅은 첫 절 중복에서 발생)
- **개수 자체는 유지** — 이 레포의 에이전트 도메인은 실제 폴리글랏 스택과 1:1 대응. 문제는 개수가 아니라 설명 품질

---

## `.claude/settings.json` (신규)

```jsonc
{
  "includeCoAuthoredBy": false,          // git.md의 Co-Authored-By 금지를 결정론적 강제 (산문 8줄 불요)
  "skillListingBudgetFraction": 0.01,    // 기본값이지만 명시 = 회귀 감지 지점
  "skillListingMaxDescChars": 1536,
  "permissions": {
    "allow": [
      "Bash(buf lint:*)", "Bash(buf breaking:*)", "Bash(buf format:*)", "Bash(buf generate:*)",
      "Bash(git status)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)",
      "Bash(kubectl get:*)", "Bash(kubectl describe:*)", "Bash(kubectl logs:*)", "Bash(kubectl top:*)",
      "Bash(gh pr view:*)", "Bash(gh issue view:*)", "Bash(gh run list:*)"
    ],
    "deny": [
      "Bash(kubectl apply:*)", "Bash(kubectl delete:*)", "Bash(kubectl patch:*)",
      "Bash(kubectl edit:*)", "Bash(kubectl scale:*)", "Bash(kubectl rollout:*)",
      "Read(./.env)", "Read(./**/*.pem)", "Read(./**/*.key)"
    ]
  },
  "hooks": {
    "PostToolUse": [{ "matcher": "Edit|Write|MultiEdit",
      "hooks": [{ "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/claude_context_budget.py\" --quiet-if-ok" }] }],
    "PreToolUse": [{ "matcher": "Bash",
      "hooks": [{ "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/guard_destructive.py\"" }] }]
  }
}
```

**deny와 훅을 나눈 이유**: `Bash(...)` deny는 **접두사 매칭**이라 `kubectl apply …`는 확실히 잡지만
`argocd app sync --force myapp` ↔ `argocd app sync myapp --force`, `git push -f` ↔ `git push --force` 같은
**플래그 순서 의존** 케이스는 못 잡는다. 접두사로 안정적인 금지는 `deny`에, 순서 의존 금지는
`guard_destructive.py`가 커맨드 전체를 정규식으로 보고 `permissionDecision: "deny"` 반환.
`user-approval.md` §ArgoCD Force Sync 금지가 정확히 이 케이스다 — **deny 리스트가 완전하다고 착각하지 않는 것**이 요점.

---

## 강제 수단

### `scripts/claude_context_budget.py` (신규, stdlib only)

**측정 대상 = 실제로 로드되는 것만**:

```
CLAUDE.md
+ .claude/rules/**/*.md 중 frontmatter에 paths: 키가 없는 것
+ CLAUDE.md에서 실제 @import로 도달하는 파일 (재귀, depth ≤ 5)
− 절대경로 기준 중복 제거
```

**오탐 함정 — 전부 이 트리에서 실측 확인**:

| ID | 함정 | 처리 |
|---|---|---|
| FP-1 | **frontmatter가 아예 없는 룰** — `clean-code.md`·`token-budget.md`는 `# `로 시작 | frontmatter는 **1행이 정확히 `---`일 때만** 존재. 없으면 = 상시 로드 |
| FP-2 | 본문 산문·YAML 예시에 `paths:` 등장 | 구분자 블록 **안에서만** 파싱. 본문 grep 금지 |
| FP-3 | **`^@`는 @import가 아니다** — 코드펜스 안 `@Transactional`(spring 3) `@Bean` `@Test` `@Entity` `@RestControllerAdvice` `@DisplayName` `@EqualsAndHashCode` 등 **가짜 10건** 실측 | 펜스(```/~~~) 상태 추적 스킵 + inline code span 스킵 + **`@` 뒤 토큰이 실제 파일로 resolve될 때만** 인정 |
| FP-4 | @import이면서 `paths:` 없는 파일은 1회만 계상 — 그 중복이 지금 고치는 버그 | 1회 계상 + `WARN: @import X는 no-op` 출력 |
| FP-5 | `paths:` 키는 있는데 비어 있음(`paths:` / `paths: []`) | 상시 로드로 분류 **+ 경고** |
| FP-6 | **한글은 바이트≠문자** (여기선 1.58 byte/codepoint) | UTF-8로 읽고 **코드포인트**로 예산. 줄/자/바이트/추정토큰 전부 출력해 교차검증 |
| FP-7 | `~/.claude/CLAUDE.md`도 로드되지만 CI는 못 봄 | 프로젝트 메모리로 범위 명시 + 안내 출력. gitignore된 `CLAUDE.local.md` 존재 시 경고 |

**임계값 — 2계층, 둘 다 blocking**

*Tier A — 상시 로드 (빡빡하게, 통제 대상)*

| 항목 | 1단계 | 2단계 |
|---|---:|---:|
| 상시 로드 총 줄수 | ≤ 900 | **≤ 300** |
| 상시 로드 총 코드포인트 | ≤ 26,000 | **≤ 9,000** |
| CLAUDE.md 줄수 | ≤ 150 | **≤ 80** |
| 상시 로드 개별 룰 줄수 | ≤ 160 | **≤ 60** |
| CLAUDE.md의 실제 @import 수 | ≤ 2 | **= 0** |
| no-op @import (FP-4) | = 0 | = 0 |

*Tier B — 참고 문서 길이 예산 (오늘의 최댓값보다 살짝 위 → 진짜 회귀에만 발화)*

| 항목 | 상한 | 오늘의 최댓값 |
|---|---:|---|
| `paths:` 스코프 룰 줄수 | ≤ 200 | `debugging.md` **195 (97% 소진)** ← 첫 실질 신호 |
| `skills/*/SKILL.md` 줄수 | ≤ 300 | — |
| `skills/*/SKILL.md` 개수 | ≤ 12 | 승격 후 7 |
| SKILL.md `description` 자수 | ≤ 400 | — |
| flat `skills/<cat>/*.md` 줄수 | ≤ 700 | `dx/local-dev-makefile.md` 636 |
| 에이전트 본문 줄수 | ≤ 620 | `java-expert.md` **605** |
| 에이전트 `description` 자수 | ≤ 400 | `architect-agent.md` 371 |
| 에이전트 description 합계 | ≤ 5,200 | 5,063 |

플래그: `--json` (§검증용) · `--quiet-if-ok` (훅 모드) · `--tier a|b|all`

### `.github/workflows/claude-context-budget.yml` (신규)

`security-scan.yml`의 "주석으로 근거 남기는" 스타일 + `actions/checkout@v6` 승계.
트리거 = `pull_request`(paths 필터) + `push: branches:[main]` + `workflow_dispatch`.
`schedule:` 없음 — gitleaks와 달리 커밋 없이 드리프트하는 경로가 없다.

**`ci/README.md`에 한계를 정직하게 명시**: 이 레포는 main 직접 push라 `pull_request` 레그는 **실제로 안 걸린다**.
`push: main` 레그는 **사후 탐지**(main에 빨간 X). **실시간 차단은 `PostToolUse` 훅**이 담당.

---

## 검증

각 커밋 후:

```bash
python3 scripts/claude_context_budget.py --json
grep -c '^@' CLAUDE.md                           # C2 이후 0
grep -rn 'cloud-cli-safety' .claude/ CLAUDE.md   # C4 이후 0
ls .claude/skills/*/SKILL.md | wc -l             # C8 이후 7 (상한 12)
```

**게이트 실측 검증** (C1에서 수행 — 문서만 쓰지 말고 게이트까지 배선):

1. **기준선 재현**: `--json`이 정확히 `1,975줄 / 57,131자 / 90,214바이트 / 16파일`을 뱉는가
2. **음성 테스트**: `clean-code.md`에 임시 `paths:` 추가 → 카운트가 정확히 **75** 감소 → 원복
3. **FP-3 테스트**: `imports: 7`로 보고하는가 (17 아님 — 가짜 10건이 안 잡혀야)
4. **임계값 테스트**: C5에서 임계값을 현재값 아래로 잠깐 내려 exit 1 + 읽을 만한 메시지 확인 → 원복

**스코프 동작 확인** (C3 이후): 세션에서 `/context`의 Memory files 목록으로,
`infra/k8s/base/kustomization.yaml`을 열면 `config-contract-audit`가 로드되고 `proto/**/*.proto`를 열면 안 되는지.

**훅 확인** (C6 이후): `/hooks`에 2개 등록 → `.claude/rules/*.md` 편집 시 예산 라인 출력 →
`kubectl delete pod x`가 deny → `argocd app sync a --force`가 **deny 리스트가 아닌 훅**에 걸리는지.

---

## 재개 지점 (Resume)

```
마지막 완료 = C13 (전 단계 완료 — 2026-07-28)
다음        = 없음. 이 plan은 done.
결과        = 상시 로드 1,975 → 300줄 (−85%) / 57,131 → 12,296자 / ~28.7k → ~6.2k토큰
              게이트 3중 배선(스크립트 + push:main CI + PostToolUse 훅), stage2 임계값 래칫 완료
회고        = docs/dev-logs/2026-07-28-claude-context-budget.md
```

### 계획 대비 달라진 것 (근거와 함께)

| 항목 | 계획 | 실제 | 왜 |
|---|---|---|---|
| `security.md` rename | `security-appsec.md` | 유지 | ADR-0021·secure-coding·plan 3곳이 파일명으로 참조 — `paths:`만으로 토큰 결과 동일 |
| stage1 임계값 | 900줄 / 26,000자 | 1,000 / 33,000 | 계획 추정이 `effort-guide`(143줄)를 누락. 실측 961줄 |
| stage2 임계값 | 300줄 / 9,000자 | 340 / 14,000 | 자수 추정이 한글 밀도를 낮게 봄. 실측 12,296자 |
| SKILL.md 상한 | 300줄 | 500줄 | 300은 임의값, 공식 권고가 "under 500". 훅이 `clean-code`(474줄)를 막아 발견 |
| 댕글링 에이전트 | 11건 | **9건** | `grafana-agent`(Grafana 제품명)·`pilot-agent`(Istio CLI)는 오탐 — 서브에이전트 아님 |
| C3 내용 재작성 | `documentation`·`config-contract-audit` 본문 trim 포함 | frontmatter만 | 1단계의 "산문 0줄 수정" 성질 유지. 스코프 후엔 예산 무관이라 급하지 않음 |

## 범위 밖

- flat 레퍼런스 스킬 ~190개 마이그레이션 — 리스팅 예산 초과로 역효과
- `debugging.md`의 K8s 절 분리 — 선택적, 나중
- 이미 `paths:` 스코프된 룰 18개의 **본문** 수정
- 서비스 레포(`backend`/`crdt-engine`/`frontend`) — 브랜치+PR+건별 승인 필요
