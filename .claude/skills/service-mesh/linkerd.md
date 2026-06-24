---
name: linkerd
description: "Linkerd Service Mesh 가이드 — Linkerd v2.17 핵심 운영 가이드: Rust micro-proxy 기반 경량 서비스 메시, 자동 mTLS, 멀티클러스터, Gateway API 통합 Use when working with service-mesh 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Linkerd Service Mesh 가이드

Linkerd v2.17 핵심 운영 가이드: Rust micro-proxy 기반 경량 서비스 메시, 자동 mTLS, 멀티클러스터, Gateway API 통합

## Quick Reference (결정 트리)

```
Service Mesh 선택?
    |
    +-- 최소 레이턴시 / 경량 우선 ---------> Linkerd (0.9ms p99)
    |       +-- mTLS만 필요 ---------------> Linkerd (zero-config)
    |       +-- L7 라우팅 필요 ------------> Linkerd HTTPRoute
    |       +-- 멀티클러스터 연동 ---------> Linkerd Multi-cluster
    |
    +-- 복잡한 L7 정책 / Wasm 필요 -------> Istio
    +-- 기존 Envoy 투자 -----------------> Istio Ambient
    +-- 간단한 mTLS + 최소 운영 ---------> Linkerd (권장)

Linkerd 기능 선택?
    |
    +-- 기본 보안 (mTLS) -----------------> linkerd inject (기본)
    +-- 트래픽 관리 ----------------------> HTTPRoute + ServiceProfile
    +-- 카나리 배포 ----------------------> SMI TrafficSplit
    +-- 멀티클러스터 ---------------------> Link CRD + Gateway
    +-- 관찰성 대시보드 -----------------> linkerd viz install
```

---

## CRITICAL: Linkerd 아키텍처

```
+------------------------------------------------------------------+
|  Control Plane                                                     |
|  +-------------+  +--------------+  +------------------+          |
|  | destination |  | identity     |  | proxy-injector   |          |
|  | (서비스     |  | (mTLS 인증서 |  | (Sidecar 자동    |          |
|  |  디스커버리)|  |  자동 발급)  |  |  주입)           |          |
|  +------+------+  +------+-------+  +--------+---------+          |
+---------+----------------+--------------------+-------------------+
          |                |                    |
          v                v                    v
+------------------------------------------------------------------+
|  Data Plane (Per Pod)                                              |
|  +--------------------+     +-----------------------------+       |
|  |  Application       |<--->|  linkerd2-proxy (Rust)      |       |
|  |  Container         |     |  - 자동 mTLS / L7 메트릭   |       |
|  +--------------------+     |  - EWMA 로드밸런싱         |       |
|                             |  - Retry / Timeout          |       |
|                             +-----------------------------+       |
|  메모리: ~10-20MB per proxy  |  레이턴시: < 1ms p99              |
+------------------------------------------------------------------+
```

---

## CRITICAL: Linkerd vs Istio Ambient 비교

| 항목 | Linkerd v2.17 | Istio Ambient |
|------|---------------|---------------|
| **프록시** | linkerd2-proxy (Rust) | ztunnel + waypoint (Envoy) |
| **P99 레이턴시** | **~0.9ms** | 3-10ms |
| **Control Plane 메모리** | **~200MB** | 1-2GB |
| **Sidecar 메모리** | ~10-20MB/pod | ztunnel ~50MB/node |
| **mTLS** | 자동 (zero-config) | 자동 (ztunnel) |
| **L7 정책** | HTTPRoute, ServiceProfile | waypoint 필요 |
| **Wasm 확장** | 미지원 | 지원 |
| **멀티클러스터** | Link CRD (간단) | 복잡 |
| **Gateway API** | v1.2 지원 | v1.2 지원 |
| **CNCF** | Graduated | Graduated |
| **설치** | `linkerd install` (2분) | `istioctl install` (5-10분) |
| **학습 곡선** | 낮음 | 높음 |

```yaml
# 성능 벤치마크 (3 Node, 100 서비스, 1000 RPS)
Linkerd:  P50 0.4ms | P99 0.9ms | CP 200MB | Proxy 2GB (100x20MB)
Ambient:  P50 1.5ms | P99 5-10ms | CP 1.5GB | ztunnel+wp 450MB
# 결론: 순수 성능 = Linkerd, 확장성/기능 = Istio
```

