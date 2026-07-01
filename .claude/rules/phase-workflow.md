---
paths:
  - "**/sdd-*.md"
  - "**/phase-start*"
  - "**/phase-workflow*"
---

# Phase Workflow Gate Rules

Phase 기반 작업 시 반드시 따라야 할 게이트 규칙.
**이 규칙은 `/phase-start` 커맨드로 Phase를 시작한 경우에만 적용된다.**
각 게이트를 통과하지 않으면 다음 단계로 넘어가지 않는다.

---

## 적용 대상

다음 조건 중 하나 이상에 해당하면 `/phase-start`로 Phase를 시작해야 한다:

- 새 서비스/모듈 구현 (6개 이상 파일 변경 예상)
- 기존 서비스 대규모 변경 (API 추가/변경 3개 이상)
- 시스템 마이그레이션 (언어 전환, 아키텍처 변경)

## 적용 대상 아님

- 버그 수정, 문서 수정, 설정 변경 등 소규모 작업 → `rules/workflow.md`의 일반 작업 순서
- SDD/마이그레이션 문서의 오타 수정, 참조 링크 추가

## spec-driven-development.md와의 관계

이 규칙은 `skills/dx/spec-driven-development.md`의 Spec-Driven 워크플로우(Research→Specify→Plan→Execute→Review)를 **프로젝트 운영 Gate로 강제화**한 것이다.

| spec-driven-development.md (지식) | 이 규칙 (강제) |
|---|---|
| Phase 2: SPEC.md 작성 | Gate 1: SDD 작성 |
| Phase 3: Plan Mode | Gate 2: SDD 리뷰 |
| Phase 4: Execute | Gate 3-4: 코드 리뷰 + 테스트 |
| Phase 5: Phase Gate | Gate 5: PR 리뷰 |

**용어**: 이 규칙에서는 "SDD(Software Design Document)"로 통일한다. spec-driven-development.md의 "SPEC.md"와 동일한 개념이다.

---

## Gate 1: SDD 작성 (MANDATORY)

- SDD(Software Design Document)를 먼저 작성한다
- 템플릿: `.claude/templates/sdd.md.template` (범용) 또는 도메인 특화 템플릿
- SDD에 "구현 순서" 섹션이 명확해야 한다 (Step별 의존성 포함)
- SDD에 "테스트 전략" 섹션이 있어야 한다

**금지**: SDD 없이 구현 코드 작성

---

## Gate 2: SDD 리뷰 (MANDATORY)

- SDD 작성 후 code-reviewer 에이전트로 리뷰를 실행한다
- 리뷰 관점: API 명세 일관성, 데이터 모델 정합성, 구현 순서 의존성, 누락 항목
- 리뷰 피드백을 SDD에 반영한 후 구현 단계로 진입한다

**금지**: 리뷰 피드백 미반영 상태에서 구현 시작

---

## Gate 3: 코드 리뷰 (MANDATORY)

- SDD 기반으로 구현 완료 후 코드 리뷰를 받는다
- 사용 커맨드: 기술 스택에 맞는 리뷰 (`/go:review`, `/java:review`, `/backend:review` 등)
- 리뷰 피드백을 반영한다
- 표준 체크리스트(예: `error-handling.md`)의 **[B] 위반 = 반려** — 수정 후 재리뷰. 새로 잡힌 갭은 해당 표준 체크리스트에 항목으로 승격한다(gap→standard loop 폐쇄)

**금지**: 코드 리뷰 없이 PR 생성

---

## Gate 4: 테스트 통과 (MANDATORY)

- SDD의 "테스트 전략"에 정의된 테스트를 작성한다
- 단위 테스트 + 통합 테스트 모두 통과해야 한다
- 테스트 검증 명령어를 실행하고 결과를 확인한다

**금지**: 테스트 미통과 상태에서 PR 생성

---

## Gate 5: PR 리뷰 (MANDATORY)

- PR 생성 직후 `/review-pr`을 자동 실행한다
- Gemini 리뷰 결과와 비교하여 리뷰 갭을 `docs/review-gaps.md`에 기록한다
- 양쪽 피드백을 반영한 후 머지한다

**금지**: `/review-pr` 미실행 상태에서 머지

---

## Phase 체크리스트

Phase 시작 시 아래 체크리스트를 출력하고 진행 상황을 추적한다.
(`/phase-start` 커맨드로 자동 출력)

```
[ ] SDD 작성 완료
[ ] SDD 리뷰 완료 (피드백 반영)
[ ] SDD 기반 코드 구현 (Step별 순차)
[ ] 코드/보안 리뷰 실행 + 피드백 반영
[ ] 테스트 코드 작성 + 전체 통과
[ ] PR 생성
[ ] /review-pr 멀티 관점 리뷰
[ ] Gemini 리뷰 확인 + 갭 기록
[ ] 피드백 반영 → push → merge
[ ] main pull
[ ] 트러블슈팅 로그 (/log-trouble) — 문제 발생 시
```

---

## 트러블슈팅 연계

Phase 진행 중 문제 발생 시:
1. `rules/debugging.md`의 가설-검증 루프를 따른다
2. 해결 후 `/log-trouble`로 기록한다 (failure_type 태그 포함)
3. SDD에 영향이 있으면 SDD를 업데이트한다

---

## 관련 파일

- 범용 SDD 템플릿: `.claude/templates/sdd.md.template`
- 일반 작업 순서: `.claude/rules/workflow.md`
- 디버깅 프로토콜: `.claude/rules/debugging.md`
- PR 리뷰 프로세스: `.claude/rules/code-review.md`
- Phase 시작 커맨드: `/phase-start`
