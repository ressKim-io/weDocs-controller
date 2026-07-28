# Workflow Rules

모든 코드 수정·기능 추가·버그 수정에 적용되는 작업 순서. 상시 로드된다 — 짧게 유지할 것.

## 작업 순서 (MANDATORY)

1. **EXPLORE** — 수정할 파일과 관련 파일을 **먼저 읽는다**. 기존 패턴·컨벤션을 파악한다. 읽지 않은 파일은 고치지 않는다.
2. **PLAN** — 변경 파일 목록과 side effect를 정리한다. multi-file이면 Plan Mode. EXPLORE를 건너뛰고 오지 않는다.
3. **IMPLEMENT** — 기존 패턴에 맞춰, 목적 달성에 필요한 **최소 변경**만. 한 번에 10개 파일까지.
4. **VERIFY** — 테스트·lint 실행, `git diff` 전체 리뷰. 통과 전 커밋 금지.
5. **COMMIT** — Conventional Commits. 무엇을·왜 바꿨는지 쓴다.

| 금지 | 이유 |
|---|---|
| multi-file 변경에 EXPLORE/PLAN 생략 | 예상 못 한 side effect |
| 읽지 않은 파일 수정 | 컨벤션 위반 |
| 테스트 통과 전 커밋 | broken commit이 CI를 오염 |
| 한 커밋에 10개 초과 파일 | 리뷰 불가 |

## Blast Radius 선언 (4+ 파일 또는 인프라 변경 시 MANDATORY)

PLAN 단계에서 명시한다: **직접 변경**(파일 목록) · **간접 영향**(동작이 달라질 파일/서비스/경로) ·
**롤백 방법**(git revert, ArgoCD sync) · **검증 방법** · **다운타임**(인프라 한정).

## 검증 없이 쓰지 않는다 (MANDATORY)

처음 쓰는 라이브러리·CLI·차트, 메이저 버전 변경, 그리고 **knowledge cutoff 이후 출시·변경된 모든 것**에
대해 **추측으로 코드를 쓰거나 문서에 값을 적지 않는다.**

- MUST 공식 docs·spec·CHANGELOG·Release Notes를 **WebFetch로 직접** 확인한 뒤 작성. 빈약한 블로그/SO 답변 의존 금지
- MUST 기록에 **출처 URL + 검증일 + 상태 마킹**(✅ verified / ⚠️ unverified)을 남긴다
- NEVER **unverified 값을 근거로 다음 기록을 쌓지 않는다** — 인용 전에 원본의 검증 상태를 확인한다.
  추정이 추정을 정당화하는 순간 전체가 검증 불가능한 모래탑이 된다
- NEVER caveat("확인 필요")로 면피하지 않는다 — caveat는 **검증이 불가능한 영역**의 사후 보강이지,
  5분이면 확인되는 것의 대체가 아니다. 검증 못 했으면 **왜 못 했는지** 1줄 남긴다
- 작성 후 서브에이전트로 cross-check (사용법 정합성)

> 사용자가 "이거 검증된 거야?"라고 묻는 시점은 **마지막 안전망이지 검증 시작 신호가 아니다.**
> 사례·자기점검 시그널 전문 = `deep-thinking.md`(`paths:` 스코프).

## Trouble → 회귀 방지 SOP (MANDATORY)

버그를 고친 뒤 반드시:

1. **dev-log 작성** — 원인/해결/검증 (`docs/dev-logs/YYYY-MM-DD-제목.md`)
2. **패턴 전수 스캔** — 같은 패턴이 다른 곳에도 있다고 가정하고 `rg`로 전수 검색 (`debugging.md`)
3. **rule / skill 보강** — 해당 도메인에 체크리스트 한 줄 승격
4. **회귀 테스트 또는 lint rule** — 자동 검증 가능하면 스크립트화
5. **연관 dev-log 검색** — 같은 stack trace·키워드가 과거에 있었는지

이 순서를 건너뛰면 같은 버그가 다른 모듈에서 재발한다.

---

디버깅 절차 = `debugging.md` · 컨텍스트/토큰 운영 = `token-budget.md` · plan 영구 기록 = `plan-logging.md`.
