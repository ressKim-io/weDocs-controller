---
date: 2026-07-28
category: decision
tier: 2
importance: major
status: resolved
tags: [claude-md, rules, paths-scope, add-dir, polyrepo, craft-gate]
related:
  - dev-logs/2026-07-28-claude-context-budget.md
  - plans/2026-07-28-claude-context-budget.md
---

# `paths:` 스코프 룰은 레포 경계를 넘지 않는다 — 크래프트 게이트는 에이전트로 실행

## Context

- 발생 환경: controller 레포에서 `--add-dir`로 서비스 레포(`weDocs-backend` 등)를 함께 여는 워크플로우
- 트리거: 컨텍스트 예산 정리(1,975→300줄) 후 "나머지 레포에도 적용되나?" 확인 요청

controller의 `.claude/rules/`에는 크래프트 표준 6종을 포함해 언어별 룰 10개가
`paths: **/*.java` 등으로 스코프돼 있다. `CLAUDE.md` 불변규칙 7번은 서비스 코드 PR에
그 `[B]` 체크리스트 통과를 요구한다. **그런데 그 룰이 서비스 레포 파일을 열 때 실제로
로드되는지는 아무도 확인한 적이 없었다.**

서비스 3레포(`weDocs-backend`·`weDocs-crdt-engine`·`weDocs-frontend`)는 각각 별도 git 레포이고
`CLAUDE.md`·`.claude/`가 **하나도 없다**. 상위 디렉토리에도 `CLAUDE.md`가 없어 위에서 내려오는 것도 없다.

## 측정 (추측 대신 실측)

`InstructionsLoaded` 훅을 임시로 걸고 헤드리스 세션(`claude -p`)을 3회 띄워
**하네스가 직접 보고한 로딩 기록**을 받았다. 훅 입력에는 `file_path`·`memory_type`·`load_reason`이 들어온다.

| # | cwd | 읽은 파일 | 스코프 룰 발화 |
|---|---|---|---|
| 1 | controller | `infra/argocd/app-of-apps.yaml` (**레포 내부**) | **2개** — `reason=path_glob_match` |
| 2 | controller `--add-dir ../weDocs-backend` | `../weDocs-backend/buf.gen.yaml` (**동일 글롭**) | **0개** |
| 3 | controller `--add-dir ../weDocs-backend` | `../weDocs-backend/.../DocServiceApplication.java` | **0개** |

**②가 결정적이다.** ①과 정확히 같은 `**/*.yaml` 글롭인데 레포 안에서는 발화하고
add-dir 대상에서는 발화하지 않았다 → 글롭 매칭 실패가 아니라
**`paths:` 스코프가 프로젝트 디렉토리 경계 자체를 넘지 않는다.**

## 결론 — controller에서 서비스 레포를 열 때 실제로 오는 것

| | 상태 |
|---|---|
| `CLAUDE.md` + 상시 룰 4종(workflow·user-approval·plan-logging·token-budget) | ✅ 온다 (`session_start`) |
| `settings.json` 권한·훅(`guard_destructive`·예산 훅·kubectl deny) | ✅ 적용 (세션 단위) |
| 에이전트 20개 · tier1 스킬 6개 | ✅ 호출 가능 |
| **언어·크래프트 룰 10종**(java·spring·error-handling·concurrency·secure-coding·design-patterns·layering-readability·observability·clean-code·security) | ❌ **안 온다** |

즉 "서비스 레포는 브랜치+PR+건별 승인" 같은 **가드레일과 승인 규칙은 따라오는데**,
불변규칙 7번이 요구하는 **크래프트 `[B]` 체크리스트 본문은 그 자리에 없다.**

## 결정 — 옵션 1 (현행 유지 + 에이전트 경유)

에이전트 본문에는 체크리스트 실행 지시가 들어 있고 에이전트 호출은 정상 동작한다.
따라서 **리뷰를 `rust-`/`java-`/`python-expert`로 돌리면 실질적으로 커버된다.**

기각한 대안:
- **서비스 레포 3곳에 룰 커밋** — 정공법이지만 그 레포들은 브랜치+PR+건별 승인이 필요하고,
  룰 사본이 4벌로 늘어 드리프트 지점이 3개 생긴다(`plan-logging.md` §사본을 만들지 않는다와 충돌).
  필요해지면 그때 진행.
- **`paths:`에서 언어 확장자를 빼 상시 승격** — 방금 −85% 줄인 것을 되돌리는 데다,
  controller엔 그 코드가 없어 대부분 세션에서 순수 낭비.
- **`weDocs/`에 공통 `CLAUDE.md`** — git 추적 밖의 PC 로컬 설정이라 전역 오염. 배제.

## 배선 (결정이 잊히지 않도록)

`CLAUDE.md` 불변규칙 7번에 한 절 추가 — 게이트를 요구하는 **바로 그 문장 옆에** 경고를 뒀다.
별도 문서에 적으면 정작 그 순간에 안 읽힌다.

> ⚠️ 그 룰들은 서비스 레포에서 자동 로드되지 않는다(실측 2026-07-28)
> — 반드시 `rust-`/`java-`/`python-expert` 에이전트로 실행할 것.

## 재사용 가능한 교훈

- **`InstructionsLoaded` 훅이 "무엇이 로드되는가"의 ground truth다.** `--debug-file`에는
  메모리 로딩이 안 담긴다. 훅 입력의 `load_reason`이 `session_start`인지 `path_glob_match`인지로
  상시/조건부가 구분된다.
- **로딩 동작을 추론하지 말고 대조군으로 측정한다.** "add-dir에선 안 뜨네"만으로는
  글롭 오류인지 경계 문제인지 못 가린다. **같은 글롭을 안/밖에서 각각** 돌려야 원인이 갈린다.
- 폴리레포에서 "컨트롤 플레인에 룰을 모아두면 다 커버된다"는 가정은 **틀리다.**
  상시 로드(`CLAUDE.md` + `paths:` 없는 룰)만 넘어가고, 조건부 룰은 안 넘어간다.
