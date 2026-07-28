---
date: 2026-07-28
category: meta
tier: 2
importance: critical
status: resolved
tags: [claude-md, context-budget, rules, skills, hooks, ci-gate, drift]
related:
  - dev-logs/2026-07-28-claude-md-restructure.md
  - plans/2026-07-28-claude-context-budget.md
---

# 상시 로드 컨텍스트 1,975 → 300줄 — 룰을 지운 게 아니라 로딩 시점을 고쳤다

## Context

- 발생 환경: controller 레포 `.claude/` 전체 (Claude Code 설정)
- 트리거: "claude code 효율 극대화를 위한 설정 조정" 요청 → 상시 로드량 실측

직전 작업(`2026-07-28-claude-md-restructure`, `a9b1f7f`)에서 CLAUDE.md 자체는 78줄까지 줄였다.
그런데 **로딩 메커니즘을 오해한 채로** 정리해서, 실제 상시 로드량은 거의 그대로였다.
측정해 보니 **매 세션 1,975줄 / 57,131자 / ~28,700토큰**. 공식 권고(200줄)의 약 10배.

## 근본 원인 — 3가지가 겹쳐 있었다

**1. `@import`가 절감 수단이라는 오해.**
CLAUDE.md의 `### 항상 적용 (import)` 블록에 7개가 있었는데:
- 5개(`clean-code`·`workflow`·`security`·`user-approval`·`plan-logging`)는 `paths:`가 없어
  **어차피 자동 로드**되는 파일이었다 → import는 순수 no-op
- 2개(`testing` 151줄 · `debugging` 195줄)는 자기 `paths:` 스코프를 가진 파일인데
  import가 그 스코프를 **무력화**해 346줄을 상시로 끌어올리고 있었다

공식 문서가 명시한다: *"Splitting into `@path` imports helps organization but doesn't reduce
context, since imported files load at launch."* — 조직화 수단이지 절감 수단이 아니다.

**2. 상시 로드의 ~40%가 다른 프로젝트 내용.**
`documentation.md`의 문서 14종 표 중 **9종의 디렉토리가 이 레포에 없었고**,
`user-approval.md`는 goti ApplicationSet·ECR 사고, `deep-thinking.md`는 Ongilro Apple/Xcode 사고,
`config-contract-audit.md`는 Go Viper 패턴을 담고 있었다 — `.claude/README.md`가
"제외: go(이 프로젝트 Go 없음)"라고 적어둔 바로 그 내용이.

토큰보다 이게 더 위험하다. 관측된 실패 양상은 **선별 무시가 아니라 전체 무시**다
(프런티어 모델이 일관되게 따르는 지시는 ~150-200개가 한계).

**3. 중복이 상시 로드 안에서 2중 계상.**
`workflow §디버깅 순서` ≡ `debugging.md §디버깅 프로토콜`(4단계 동일),
`workflow §Context 효율화` ≡ `token-budget §토큰 절약 실전`,
`deep-thinking` 전체 ≡ `workflow §신규 도구 spec 사전 검증`.
`token-budget.md`는 "effort SOT는 `effort-guide.md`"라고 적힌 채 **둘 다 상시 로드**였다.

## 해결

**원칙: 지우지 않고 로딩 시점을 바꾼다.** 서비스 코드가 별도 레포이므로
코드 룰에 `**/*.java` 같은 `paths:`를 붙이면 **이 레포에서 토큰 0인데 파일은 남는다**
= 삭제와 동일한 절감 + 되돌리기 가능. 실제 삭제는 1건뿐이었다.

| 단계 | 조치 | 상시 로드 |
|---|---|---|
| — | 시작 | 1,975줄 / 57,131자 |
| C2 | `@import` 블록 제거 | 1,624 (−351) |
| C3 | 코드·설정·문서 룰 5종 `paths:` 스코프 | 999 (−625) |
| C4 | `cloud-cli-safety.md` 삭제(유일) | 961 (−38) |
| C7 | `workflow` 중복 2절 제거 + `deep-thinking` 핵심 흡수 | 761 (−200) |
| C8 | `git`·`effort-guide` → skill `git mv`, `token-budget` 축약 | 452 (−309) |
| C9 | `user-approval`·`plan-logging` 사례 서술 분리 | **300 (−152)** |