---

## 설치 및 기본 설정

```bash
# CLI 설치 + 사전 검증
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
export PATH=$HOME/.linkerd2/bin:$PATH
linkerd check --pre

# CRD + Control Plane 설치
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check
```

### Helm 설치 (프로덕션 권장)

```bash
helm repo add linkerd https://helm.linkerd.io/stable
helm install linkerd-crds linkerd/linkerd-crds -n linkerd --create-namespace
helm install linkerd-control-plane linkerd/linkerd-control-plane -n linkerd \
  --set identity.externalCA=true \
  --set identity.issuer.scheme=kubernetes.io/tls
```

### 프로덕션 인증서 설정

```bash
# Root CA + Issuer 인증서 생성 (프로덕션 필수)
step certificate create root.linkerd.cluster.local ca.crt ca.key \
  --profile root-ca --no-password --insecure --not-after=87600h
step certificate create identity.linkerd.cluster.local issuer.crt issuer.key \
  --profile intermediate-ca --not-after=8760h --no-password --insecure \
  --ca ca.crt --ca-key ca.key

linkerd install \
  --identity-trust-anchors-file ca.crt \
  --identity-issuer-certificate-file issuer.crt \
  --identity-issuer-key-file issuer.key | kubectl apply -f -
```

---

## CRITICAL: 자동 mTLS (Zero-Config)

### linkerd inject Annotation

```yaml
# Namespace 레벨 자동 주입
apiVersion: v1
kind: Namespace
metadata:
  name: production
  annotations:
    linkerd.io/inject: enabled
---
# Deployment 레벨 (프록시 리소스 커스터마이징)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: production
spec:
  template:
    metadata:
      annotations:
        linkerd.io/inject: enabled
        config.linkerd.io/proxy-cpu-request: "100m"
        config.linkerd.io/proxy-memory-request: "20Mi"
        config.linkerd.io/proxy-memory-limit: "128Mi"
    spec:
      containers:
      - name: order-service
        image: order-service:v1.2.0
        ports: [{ containerPort: 8080 }]
```

### CLI Injection 및 mTLS 확인

```bash
# 기존 Deployment에 프록시 주입
kubectl get deploy -n production -o yaml | linkerd inject - | kubectl apply -f -

# mTLS 연결 확인
linkerd viz edges po -n production
# SRC          DST              SECURED
# order-svc    payment-svc      TRUE
```

---

## HTTPRoute 기반 Rate Limiting

```yaml
# 1. Server 리소스 정의
apiVersion: policy.linkerd.io/v1beta3
kind: Server
metadata:
  name: order-server
  namespace: production
spec:
  podSelector:
    matchLabels: { app: order-service }
  port: 8080
  proxyProtocol: HTTP/2
---
# 2. Rate Limit 적용
apiVersion: policy.linkerd.io/v1alpha1
kind: HTTPLocalRateLimitPolicy
metadata:
  name: order-rate-limit
  namespace: production
spec:
  targetRef:
    group: core
    kind: Server
    name: order-server
  total:
    requestsPerSecond: 1000       # 전체 제한
  identity:
    requestsPerSecond: 100        # Identity별 제한
  overrides:
  - requestsPerSecond: 500        # VIP 클라이언트 예외
    clientRefs:
    - kind: ServiceAccount
      name: vip-client
---
# 3. Authorization Policy (mTLS Identity 기반)
apiVersion: policy.linkerd.io/v1alpha1
kind: AuthorizationPolicy
metadata:
  name: order-authz
  namespace: production
spec:
  targetRef:
    group: policy.linkerd.io
    kind: Server
    name: order-server
  requiredAuthenticationRefs:
  - name: order-mesh-authn
    kind: MeshTLSAuthentication
    group: policy.linkerd.io
---
apiVersion: policy.linkerd.io/v1alpha1
kind: MeshTLSAuthentication
metadata:
  name: order-mesh-authn
  namespace: production
spec:
  identityRefs:
  - kind: ServiceAccount
    name: api-gateway
  - kind: ServiceAccount
    name: frontend
```

---

## ServiceProfile (Per-Route 메트릭 / 재시도)

