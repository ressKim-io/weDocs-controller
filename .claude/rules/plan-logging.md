# Plan Logging Rules — 재개 가능한 영구 plan 로그 (MANDATORY)

비자명한 작업의 plan을 수립할 때, **실행 전에 plan을 repo에 영구 기록하고 커밋**한다.
세션이 유실되어도 다음 세션이 `docs/plans/` 최신 파일만 열면 **재도출 없이 이어서** 작업할 수 있게 하는 것이 목적.

> 배경: harness plan 파일(`~/.claude/plans/<random>.md`)은 휘발성·랜덤명이라 세션 종료 시 사실상 분실된다. 실제로 직전 세션의 다음-할-일이 dev-log 한 줄로만 남아, 새 세션이 proto·SDD·버전을 전부 다시 찾아야 했다. plan은 repo의 1급 산출물로 남긴다.

---

## 트리거 (MANDATORY)

- **Plan Mode를 사용하는 모든 작업** (= multi-file / 아키텍처 결정 / 신규 모듈 등 `workflow.md` PLAN 단계 대상)
- 4+ 파일 또는 인프라 변경 (`workflow.md` Blast Radius 대상)
- 여러 세션에 걸칠 가능성이 있는 작업

단순 1-2 파일 수정·오타·읽기 작업은 대상 아님.

---

## 위치 / 파일명

```
docs/plans/YYYY-MM-DD-<slug>.md
```

- `slug`은 작업을 식별하는 kebab-case (예: `m1-repo-scaffold`)
- harness plan 파일이 아니라 **이 repo 파일이 SSOT**. harness plan은 작업용 임시본일 뿐.

---

## Frontmatter 표준 (MANDATORY)

```yaml
---
date: YYYY-MM-DD
slug: <kebab-case>
status: planned | in-progress | done | abandoned
related:
  - adr/NNNN-...md
  - dev-logs/YYYY-MM-DD-...md
---
```

| status | 의미 |
|--------|------|
| `planned` | 작성 완료, 실행 전 |
| `in-progress` | 실행 중 (체크리스트 일부 완료) |
| `done` | 전 단계 완료 + 결과 dev-log 링크 |
| `abandoned` | 중단/대체 — 사유 + 대체 plan 링크 명시 |

---

## 필수 섹션 (MANDATORY)

1. **Context** — 왜 이 작업인가, 무엇을 확정했는가(결정·근거·검증 출처)
2. **실행 체크리스트** — 단계를 `- [ ]` 체크박스로. 완료 시 `- [x]` + 커밋 해시(짧게)
3. **검증** — 각 단계/전체를 어떻게 검증하는지 (명령어 포함)
4. **재개 지점 (Resume)** — **세션이 끊기면 여기부터**. `마지막 완료 = … / 다음 = … / 주의 = …` 한 블록. 단계 완료마다 갱신
5. **범위 밖** — 이 plan에서 하지 않는 것 (scope creep 방지)

---

## 라이프사이클 (MANDATORY 순서)

```
1. plan 작성 (docs/plans/...md, status: planned)
2. ★ 작업 시작 전 commit  ← 재개 보장의 핵심. 이 커밋 없이 코드 작업 금지
3. status: in-progress 로 갱신
4. 각 단계 완료마다: 체크박스 [x] + 재개 지점 갱신 + 주기적 commit
5. 전 단계 완료: status: done + 결과 dev-log 링크 추가 + commit
```

- **2번이 빠지면 이 룰의 의미가 없다.** plan 커밋 → 그 다음 실제 작업.
- 단계가 길면 단계 경계마다 plan 갱신 커밋을 끼워, 어느 시점에 끊겨도 재개 지점이 최신.
- controller 레포는 `CLAUDE.md` §커밋·push 규칙상 main 직접 커밋 허용 → plan 커밋도 직접.

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| plan을 repo에 커밋하지 않고 코드 작업 시작 | 세션 유실 시 재도출 — 이 룰의 존재 이유 위반 |
| 재개 지점(Resume) 미갱신 채 다음 단계 진행 | 끊기면 "어디까지 했는지" 불명 |
| harness plan(`~/.claude/plans`)만 믿고 repo 기록 생략 | 휘발성 — 사실상 미기록 |
| `status` 방치 (planned인데 이미 절반 실행) | 재개 시 상태 오판 |

---

## 다른 룰과의 관계

- `workflow.md` §PLAN / §Blast Radius — plan의 **내용** 표준. 본 룰은 그 plan의 **영구 기록·재개** 표준
- `phase-workflow.md` — `/phase-start` 게이트. Phase 작업이면 plan 로그와 병행
- `devlog-lifecycle.md` — plan `done` 시 결과는 dev-log로. plan=전향(할 일) / dev-log=후향(한 일·교훈)
- `documentation.md` — plan은 `docs/` 산출물의 하나. 단, 트리거·라이프사이클은 본 룰이 규정
