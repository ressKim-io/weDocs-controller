---
name: ebpf-observability
description: "eBPF Observability 가이드 — Zero-code 분산 추적: Grafana Beyla, Odigos, Cilium Hubble 활용 Use when working with observability 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# eBPF Observability 가이드

Zero-code 분산 추적: Grafana Beyla, Odigos, Cilium Hubble 활용

## Quick Reference (결정 트리)

```
eBPF Observability 도구 선택?
    |
    +-- 자동 HTTP/gRPC 추적 ---------> Grafana Beyla
    |       |
    |       +-- 단일 앱 모니터링 -----> Beyla Sidecar
    |       +-- 클러스터 전체 --------> Beyla DaemonSet
    |
    +-- 멀티 언어 자동 계측 ---------> Odigos
    |       |
    |       +-- OpenTelemetry 백엔드 -> Odigos + OTel Collector
    |       +-- 엔터프라이즈 ---------> Odigos Enterprise
    |
    +-- 네트워크 가시성 -------------> Cilium Hubble
    |       |
    |       +-- Service Map ---------> Hubble UI
    |       +-- 네트워크 정책 디버깅 -> Hubble CLI
    |
    +-- 종합 플랫폼 -----------------> DeepFlow
            |
            +-- 분산 추적 + APM -----> DeepFlow Community
```

---

## CRITICAL: eBPF vs 기존 Agent 비교

| 항목 | 기존 Agent | eBPF 기반 |
|------|-----------|----------|
| **코드 변경** | SDK 추가 필요 | Zero-code |
| **시작 시간** | Agent 초기화 대기 | 즉시 |
| **리소스 오버헤드** | 높음 (~100MB/Pod) | 낮음 (Node 레벨) |
| **언어 지원** | 언어별 SDK | 모든 언어 자동 |
| **커널 접근** | 불가 | 시스템 콜 추적 |
| **컨테이너 호환** | 복잡한 설정 | 자동 감지 |
| **성숙도** | 검증됨 | 발전 중 (2024~) |

### eBPF 장점

```
커널 레벨 모니터링
    |
    +-- 100배 빠른 시작 (ms 단위)
    +-- 애플리케이션 변경 없음
    +-- 모든 언어/프레임워크 지원
    +-- 네트워크 + 시스템 콜 추적
    +-- 낮은 오버헤드 (1-3%)
```

---

## eBPF 기초 개념

### eBPF 아키텍처

```
User Space                         Kernel Space
+------------------+              +----------------------+
|                  |              |                      |
| BPF Program      |   load       | eBPF Virtual Machine |
| (C, Rust, Go)    | --------->   |                      |
|                  |              | +------------------+ |
+------------------+              | | Verifier         | |
                                  | | (안전성 검증)    | |
+------------------+              | +------------------+ |
|                  |              |         |           |
| BPF Maps         | <----------> | +------------------+ |
| (데이터 저장)    |   read/write | | JIT Compiler     | |
|                  |              | | (네이티브 코드)  | |
+------------------+              | +------------------+ |
                                  |         |           |
                                  | +------------------+ |
                                  | | Hook Points      | |
                                  | | (kprobe, uprobe, | |
                                  | |  tracepoint)     | |
                                  | +------------------+ |
                                  +----------------------+
```

### 주요 Hook 포인트

```yaml
# eBPF Hook 포인트 종류
kprobe:
  - 커널 함수 진입/종료 추적
  - 예: tcp_connect, tcp_accept

uprobe:
  - 사용자 공간 함수 추적
  - 예: HTTP 핸들러, DB 쿼리

tracepoint:
  - 커널 정적 추적점
  - 예: syscalls, scheduler

XDP (eXpress Data Path):
  - 패킷 레벨 처리 (NIC 드라이버)
  - 예: DDoS 방어, 로드밸런싱

tc (Traffic Control):
  - 네트워크 트래픽 제어
  - 예: QoS, 패킷 필터링
```

---

## Grafana Beyla

### 개요

Grafana Beyla는 eBPF 기반 자동 계측 도구로, 애플리케이션 코드 변경 없이 HTTP/gRPC 트레이싱과 메트릭을 수집합니다.

### 지원 프로토콜

- HTTP/1.x, HTTP/2
- gRPC
- SQL (MySQL, PostgreSQL)
- Redis
- Kafka

### DaemonSet 배포 (클러스터 전체)

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: beyla
  namespace: observability
spec:
  selector:
    matchLabels:
      app: beyla
  template:
    metadata:
      labels:
        app: beyla
    spec:
      serviceAccountName: beyla
      hostPID: true  # eBPF를 위한 필수 설정
      containers:
        - name: beyla
          image: grafana/beyla:1.8
          securityContext:
            privileged: true  # eBPF 커널 접근
            runAsUser: 0
          env:
            # 발견 설정
            - name: BEYLA_DISCOVERY_SERVICES
              value: "http"  # http, grpc, sql

            # OpenTelemetry 내보내기
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector.observability:4317"
            - name: OTEL_EXPORTER_OTLP_PROTOCOL
              value: "grpc"

            # Prometheus 메트릭
            - name: BEYLA_PROMETHEUS_PORT
              value: "9090"

            # 네임스페이스 필터
            - name: BEYLA_KUBE_NAMESPACE
              value: "production,staging"
          volumeMounts:
            - name: sys-kernel-debug
              mountPath: /sys/kernel/debug
      volumes:
        - name: sys-kernel-debug
          hostPath:
            path: /sys/kernel/debug
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: beyla
  namespace: observability
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: beyla
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "nodes"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: beyla
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: beyla
subjects:
  - kind: ServiceAccount
    name: beyla
    namespace: observability