**−85% (1,975 → 300줄 / ~28.7k → ~6.2k토큰).** 규칙은 하나도 잃지 않았다 —
핵심 문구 7종(건별 승인 · "짜증을 내더라도" · announcement≠승인 · kubectl 직접 변경 금지 ·
Force Sync · 작업 시작 전 commit · 역방향 점검)을 grep으로 보존 확인했다.

**삭제 1건의 근거**: `cloud-cli-safety.md`는 "활성화 가이드"인데 활성화 대상인
`.claude/skills/operations/`가 **존재하지 않았다**. 43줄 전부가 없는 파일을 가리키고 있었다.

## 재발 방지 — 문서가 아니라 게이트

이 정리는 놔두면 다시 무너진다. 그래서 예산을 **강제**했다:

- `scripts/claude_context_budget.py` — 실제 로드되는 것만 측정(CLAUDE.md + `paths:` 없는 룰
  + 실제 `@import` 재귀). Tier A(상시 로드) + Tier B(참고 문서 길이) 2계층.
- `.github/workflows/claude-context-budget.yml` — push:main **사후 탐지**
- `.claude/settings.json` PostToolUse 훅 — `.claude/**` 편집 시 **세션 안에서 즉시** 차단

main 직접 push 레포라 PR 게이트는 실제로 안 걸린다. 그 한계를 `ci/README.md`에 명시했다 —
게이트를 두는 것과 게이트가 무는 것은 다르다.

## 이번에 배운 것 (재사용 가능)

**측정 스크립트의 오탐 7종은 전부 이 트리에서 실제로 밟았다.** 특히:
- **`^@`는 `@import`가 아니다** — 코드펜스 안의 `@Transactional`·`@Bean`·`@Test`·`@Entity` 등
  **가짜 10건**. 순진한 grep은 7이 아니라 17을 센다. 펜스 추적 + 실재 파일 resolve 확인 필수.
- **frontmatter가 아예 없는 룰이 있다**(`clean-code`·`token-budget`은 `#`로 시작).
  `---` 블록을 전제한 파서는 오분류한다.
- **`wc -c`는 바이트지 문자가 아니다** — 한글 ~1.58 byte/codepoint. 바이트로 예산을 잡으면
  한글을 1.5~3배 계상해 임계값이 무의미해진다.

**임계값은 희망이 아니라 실측을 따른다.** 계획서 추정(stage1 900줄 / stage2 9,000자)을
그대로 썼으면 게이트가 첫날부터 red였다(실제 961줄 / 12,296자). red가 상시화된 게이트는
배선 안 한 것보다 나쁘다 — 신호가 죽는다. 두 단계 모두 실측 + 헤드룸으로 잡았다.

**훅은 켠 직후 자기 자신에게 걸린다 — 그게 검증이다.**
`guard_destructive.py`가 오탐 2종을 즉시 드러냈다: ① 전체 문자열 검색이라 인용부호 안
텍스트에도 발화 ② heredoc 본문을 줄 단위로 명령 오인. 둘 다 "사고 명령을 문서·커밋 메시지에
인용하는 것"을 막던 오탐이라, 세그먼트 앵커링 + heredoc 제외로 교정하고 회귀 테스트 22건을 남겼다.
PostToolUse 예산 훅도 `clean-code`(474줄) 승격을 실제로 막았는데, 확인해 보니 내가 잡은
상한 300이 근거 없이 빡빡한 값이었다(공식 권고 500). **게이트가 물었을 때 통과시킬지
임계값을 고칠지는 근거로 판단한다** — 둘 다 "게이트를 무시한다"와는 다르다.

**이름 기반 grep은 문맥 확인 없이 믿지 않는다.** 댕글링 에이전트 11건 중 2건
(`grafana-agent`·`pilot-agent`)은 오탐이었다 — 각각 Grafana Agent 제품명과
Istio Envoy의 `pilot-agent` CLI 바이너리. 서브에이전트가 아니었다.

## 남은 것

- tier 2 스킬 194개는 그대로. 일괄 승격하면 리스팅 예산(컨텍스트의 1%)이 넘쳐
  덜 쓰는 스킬 설명부터 잘린다 — tier 1의 이점 자체가 사라진다.
- 미도입 슬래시 커맨드 9종(`/phase-start`·`/review-pr`·`/log-*`)은 해당 룰 상단에
  "미도입" 주석으로 표시만 했다. 필요해지면 `ress-claude-agents`에서 도입.