```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: order-service.production.svc.cluster.local
  namespace: production
spec:
  routes:
  - name: POST /api/orders
    condition: { method: POST, pathRegex: /api/orders }
    isRetryable: false    # 비멱등 API는 재시도 금지
    timeout: 3s
    responseClasses:
    - condition: { status: { min: 500, max: 599 } }
      isFailure: true
  - name: GET /api/orders/{id}
    condition: { method: GET, pathRegex: "/api/orders/[^/]+" }
    isRetryable: true
    timeout: 1s
  retryBudget:
    retryRatio: 0.2          # 전체 요청의 20%까지 재시도
    minRetriesPerSecond: 10
    ttl: 10s
```

```bash
# Swagger/Protobuf에서 자동 생성 후 경로별 메트릭 확인
linkerd profile --open-api swagger.json order-service -n production | kubectl apply -f -
linkerd viz routes deploy/order-service -n production
```

---

## SMI TrafficSplit (카나리 배포)

```yaml
# 가중치 기반 트래픽 분할 (90% stable / 10% canary)
apiVersion: split.smi-spec.io/v1alpha4
kind: TrafficSplit
metadata:
  name: order-canary
  namespace: production
spec:
  service: order-service        # 클라이언트가 호출하는 루트 서비스
  backends:
  - service: order-service-stable
    weight: 900
  - service: order-service-canary
    weight: 100
# order-service-stable: selector { app: order-service, version: v1 }
# order-service-canary: selector { app: order-service, version: v2 }
```

### Flagger 연동 자동 카나리

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: order-service
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  service: { port: 8080 }
  analysis:
    interval: 30s
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
    - name: request-success-rate
      thresholdRange: { min: 99 }
      interval: 1m
    - name: request-duration
      thresholdRange: { max: 500 }
      interval: 1m
```

---

## Linkerd Viz 대시보드

```bash
# Viz 확장 설치 + 대시보드
linkerd viz install | kubectl apply -f -
linkerd check
linkerd viz dashboard &

# CLI 메트릭 확인
linkerd viz stat deploy -n production
linkerd viz routes deploy/order-service -n production
linkerd viz top deploy -n production

# 실시간 트래픽 tap (디버깅)
linkerd viz tap deploy/order-service -n production --path /api/orders

# 외부 Prometheus 연동 (프로덕션)
linkerd viz install \
  --set prometheus.enabled=false \
  --set prometheusUrl=http://prometheus.monitoring:9090 | kubectl apply -f -
```

### 핵심 Prometheus 쿼리

```promql
# 성공률
sum(rate(response_total{classification="success",namespace="production"}[5m]))
/ sum(rate(response_total{namespace="production"}[5m]))

# P99 레이턴시
histogram_quantile(0.99,
  sum(rate(response_latency_ms_bucket{namespace="production"}[5m])) by (le, deployment))
```

---

## CRITICAL: 멀티클러스터 (Federated Services)

```
+---------------------+          +---------------------+
|    Cluster West     |   Link   |    Cluster East     |
|  +---------------+  |---CRD----|  +---------------+  |
|  | order-service |--+  mTLS   +->| order-service |  |
|  +---------------+  |  Gateway |  +---------------+  |
|  Shared Trust Root  |          |  Shared Trust Root  |
+---------------------+          +---------------------+
```

### 멀티클러스터 설치

```bash
# 공통 Root CA 생성 (양쪽 클러스터 필수)
step certificate create root.linkerd.cluster.local ca.crt ca.key \
  --profile root-ca --no-password --insecure --not-after=87600h

# 각 클러스터에 같은 Trust Anchor로 설치
linkerd install --identity-trust-anchors-file ca.crt \
  --identity-issuer-certificate-file west-issuer.crt \
  --identity-issuer-key-file west-issuer.key \
  | kubectl --context=west apply -f -

# 멀티클러스터 확장 + 링크 생성
linkerd multicluster install | kubectl --context=west apply -f -
linkerd multicluster install | kubectl --context=east apply -f -
linkerd multicluster link --context=east --cluster-name east \
  | kubectl --context=west apply -f -
