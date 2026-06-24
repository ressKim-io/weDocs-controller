---
name: chaos-engineering
description: "Chaos Engineering 가이드 — LitmusChaos를 활용한 시스템 복원력 테스트 및 GameDay 운영 Use when working with sre 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Chaos Engineering 가이드

LitmusChaos를 활용한 시스템 복원력 테스트 및 GameDay 운영

## Quick Reference (결정 트리)

```
Chaos 테스트 도구?
    │
    ├─ Kubernetes 네이티브 ────> LitmusChaos (CNCF, 추천)
    ├─ AWS 환경 ──────────────> AWS Fault Injection Simulator
    ├─ 간단한 테스트 ─────────> chaos-mesh
    └─ 넷플릭스 스타일 ───────> Chaos Monkey

테스트 단계?
    │
    ├─ 1단계: Steady State 정의
    ├─ 2단계: 가설 수립
    ├─ 3단계: 실험 실행
    ├─ 4단계: 결과 분석
    └─ 5단계: 개선 및 반복
```

---

## CRITICAL: Chaos Engineering 원칙

```
┌─────────────────────────────────────────────────────────────┐
│              Chaos Engineering Process                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Steady State 정의                                        │
│     └─ "정상 상태"의 측정 가능한 지표 설정                   │
│                                                              │
│  2. 가설 수립                                                │
│     └─ "X 장애 시에도 Steady State 유지될 것"               │
│                                                              │
│  3. 실험 설계 & 실행                                         │
│     └─ 프로덕션과 유사한 환경에서 제어된 장애 주입           │
│                                                              │
│  4. 결과 분석                                                │
│     └─ 가설 검증, 약점 발견                                  │
│                                                              │
│  5. 개선                                                     │
│     └─ 발견된 약점 수정, 모니터링 개선                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **Steady State 정의** | 시스템 정상 동작의 측정 가능한 지표 |
| **실제 이벤트 가설** | 실제 발생 가능한 장애 시나리오 |
| **프로덕션 실험** | 가능하면 프로덕션 환경에서 |
| **자동화** | 지속적 실험을 위한 자동화 |
| **폭발 반경 최소화** | 영향 범위 제한 |

---

## LitmusChaos 설치

### Helm 설치

```bash
# LitmusChaos 설치
helm repo add litmuschaos https://litmuschaos.github.io/litmus-helm/
helm install litmus litmuschaos/litmus \
  --namespace litmus \
  --create-namespace \
  --set portal.frontend.service.type=LoadBalancer
```

### CRD 구성요소

| CRD | 역할 |
|-----|------|
| **ChaosEngine** | 실험 실행 트리거 |
| **ChaosExperiment** | 실험 정의 (장애 유형) |
| **ChaosResult** | 실험 결과 |
| **ChaosSchedule** | 실험 스케줄링 |

---

## 기본 실험

### Pod Delete 실험

```yaml
# ChaosExperiment 설치
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosExperiment
metadata:
  name: pod-delete
  namespace: litmus
spec:
  definition:
    scope: Namespaced
    permissions:
      - apiGroups: [""]
        resources: ["pods"]
        verbs: ["delete", "get", "list"]
    image: litmuschaos/go-runner:latest
    args:
      - -c
      - ./experiments -name pod-delete
    command:
      - /bin/bash
    env:
      - name: TOTAL_CHAOS_DURATION
        value: "30"
      - name: CHAOS_INTERVAL
        value: "10"
      - name: FORCE
        value: "false"
---
# ChaosEngine으로 실험 실행
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: order-service-chaos
  namespace: production
spec:
  appinfo:
    appns: production
    applabel: "app=order-service"
    appkind: deployment
  engineState: active
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: CHAOS_INTERVAL
              value: "10"
            - name: PODS_AFFECTED_PERC
              value: "50"
        probe:
          - name: "check-order-api"
            type: "httpProbe"
            mode: "Continuous"
            runProperties:
              probeTimeout: 5s
              retry: 3
              interval: 5s
            httpProbe/inputs:
              url: "http://order-service.production.svc:8080/health"
              insecureSkipVerify: false
              method:
                get:
                  criteria: "=="
                  responseCode: "200"
