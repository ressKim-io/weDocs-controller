---
date: 2026-07-28
category: meta
tier: 2
importance: critical
status: resolved
tags: [claude-md, context-budget, drift, documentation, ssot]
related:
  - dev-logs/2026-07-28-build-test-ci-gap.md
  - plans/2026-06-30-plan-audit-improvements.md
---

# CLAUDE.md의 80%가 진척 이력이었다 — 드리프트의 구조적 원인

## 계기

`/clear` 직전 문서 정합성 점검에서 **전향 문서 5건이 지금도 틀린 사실을 가리키고** 있었다. 가장 심한 `plan-audit-improvements`는 `status: planned`인데 체크박스가 21/26 완료였고, §재개 지점이 **이미 무효한 blocker를 "유효"라고 단언**하고 있었다(`build_client(false)` — 2b가 `true`로 flip해 끝난 얘기).

같은 종류의 사고가 **2026-07-17에 이미 한 번** 있었고, 그때 `plan-logging.md`에 "한쪽을 바꾸면 같은 커밋에서 다른 쪽도 갱신" 룰을 넣었다. **그 룰이 있는 상태에서 또 났다.** 두 번 실패한 통제는 통제가 아니다 — 그래서 룰을 강화하는 대신 구조를 봤다.

## 측정

| 구간 | 크기 | 비중 |
|---|---|---|
| 규칙·가드레일·명령 (안정) | ~700 토큰 | 7.6% |
| **진척 이력·재개 (휘발성)** | **~7,394 토큰** | **80%** |
| 표준·에이전트·커밋룰 | ~1,108 토큰 | 12% |

CLAUDE.md = 98줄 / 27,602자 / **~9,200 토큰**. 매 세션 자동 로드 합계(CLAUDE.md + 항상적용 rules 7종) = **~20,700 토큰**.
최장 줄 = **3,112자 한 줄**(재개 SSOT 블록).

## 공식 가이드와 대조

| 공식 기준 | 우리 상태 |
|---|---|
| "target under 200 lines" | 98줄 — **줄 수는 통과** |
| "❌ Exclude: **information that changes frequently**" | **80%가 진척 이력** ← 정면 위반 |
| "organized sections are easier to follow than **dense paragraphs**" | 3,112자 단일 줄 |
| "Bloated CLAUDE.md files cause Claude to **ignore your actual instructions**" | 해당 |
| "@path imports는 **컨텍스트를 줄이지 않는다**(launch에 전부 로드)" | rules 7종 = ~11.5K 토큰 상시 |

줄 수 기준만 보면 합격이라 문제를 못 봤다. **실제 제약은 토큰과 밀도**다.

출처: [best-practices](https://code.claude.com/docs/en/best-practices) · [memory](https://code.claude.com/docs/en/memory)

## 근본 원인 4가지

**RC1 — CLAUDE.md가 지시서가 아니라 진척 원장이 됐다.** Phase가 끝날 때마다 CLAUDE.md를 고쳐야 하니 "완료 = CLAUDE.md 갱신"이 습관이 됐다. 드리프트는 항상 그 습관의 **바깥**(plan 파일)에서 생겼다.

**RC2 — 같은 사실이 4곳에 복제되고 동기화가 수작업이었다.** CLAUDE.md 현재상태 불릿 + CLAUDE.md 재개 SSOT + plan §재개 지점 + 부모 plan §재개 지점. 사본 수만큼 드리프트 지점이 생긴다. "성실히 동기화하라"는 룰로는 못 막는다 — 두 번 증명됐다.

**RC3 — "무엇이 나를 pending으로 주장하는가"를 물을 방법이 없었다.** `plan-audit-improvements`의 T4-3(서비스 레포 CI)은 2026-07-28에 완료한 작업과 **같은 항목**인데 미체크로 남아 있었다. 한 달간 아무도 그 파일을 열지 않았다. 완료 시점에 역방향으로 훑는 장치가 없었다.

**RC4 — 밀도가 스캔을 무력화했다.** 3,112자 한 줄은 읽을 때 편집 중인 구간만 패턴매칭하게 만든다. 재읽기가 검증이 되지 못한다.

## 조치

### 1. 휘발성 80%를 CLAUDE.md 밖으로

```
docs/status/current.md   ← 재개 SSOT (지금 위치·다음 액션·열린 트랙·이월 findings)
docs/status/history.md   ← 완료 이력 (세션 시작에 불필요)
CLAUDE.md                ← 포인터 한 블록, 진척 내용 0
```

| | before | after |
|---|---|---|
| CLAUDE.md | 27,602자 / ~9,200 토큰 | **6,189자 / ~2,063 토큰** (-78%) |
| 최장 줄 | 3,112자 | **541자** |

매 세션 **~7,140 토큰** 절약. 더 중요한 건 **편집 빈도가 0에 수렴**한다는 것 — 포인터 경로가 바뀔 때만 손댄다.

### 2. 사본 제거 (RC2)

`plan-logging.md`의 "양방향 수작업 동기화" 룰을 **단일 SSOT 계약**으로 교체. CLAUDE.md는 동기화 대상에서 아예 빠진다(내용이 없으므로). plan §재개 지점과 `current.md`는 **역할이 달라**(작업 내부 상세 vs 프로젝트 전체 위치) 중복이 아니다.

### 3. 역방향 점검 장치 (RC3)

`current.md`에 **§열린 트랙 표** 신설 — `done`이 아닌 모든 plan과 각각의 실제 남은 항목. 작업 완료 시 **이 표부터 훑는 것**을 `plan-logging.md` MANDATORY로 배선했다.

## 교훈

- **"줄 수 200 이하"만 보면 놓친다.** 실제 제약은 토큰·밀도·**편집 빈도**다. 한 줄이 3,000자면 줄 수는 무의미하다.
- **자주 바뀌는 정보를 상시 로드 파일에 두면, 그 파일이 드리프트 공장이 된다.** 공식 가이드의 "exclude information that changes frequently"는 컨텍스트 절약 조언으로 읽히지만 **정확성 조언이기도 하다**.
- **같은 사고가 두 번 나면 룰을 강화하지 말고 구조를 바꾼다.** 2026-07-17에 넣은 동기화 룰은 성실성에 의존했고, 성실성은 사본 수에 반비례한다.
- **"완료했다" ≠ "완료가 기록됐다."** 완료 시점의 역방향 점검이 없으면 아무도 안 여는 파일에서 조용히 썩는다.

## 남은 것

- 항상적용 rules 7종(~11.5K 토큰)의 path-scoping 검토 — `testing.md`·`debugging.md`는 `paths:` 스코프 후보. 단 진짜 횡단 룰을 스코프하면 오히려 누락되므로 신중히.
- `/doctor` 트림 체크(v2.1.206+)를 주기적으로 돌려 재비대 감시.
