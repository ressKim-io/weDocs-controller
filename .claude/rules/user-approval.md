# User Approval Rules

외부 시스템에 영향을 주는 작업은 **실행 전에** 내용을 보여주고 승인을 받는다. 예외 없다.

## 사전 승인 필수 (MANDATORY)

| 영역 | 대상 |
|---|---|
| GitHub | `gh pr comment` · `gh pr create/close/merge` · `gh issue create/close` · `gh release create` |
| Git | `git push` · `git branch -D` |
| 외부 서비스 | Slack/Discord 전송 · 외부 상태를 바꾸는 API 호출 · ArgoCD sync 트리거 |
| 클라우드 CLI | 모든 destructive operation(삭제·교체·스케일·권한 변경) |

- **`--force` / `--quiet`를 임의로 덧붙이지 않는다** — 확인 프롬프트 생략·의존성 체크 우회
- 과금이 튀는 작업(GPU/대형 인스턴스·프로비저닝 급증·무효화 과다 호출)은 실행 전 비용 고지
- controller 레포의 `git push`는 예외 — `CLAUDE.md` §커밋·push 규칙에서 사전 승인됨

## 승인 없이 해도 되는 것

파일 읽기(Read/Glob/Grep) · 로컬 파일 쓰기·수정 · 로컬 빌드/테스트/린트 ·
읽기 전용 git(`status`/`diff`/`log`) · 읽기 전용 `gh`(`pr view`/`issue view`).

## 포괄 위임 하에서도 건별 승인 (ABSOLUTE)

사용자가 "알아서 해", "맘껏 해", "빨리 진행해", "바로 해줘" 같은 **포괄적 위임**을 했더라도,
위 사전 승인 필수 작업은 **건별로 개별 승인**을 받는다.

- 포괄 위임 = 일반 작업(코드 수정 / 커밋 메시지 초안 / 분석 / 로컬 명령)에 대한 위임이지 **외부 상태 변경 위임이 아니다**
- 세션 내 여러 번 필요해도 **매번** 확인. "이전에 승인했으니 이번에도 OK" 가정 금지 — 승인은 특정 scope 한정
- 승인 없는 외부 영향 작업은, **사용자가 짜증을 내더라도** 다시 텍스트로 확인을 요청한다

이 규칙은 사용자의 의도(=신중한 변경)를 시간이 흐른 뒤의 발언("그냥 해줘")보다 우선시한다.

## 자동 실행 금지 (MANDATORY)

"자동으로 실행합니다" / "지금 바로 진행하겠습니다" 류의 announcement는 **승인 요청의 일부이지 승인이 아니다.**
"응"/"OK"/"진행해" 같은 명시적 답변을 받을 때까지 대기한다. 응답이 없으면 추측으로 진행하지 않는다.

## 리뷰 결과 게시 (MANDATORY)

`리뷰 실행 → 결과를 사용자에게 텍스트로 먼저 표시 → 확인·수정 → 승인 후 게시`.
**리뷰 결과를 사용자 확인 없이 PR 코멘트로 올리지 않는다.**
서브에이전트에는 **결과만 반환하도록** 지시한다 — 에이전트가 직접 `gh pr comment`/`gh issue create`를 실행하게 하지 않는다.

## kubectl · ArgoCD (MANDATORY)

- ⛔ **kubectl로 K8s 리소스를 직접 바꾸지 않는다.** `get`/`describe`/`logs`/`top`/`port-forward`/읽기용 `exec`만.
  `apply`·`delete`·`patch`·`edit`·`set image`·`scale`·`rollout`·변경 목적 `annotate`/`label` 금지.
  **왜**: ArgoCD OutOfSync로 drift 추적 불가 + 새 ReplicaSet 생성으로 의도치 않은 rollout(실제 사고 2026-03-22).
  올바른 경로 = 소스(values/chart/manifest) 수정 → commit/push → ArgoCD sync.
  사용자가 "kubectl로 고쳐줘"라고 해도 **소스 수정 경로를 제안**한다. 긴급 장애 시에만 예외, 즉시 소스 반영.
- ⛔ **`ServerSideApply=true` 앱에 Force Sync 금지** — `--force`와 `--server-side`는 동시 사용 불가.
  ExternalSecret(syncWave -1) 실패 시 후속 wave 전체가 skip되고 retry 소진 후 stuck된다(실제 사고 2026-03-28).
  모든 goti ApplicationSet 앱이 `ServerSideApply=true`라 전체 해당.

> 위 두 금지는 `.claude/settings.json`의 `permissions.deny` + `scripts/guard_destructive.py`가 결정론적으로 강제한다
> (deny는 접두사 매칭이라 플래그가 뒤로 가는 경우를 못 잡아 훅과 나눴다).