linkerd multicluster check --context=west
```

### Link CRD 및 서비스 미러링

```yaml
# Link 리소스 (자동 생성됨, 참고용)
apiVersion: multicluster.linkerd.io/v1alpha1
kind: Link
metadata:
  name: east
  namespace: linkerd-multicluster
spec:
  targetClusterName: east
  targetClusterDomain: cluster.local
  clusterCredentialsSecret: cluster-credentials-east
  gatewayAddress: gateway-east.example.com
  gatewayPort: 4143
  selector:
    matchLabels:
      mirror.linkerd.io/exported: "true"
---
# 원격 서비스 export (East 클러스터에서 설정)
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: production
  labels:
    mirror.linkerd.io/exported: "true"    # 이 레이블로 자동 미러링
spec:
  selector: { app: payment-service }
  ports: [{ port: 8080 }]
# West에서 payment-service-east.production.svc.cluster.local 로 접근
```

---

## Gateway API 통합

```yaml
# Linkerd + Gateway API HTTPRoute (헤더 기반 카나리 + 가중치 라우팅)
apiVersion: gateway.networking.k8s.io/v1beta1
kind: HTTPRoute
metadata:
  name: order-route
  namespace: production
spec:
  parentRefs:
  - name: order-service
    kind: Service
    group: core
    port: 8080
  rules:
  - matches:
    - path: { type: PathPrefix, value: /api/v2/orders }
      headers: [{ name: X-Canary, value: "true" }]
    backendRefs:
    - name: order-service-canary
      port: 8080
  - matches:
    - path: { type: PathPrefix, value: /api/orders }
    backendRefs:
    - { name: order-service-stable, port: 8080, weight: 90 }
    - { name: order-service-canary, port: 8080, weight: 10 }
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 기본 인증서로 프로덕션 운영 | 만료 시 메시 전체 중단 | `step` CLI 외부 CA, cert-manager 연동 |
| 모든 Pod에 무조건 inject | init container, Job 오작동 | `linkerd.io/inject: disabled` 예외 |
| ServiceProfile 없이 운영 | per-route 메트릭 부재 | Swagger/Protobuf에서 자동 생성 |
| Viz를 프로덕션 모니터링으로 사용 | 내장 Prometheus 용량 부족 | 외부 Prometheus/Grafana 연동 |
| 멀티클러스터 Trust Anchor 불일치 | 클러스터 간 mTLS 실패 | 공통 Root CA 반드시 공유 |
| non-HTTP 트래픽 무시 | TCP 프록시 오작동 | `config.linkerd.io/skip-outbound-ports` |
| Retry를 비멱등 API에 적용 | 중복 주문/결제 발생 | `isRetryable: false` 명시 |
| 업그레이드 시 CLI 버전 불일치 | CP/DP 호환 문제 | `linkerd check` 반드시 실행 |

---

## 체크리스트

### 초기 설치
- [ ] `linkerd check --pre` 사전 검증 통과
- [ ] 프로덕션용 Trust Anchor / Issuer 인증서 설정
- [ ] cert-manager 또는 외부 CA 연동
- [ ] `linkerd check` 전체 통과

### Namespace 온보딩
- [ ] `linkerd.io/inject: enabled` annotation 추가
- [ ] 기존 Deployment 재배포 (프록시 주입)
- [ ] `linkerd edges` 로 mTLS 연결 확인
- [ ] init container / Job 등 예외 처리

### 트래픽 관리
- [ ] ServiceProfile 생성 (per-route 메트릭)
- [ ] 재시도 정책 설정 (멱등 API만)
- [ ] 타임아웃 / Authorization Policy 설정

### 관찰성
- [ ] Viz 확장 설치
- [ ] 외부 Prometheus 연동 (프로덕션)
- [ ] 성공률 / 레이턴시 / 처리량 알림 설정

### 멀티클러스터
- [ ] 공통 Trust Anchor 공유
- [ ] multicluster extension 설치
- [ ] Link CRD 생성 및 검증
- [ ] 서비스 미러링 확인 (`mirror.linkerd.io/exported`)

### 업그레이드
- [ ] CLI -> CRD -> Control Plane -> Data Plane 순서
- [ ] `linkerd check` 최종 검증

---

**관련 스킬**: `/istio-core`, `/istio-ambient`, `/k8s-traffic`, `/gateway-api`