```

### Container Kill 실험

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: container-kill-chaos
  namespace: production
spec:
  appinfo:
    appns: production
    applabel: "app=api-gateway"
    appkind: deployment
  engineState: active
  chaosServiceAccount: litmus-admin
  experiments:
    - name: container-kill
      spec:
        components:
          env:
            - name: TARGET_CONTAINER
              value: "api-gateway"
            - name: TOTAL_CHAOS_DURATION
              value: "30"
            - name: CHAOS_INTERVAL
              value: "10"
```

### Network Chaos (지연/손실)

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: network-chaos
  namespace: production
spec:
  appinfo:
    appns: production
    applabel: "app=payment-service"
    appkind: deployment
  engineState: active
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-network-latency
      spec:
        components:
          env:
            - name: NETWORK_INTERFACE
              value: "eth0"
            - name: NETWORK_LATENCY
              value: "500"  # 500ms 지연
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: CONTAINER_RUNTIME
              value: "containerd"
---
# 네트워크 패킷 손실
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: network-loss-chaos
spec:
  experiments:
    - name: pod-network-loss
      spec:
        components:
          env:
            - name: NETWORK_INTERFACE
              value: "eth0"
            - name: NETWORK_PACKET_LOSS_PERCENTAGE
              value: "30"  # 30% 패킷 손실
            - name: TOTAL_CHAOS_DURATION
              value: "60"
```

### CPU/Memory Stress

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: stress-chaos
  namespace: production
spec:
  appinfo:
    appns: production
    applabel: "app=compute-service"
    appkind: deployment
  engineState: active
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-cpu-hog
      spec:
        components:
          env:
            - name: CPU_CORES
              value: "2"
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: CPU_LOAD
              value: "100"
---
# 메모리 스트레스
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: memory-stress-chaos
spec:
  experiments:
    - name: pod-memory-hog
      spec:
        components:
          env:
            - name: MEMORY_CONSUMPTION
              value: "500"  # 500Mi
            - name: TOTAL_CHAOS_DURATION
              value: "60"
```

---

## Probe (검증)

### HTTP Probe

```yaml
probe:
  - name: "health-check"
    type: "httpProbe"
    mode: "Continuous"
    runProperties:
      probeTimeout: 5s
      retry: 3
      interval: 5s
    httpProbe/inputs:
      url: "http://service.namespace.svc:8080/health"
      method:
        get:
          criteria: "=="
          responseCode: "200"
```

### Prometheus Probe

```yaml
probe:
  - name: "error-rate-check"
    type: "promProbe"
    mode: "Edge"  # 실험 시작/끝에 체크
    runProperties:
      probeTimeout: 5s
      retry: 2
      interval: 10s
    promProbe/inputs:
      endpoint: "http://prometheus:9090"
      query: "sum(rate(http_requests_total{status=~\"5..\"}[1m])) / sum(rate(http_requests_total[1m]))"
      comparator:
        type: "float"
        criteria: "<"
        value: "0.05"  # 에러율 5% 미만
```

### Command Probe

```yaml
probe:
  - name: "db-connection-check"
    type: "cmdProbe"
    mode: "Continuous"
    runProperties:
      probeTimeout: 10s
      retry: 3
      interval: 10s
    cmdProbe/inputs:
      command: "pg_isready -h postgres -p 5432"
      comparator:
        type: "string"
        criteria: "contains"
        value: "accepting connections"
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 프로덕션 첫 실험 | 서비스 장애 | 스테이징부터 시작 |
| Steady State 없음 | 성공/실패 판단 불가 | SLI 기반 지표 정의 |
| 롤백 계획 없음 | 장애 확대 | 롤백 절차 사전 준비 |
| 모니터링 없이 실험 | 영향 파악 불가 | 대시보드 준비 |
| 너무 큰 폭발 반경 | 심각한 장애 | 작은 범위부터 시작 |

---

## 체크리스트

- [ ] LitmusChaos 설치 및 ServiceAccount/RBAC 설정
- [ ] Steady State 지표 정의 (SLI 기반)
- [ ] 롤백 절차 문서화
- [ ] 가설 명확히 정의
- [ ] Probe 설정 (성공/실패 자동 판정)
- [ ] 폭발 반경 제한
- [ ] 스테이징 먼저 테스트

---

## 참조 스킬

- `/chaos-engineering-gameday` - GameDay 운영, 모니터링, 알림
- `/sre-sli-slo` - SLI/SLO 기반 Steady State 정의
- `/load-testing` - 부하 테스트
- `/monitoring-troubleshoot` - 모니터링 트러블슈팅
