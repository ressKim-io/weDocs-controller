---
name: deployment-strategies
description: "배포 전략 가이드 — Rolling Update, Blue-Green 배포 및 기본 전략 개요 Use when working with cicd 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# 배포 전략 가이드

Rolling Update, Blue-Green 배포 및 기본 전략 개요

## Quick Reference (결정 트리)

```
배포 전략 선택?
    │
    ├─ 빠른 롤백 필요 ───────────> Blue-Green
    │
    ├─ 점진적 검증 필요 ─────────> Canary
    │
    ├─ 리소스 효율 중시 ─────────> Rolling Update
    │
    └─ 사용자 세그먼트 테스트 ───> A/B Testing

도구 선택?
    │
    ├─ 기본 K8s ────────> Rolling Update (Deployment)
    ├─ 고급 트래픽 제어 ─> Argo Rollouts + Istio
    └─ 서비스 메시 있음 ─> Istio VirtualService
```

---

## CRITICAL: 전략 비교

| 전략 | 다운타임 | 롤백 속도 | 리소스 | 복잡도 |
|------|----------|----------|--------|--------|
| **Rolling Update** | 없음 | 느림 | 1x | 낮음 |
| **Blue-Green** | 없음 | 즉시 | 2x | 중간 |
| **Canary** | 없음 | 빠름 | 1.x | 높음 |
| **A/B Testing** | 없음 | 빠름 | 1.x | 높음 |

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Strategies                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Rolling Update: [v1][v1][v2][v2] → [v2][v2][v2][v2]        │
│                                                              │
│  Blue-Green:     [v1 100%] ─switch─> [v2 100%]              │
│                                                              │
│  Canary:         [v1 90%] → [v1 70%] → ... → [v2 100%]     │
│                  [v2 10%] → [v2 30%] → ...                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Rolling Update (기본)

### Deployment 설정

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%        # 추가 Pod 허용량
      maxUnavailable: 25%  # 동시 중단 허용량
  template:
    spec:
      containers:
        - name: my-app
          image: myapp:v2
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 10
```

### 권장 설정

| 시나리오 | maxSurge | maxUnavailable |
|----------|----------|----------------|
| 안전 우선 | 1 | 0 |
| 빠른 배포 | 50% | 50% |
| 균형 | 25% | 25% |

### 롤백

```bash
# 이전 버전으로 롤백
kubectl rollout undo deployment/my-app

# 특정 리비전으로 롤백
kubectl rollout undo deployment/my-app --to-revision=2

# 롤아웃 상태 확인
kubectl rollout status deployment/my-app

# 히스토리 확인
kubectl rollout history deployment/my-app
```

---

## Blue-Green 배포

### 수동 Blue-Green

```yaml
# blue-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-blue
  labels:
    app: my-app
    version: blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
      version: blue
  template:
    metadata:
      labels:
        app: my-app
        version: blue
    spec:
      containers:
        - name: my-app
          image: myapp:v1
---
# green-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-green
  labels:
    app: my-app
    version: green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
      version: green
  template:
    metadata:
      labels:
        app: my-app
        version: green
    spec:
      containers:
        - name: my-app
          image: myapp:v2
---
# service.yaml - selector 변경으로 전환
apiVersion: v1
kind: Service
metadata:
  name: my-app
spec:
  selector:
    app: my-app
    version: blue  # → green으로 변경하여 전환
  ports:
    - port: 80
      targetPort: 8080
```

### Argo Rollouts Blue-Green

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: my-app
          image: myapp:v2
  strategy:
    blueGreen:
      activeService: my-app-active
      previewService: my-app-preview
      autoPromotionEnabled: false  # 수동 승인
      scaleDownDelaySeconds: 30
      prePromotionAnalysis:
        templates:
          - templateName: success-rate
        args:
          - name: service-name
            value: my-app-preview
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-active
spec:
  selector:
    app: my-app
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-preview
spec:
  selector:
    app: my-app
  ports:
    - port: 80
```

---

## Argo Rollouts 설치 & CLI

### 설치

```bash
# Controller 설치
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# kubectl 플러그인 설치
brew install argoproj/tap/kubectl-argo-rollouts

# 대시보드 (선택)
kubectl argo rollouts dashboard
```

### CLI 명령어

```bash
# 롤아웃 상태 확인
kubectl argo rollouts get rollout my-app --watch

# 수동 Promote
kubectl argo rollouts promote my-app

# Abort (롤백)
kubectl argo rollouts abort my-app

# 이미지 변경으로 롤아웃 트리거
kubectl argo rollouts set image my-app myapp=myapp:v3

# 일시 정지/재개
kubectl argo rollouts pause my-app
kubectl argo rollouts resume my-app
```

---

## 모니터링

### Prometheus 메트릭

```promql
# Rollout 상태
argo_rollouts_info{name="my-app"}

# 현재 Phase
argo_rollouts_info{name="my-app",phase="Progressing"}

# 레플리카 상태
argo_rollouts_replicas{name="my-app"}
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| Readiness Probe 없음 | 불완전한 Pod에 트래픽 | Probe 필수 설정 |
| Blue-Green 리소스 방치 | 비용 낭비 | scaleDownDelay 설정 |
| 롤백 계획 없음 | 장애 시 혼란 | 자동 롤백 조건 설정 |

---

## 체크리스트

### 기본 설정
- [ ] Readiness/Liveness Probe 설정
- [ ] 리소스 requests/limits 설정
- [ ] PodDisruptionBudget 설정

### Blue-Green
- [ ] Active/Preview Service 생성
- [ ] prePromotionAnalysis 설정
- [ ] scaleDownDelay 설정

### 모니터링
- [ ] 배포 메트릭 수집
- [ ] 알림 설정
- [ ] 대시보드 구성

**관련 skill**: `/deployment-canary` (Canary/A/B Testing), `/gitops-argocd`, `/istio-traffic`, `/sre-sli-slo`
