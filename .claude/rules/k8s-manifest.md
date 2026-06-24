---
paths:
  - "**/*application*"
  - "**/*appproject*"
  - "**/*networkpolicy*"
  - "**/*clusterrole*"
  - "**/*role*"
  - "**/*rolebinding*"
---

# K8s Manifest Rules

K8s 매니페스트(ArgoCD Application/AppProject, NetworkPolicy, RBAC) 작성/수정 시 반드시 준수.
실전 PR 리뷰 갭 + 보안 외부 검증에서 추출.

---

## ArgoCD

### AppProject
- NEVER `clusterResourceWhitelist`에 `kind: "*"` 와일드카드 사용
  - 모든 cluster-scoped 리소스(ClusterRole, Namespace, CRD 등) 배포 허용 → least privilege 위반
  - MUST 명시적 resource kind 목록 작성

### Application targetRevision
- Production: MUST Git tag (`refs/tags/v*`) 또는 commit SHA 사용
  - `targetRevision: main` → 미검증 변경이 자동 배포되는 위험
- Dev/Staging: branch tracking 허용 (`main`, `develop`)

---

## NetworkPolicy

### IMDS 차단 (보안 필수)
- MUST EKS/클라우드 환경에서 IMDS 접근 차단:
  ```yaml
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 169.254.169.254/32  # IMDS
  ```
- 미차단 시: 컨테이너에서 `curl 169.254.169.254`로 Node IAM Role 자격증명 탈취 가능

### Broad Egress
- `0.0.0.0/0` egress 사용 시 WARNING — 정당성 문서화 필수
- PREFER 특정 CIDR + `ipBlock.except`로 범위 제한
- 추가 차단 권장: kubelet API (`<Node IP>:10250`), 외부 DNS (CoreDNS만 허용)

---

## RBAC

### 비호환 조합
- `create` verb + `resourceNames` = 무효 — K8s API가 create 요청 URL에 resource name 없음 → `resourceNames` 무시됨
  - `list`, `watch`, `deletecollection`도 동일
  - 대안: Kyverno/OPA admission controller로 세분화

### 위험 Verb (보안 CRITICAL)
아래 verb 사용 시 반드시 정당성 명시:

| Verb/Resource | 위험도 | 이유 |
|---|---|---|
| `escalate` | CRITICAL | 자신보다 높은 권한의 Role 생성 가능 |
| `bind` | CRITICAL | 고권한 Role을 자신에게 바인딩 가능 |
| `impersonate` | CRITICAL | 임의 사용자/SA로 행동 가능 |
| `nodes/proxy` GET | CRITICAL | Pod에 직접 명령 실행, audit 로그 우회 |
| `verbs: ["*"]` | CRITICAL | 현재 + 미래 모든 verb 허용 |
| `resources: ["*"]` | CRITICAL | 현재 + 미래 모든 리소스 접근 |
| `list`/`watch` on Secrets | HIGH | 네임스페이스 내 전체 시크릿 내용 노출 |
| PersistentVolume 생성 | HIGH | `hostPath`로 호스트 파일시스템 접근 |
| 워크로드 생성 (pods, deployments) | HIGH | 네임스페이스 secrets/configmaps 암묵적 접근 |

### ServiceAccount
- PREFER `automountServiceAccountToken: false` 기본 설정
- API 접근이 필요한 Pod만 명시적으로 `true` 설정

---

## Alert Rules

### Kafka Consumer Lag
- MUST `sum by (topic, consumergroup)` 집계 사용
  - partition 단위 alert → alert storm 발생 위험
  - 근거: review-gap #21

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| AppProject `kind: "*"` | Least privilege 위반 |
| Production `targetRevision: main` | 미검증 자동 배포 |
| IMDS egress 미차단 | IAM 자격증명 탈취 |
| `escalate`/`bind`/`impersonate` 정당성 없이 사용 | 권한 상승 공격 |
| `create` + `resourceNames` 조합 | K8s가 무시 → 의도와 다른 동작 |