```

### Sidecar 배포 (특정 앱)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      shareProcessNamespace: true  # Sidecar에서 앱 프로세스 접근
      containers:
        - name: my-app
          image: my-app:latest
          ports:
            - containerPort: 8080

        - name: beyla
          image: grafana/beyla:1.8
          securityContext:
            privileged: true
            runAsUser: 0
          env:
            - name: BEYLA_OPEN_PORT
              value: "8080"  # 특정 포트만 모니터링
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector.observability:4317"
```

### Beyla 설정 파일

```yaml
# beyla-config.yaml
discovery:
  services:
    - name: "http-services"
      k8s_namespace: "production"
      k8s_pod_labels:
        app: "*"
    - name: "grpc-services"
      k8s_namespace: "production"
      protocol: grpc

# 라우트 정규화
routes:
  patterns:
    - /api/users/{id}
    - /api/orders/{orderId}/items/{itemId}
  ignored_patterns:
    - /health
    - /ready
    - /metrics

# 메트릭 설정
prometheus:
  port: 9090
  path: /metrics

# 트레이싱 설정
otel:
  protocol: grpc
  endpoint: http://otel-collector:4317
  traces:
    enabled: true
    sampler:
      name: parentbased_traceidratio
      arg: "0.1"  # 10% 샘플링

# 필터
attributes:
  kubernetes:
    enable: true
```

---

## Odigos

### 개요

Odigos는 eBPF 기반 자동 계측 플랫폼으로, 설치만으로 클러스터 전체 애플리케이션을 OpenTelemetry로 계측합니다.

### 설치

```bash
# Helm 설치
helm repo add odigos https://keyval-dev.github.io/odigos-charts
helm install odigos odigos/odigos \
  --namespace odigos-system \
  --create-namespace

# 또는 CLI 설치
brew install odigos
odigos install
```

### 백엔드 설정

```yaml
# odigos-destination.yaml
apiVersion: odigos.io/v1alpha1
kind: Destination
metadata:
  name: jaeger
  namespace: odigos-system
spec:
  type: jaeger
  jaeger:
    endpoint: "jaeger-collector.observability:14250"
---
apiVersion: odigos.io/v1alpha1
kind: Destination
metadata:
  name: prometheus
  namespace: odigos-system
spec:
  type: prometheus
  prometheus:
    url: "http://prometheus.observability:9090/api/v1/write"
---
apiVersion: odigos.io/v1alpha1
kind: Destination
metadata:
  name: grafana-cloud
  namespace: odigos-system
spec:
  type: grafana
  grafana:
    url: "https://otlp-gateway-prod-us-central-0.grafana.net/otlp"
    secretRef:
      name: grafana-credentials
```

### 네임스페이스 활성화

```yaml
# 네임스페이스 레이블로 자동 계측 활성화
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    odigos-instrumentation: enabled
---
# 또는 InstrumentedApplication CR
apiVersion: odigos.io/v1alpha1
kind: InstrumentedApplication
metadata:
  name: my-app
  namespace: production
spec:
  instrumentations:
    - type: ebpf
      languages:
        - go
        - java
        - python
        - nodejs
        - dotnet
```

### 언어별 지원 현황

| 언어 | 지원 프레임워크 | 자동 계측 |
|------|----------------|----------|
| **Go** | net/http, gin, echo, fiber | eBPF |
| **Java** | Spring, Quarkus, Micronaut | eBPF + Agent |
| **Python** | Flask, Django, FastAPI | eBPF |
| **Node.js** | Express, Fastify, NestJS | eBPF |
| **.NET** | ASP.NET Core | eBPF |
| **Rust** | Actix, Axum | eBPF |

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 구버전 커널에서 실행 | 기능 제한/실패 | 커널 5.8+ 업그레이드 |
| privileged 없이 배포 | eBPF 로드 실패 | 적절한 capabilities |
| 모든 네임스페이스 활성화 | 오버헤드 증가 | 필요한 네임스페이스만 |
| 샘플링 미설정 | 과도한 데이터 | 10% 샘플링 시작 |
| Hubble L7 무분별 활성화 | CPU 사용량 급증 | 필요한 서비스만 |

---

## 체크리스트

### 환경 준비
- [ ] 커널 버전 확인 (5.8+ 권장)
- [ ] BTF 지원 확인
- [ ] SecurityContext 설정

### Beyla 배포
- [ ] DaemonSet 또는 Sidecar 선택
- [ ] 네임스페이스 필터 설정
- [ ] OTel Collector 연동

### Odigos 배포
- [ ] 백엔드 Destination 설정
- [ ] 네임스페이스 레이블
- [ ] 언어별 지원 확인

---

## 참조 스킬

- `ebpf-observability-advanced.md` - Cilium Hubble, DeepFlow, eBPF 요구사항, OTel 연동
- `/observability-otel` - OpenTelemetry 통합 가이드
- `/monitoring-metrics` - 메트릭 수집/시각화
- `/cilium-networking` - Cilium 네트워킹

---

## Sources

- [Grafana Beyla Documentation](https://grafana.com/docs/grafana-cloud/monitor-applications/application-observability/setup/instrument/beyla/)
- [Odigos Documentation](https://docs.odigos.io/)
