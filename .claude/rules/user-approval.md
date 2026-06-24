# User Approval Rules

외부 시스템에 영향을 주는 모든 작업은 반드시 사용자 승인을 받은 후 실행한다.
이 규칙은 예외 없이 적용된다.

---

## 사전 승인 필수 작업 (MANDATORY)

아래 작업은 **실행 전 반드시 사용자에게 내용을 보여주고 승인을 받는다**.

### GitHub 작업
- `gh pr comment` — PR 코멘트 게시
- `gh pr create` — PR 생성
- `gh pr close/merge` — PR 닫기/머지
- `gh issue create` — 이슈 생성
- `gh issue close` — 이슈 닫기
- `gh release create` — 릴리스 생성

### Git 작업
- `git push` — 원격 레포에 푸시
- `git branch -D` — 브랜치 삭제

### 외부 서비스
- Slack/Discord 메시지 전송
- API 호출로 외부 상태 변경
- ArgoCD sync 트리거

---

## 리뷰 결과 게시 프로세스 (MANDATORY)

코드 리뷰 실행 후 반드시 다음 순서를 따른다:

```
1. 리뷰 실행 (에이전트 또는 직접)
2. 리뷰 결과를 사용자에게 텍스트로 먼저 표시
3. 사용자가 내용 확인 및 수정 요청
4. 사용자 승인 후 gh pr comment로 게시
```

**절대 금지**: 리뷰 결과를 사용자에게 보여주지 않고 바로 PR 코멘트로 게시

---

## 에이전트 실행 규칙

서브 에이전트에게 작업을 위임할 때:

- **결과만 반환하도록 지시** — 에이전트가 직접 `gh pr comment`, `gh issue create` 등 실행 금지
- 에이전트 프롬프트에 "PR 코멘트로 게시하라" 등의 지시를 포함하지 않는다
- 에이전트가 반환한 결과를 사용자에게 보여준 후, 승인 시 메인 에이전트가 게시한다

---

## 포괄 위임 하에서도 건별 승인 필수 (ABSOLUTE)

사용자가 "알아서 해", "맘껏 해", "빨리 진행해", "바로 해줘" 같은 **포괄적 위임**을 했더라도, 이 파일과 `cloud-cli-safety.md`의 사전 승인 필수 작업은 **건별로 개별 승인**을 받는다.

- 포괄 위임 = 일반 작업(코드 수정 / 커밋 메시지 초안 / 분석 / 로컬 명령 등)에 대한 위임이지, **외부 상태 변경 위임이 아님**
- 세션 내 여러 번의 변경이 필요해도 **매번** 승인 확인
- "이전에 승인했으니 이번에도 OK" 가정 금지 — 승인은 특정 scope 한정
- 승인 받지 않은 외부 영향 작업은, 사용자가 짜증을 내더라도 다시 텍스트로 확인을 요청한다

이 규칙은 사용자의 의도(=신중한 변경)를 시간이 흐른 뒤의 발언("그냥 해줘")보다 우선시한다.

---

## 자동 실행 금지 (MANDATORY)

"자동으로 실행합니다" / "지금 바로 진행하겠습니다" 류의 announcement 후 사용자 확인 없이 외부 작업을 수행하지 않는다.

- announcement는 **승인 요청의 일부**이지 승인 그 자체가 아니다
- 사용자가 명시적으로 "응", "OK", "진행해" 같은 답변을 줄 때까지 대기
- 사용자 응답 부재 시 대기 — 추측으로 진행 금지

---

## 자동 실행 허용 범위

아래 작업은 사전 승인 없이 실행할 수 있다:

- 파일 읽기 (Read, Glob, Grep)
- 로컬 파일 쓰기/수정 (Write, Edit)
- 로컬 빌드/테스트/린트 실행
- `git status`, `git diff`, `git log` 등 읽기 전용 git 명령
- `gh pr view`, `gh issue view` 등 읽기 전용 GitHub 명령

---

## kubectl 변경 금지 (MANDATORY)

**kubectl로 K8s 리소스를 직접 수정하지 않는다.** 읽기 전용으로만 사용한다.

### 허용 (읽기 전용)
- `kubectl get`, `kubectl describe`, `kubectl logs`, `kubectl top`
- `kubectl port-forward` (디버깅용)
- `kubectl exec` (디버깅용, 상태 변경 없는 명령만)

### 금지 (상태 변경)
- `kubectl edit`, `kubectl patch`, `kubectl apply`, `kubectl delete`
- `kubectl set image`, `kubectl scale`, `kubectl rollout`
- `kubectl annotate`, `kubectl label` (변경 목적)
- `kubectl run` (디버깅용 임시 pod 제외)

### 올바른 변경 경로
```
소스 코드 수정 (Helm values, chart, manifest)
  → git commit/push
  → ArgoCD sync
```

kubectl로 직접 수정하면:
- ArgoCD OutOfSync 발생 → drift 추적 불가
- 새 ReplicaSet이 생성되어 의도치 않은 rollout 발생
- ECR credential 만료 타이밍에 ImagePullBackOff 유발 (실제 사고 발생: 2026-03-22)

사용자가 "kubectl로 수정해줘"라고 요청해도 **소스 코드 수정 경로를 제안**한다.
긴급 장애 대응으로 불가피한 경우에만 예외를 허용하되, 즉시 소스에 반영한다.

---

## ArgoCD Force Sync 금지 (MANDATORY)

**ServerSideApply=true 사용 Application에서 Force Sync를 절대 사용하지 않는다.**

### 금지
- ArgoCD UI/CLI에서 Force Sync 체크박스 활성화
- `argocd app sync --force`
- `kubectl patch application` 시 `syncStrategy.apply.force: true` 설정

### 이유
- `--force`와 `--server-side`는 kubectl에서 동시 사용 불가
- ExternalSecret(syncWave -1) 실패 → **후속 wave의 Deployment 등 전체 리소스 sync skip**
- retry 소진 후 stuck → selfHeal도 동일 에러 반복 → 수동 operation 제거 필요
- 실제 사고 발생: 2026-03-28 (goti-queue-sungjeon-dev, env 변경 미반영으로 CrashLoopBackOff 지속)

### 복구 방법 (stuck 발생 시)
```
1. Application JSON export → operation/operationState에서 force 플래그 제거
2. kubectl replace -f <fixed-json>
3. force 없는 깨끗한 sync operation 트리거
```

### 현재 해당 앱
모든 goti ApplicationSet 앱이 `ServerSideApply=true`를 사용하므로, **전체 goti 앱에 해당**한다.

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| 리뷰 결과를 사용자 확인 없이 PR에 자동 게시 | 품질 검증 기회 박탈 |
| 에이전트에 외부 게시 권한 위임 | 사용자 제어권 상실 |
| "자동으로 실행합니다" 후 바로 실행 | 승인 = 사용자의 명시적 동의 |
| 사용자가 "해줘"라고 한 것 이상의 외부 작업 수행 | 의도 범위 초과 |
| kubectl로 K8s 리소스 직접 수정 | GitOps drift 유발, 장애 원인 |
| ServerSideApply=true 앱에 Force Sync | --force + --server-side 비호환, 전체 sync stuck |
