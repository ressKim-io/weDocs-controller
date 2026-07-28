# Plan Logging Rules — 재개 가능한 영구 plan 로그 (MANDATORY)

비자명한 작업은 **실행 전에 plan을 repo에 기록하고 커밋**한다. 세션이 유실돼도 다음 세션이
`docs/plans/` 최신 파일만 열면 **재도출 없이** 이어갈 수 있게 하는 것이 목적.
harness plan(`~/.claude/plans/<random>.md`)은 휘발성·랜덤명이라 사실상 미기록 — **repo 파일이 SSOT**다.

## 트리거

Plan Mode를 쓰는 모든 작업 · 4+ 파일 또는 인프라 변경 · 여러 세션에 걸칠 가능성이 있는 작업.
단순 1-2 파일 수정·오타·읽기 작업은 대상 아님.

## 형식

`docs/plans/YYYY-MM-DD-<slug>.md`. frontmatter(`date`/`slug`/`status`/`related`)와
필수 5개 섹션(**Context · 실행 체크리스트 · 검증 · 재개 지점 · 범위 밖**)은
`.claude/templates/plan.md.template` 그대로 — 여기서 중복 규정하지 않는다.

| status | 의미 |
|---|---|
| `planned` | 작성 완료, 실행 전 |
| `in-progress` | 실행 중 |
| `done` | 전 단계 완료 + 결과 dev-log 링크 |
| `abandoned` | 중단/대체 — 사유 + 대체 plan 링크 |

## 라이프사이클 (MANDATORY 순서)

```
1. plan 작성 (status: planned)
2. ★ 작업 시작 전 commit   ← 재개 보장의 핵심. 이 커밋 없이 코드 작업 금지
3. status: in-progress
4. 단계 완료마다: 체크박스 [x] + 재개 지점 갱신 + 커밋
5. 전 단계 완료: status: done + 결과 dev-log 링크 + commit
```

**2번이 빠지면 이 룰은 의미가 없다.** controller는 main 직접 커밋 허용이라 plan 커밋도 직접.

## 재개 정보의 SSOT — 사본을 만들지 않는다 (MANDATORY)

같은 사실을 여러 곳에 복제하고 수작업으로 맞추는 방식은 **두 번 실패했다**(2026-07-17 · 2026-07-28).
사본 수만큼 드리프트 지점이 생기므로, 통제는 "성실히 동기화"가 아니라 **사본 제거**다.

| 파일 | 역할 | 갱신 시점 |
|---|---|---|
| `docs/status/current.md` | **재개 SSOT** — 지금 위치·다음 액션·열린 트랙·이월 findings | 작업 단위 완료마다 |
| `CLAUDE.md` | current.md를 가리키는 **포인터만**(진척 내용 0) | 경로가 바뀔 때만 = 사실상 불변 |
| `docs/plans/<slug>.md` §재개 지점 | 그 **작업 내부**의 상세 재개점 | 그 plan의 단계 완료마다 |
| `docs/status/history.md` | 완료 이력 보관 | 마일스톤/Phase 완료 시 append |

- **CLAUDE.md에 진척 이력·커밋 해시·Phase 상태를 쓰지 않는다** — 공식 가이드가 배제 대상으로 명시한
  "자주 바뀌는 정보"이고, 그 편집 지점이 곧 드리프트 지점이었다.
- plan §재개 지점과 `current.md`는 역할이 다르다(작업 내부 상세 vs 프로젝트 전체 위치) → 중복 아님.
  단 같은 문장을 양쪽에 **복사하지 않는다** — plan은 상세를, current.md는 위치와 링크를.

## 완료 시 역방향 점검 (MANDATORY)

작업을 끝냈으면 **`current.md` §열린 트랙 표를 먼저 훑는다** — "이 항목을 아직 pending으로 든 plan이 있나?"

```bash
for f in docs/plans/*.md; do grep -m1 '^status:' $f; done   # done 아닌 plan의 재개 지점 점검
```

> 이 장치가 없어서 `plan-audit-improvements`의 T4-3가 **한 달간 미체크**로 남았다. 정작 그 항목은
> 이미 완료된 작업과 같은 것이었다. **"완료했다"와 "완료가 기록됐다"는 다르다.**

## 절대 금지

| 금지 | 이유 |
|---|---|
| plan 커밋 없이 코드 작업 시작 | 세션 유실 시 재도출 — 이 룰의 존재 이유 위반 |
| 재개 지점 미갱신 채 다음 단계 진행 | 끊기면 어디까지 했는지 불명 |
| `status` 방치 (planned인데 절반 실행 / 완료인데 in-progress) | 재개 시 상태 오판, 완료 작업 재실행 |
| 하위 트랙 완료로 부모 plan 재개 조건이 바뀌었는데 부모 미갱신 | 부모만 여는 세션이 끝난 트랙을 재실행 |
| CLAUDE.md에 진척 이력·커밋 해시 기재 | 자주 바뀌는 정보 = 공식 배제 대상 |
| 완료 후 `current.md` §열린 트랙 역방향 점검 생략 | 그 항목을 pending으로 든 plan이 방치됨 |

관련: `workflow.md` §PLAN(내용 표준) · `phase-workflow.md`(Phase 게이트) ·
`devlog-lifecycle.md`(plan=전향 / dev-log=후향) · `documentation.md`.
