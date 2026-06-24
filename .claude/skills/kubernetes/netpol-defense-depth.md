---
name: netpol-defense-depth
description: Kubernetes NetworkPolicy + 서비스 메시 AuthorizationPolicy의 멀티 레이어 방어 체크리스트. ingress + egress + AuthZ 3중 구조 누락 검출. CNI 호환성과 default deny 정책 포함.
---

# NetworkPolicy Defense in Depth

K8s NetworkPolicy(NP) + 서비스 메시 AuthorizationPolicy(AuthZ) 의 **3중 방어 체계**를 검증하는 체크리스트.
단일 레이어만 설정하면 우회 가능성이 있으며, 한 레이어 누락이 production 통신 차단 / 보안 우회의 단골 원인.

> ⚠️ 가장 흔한 사고: ingress만 막고 egress 누락 → 외부 worker가 internal API 호출 불가, CrashLoopBackOff.

---

## 3중 방어 모델

```
+----------------------------------+
| Layer 3: AuthorizationPolicy     | ← 메시(Istio) L7 인증/인가
| (sidecar / waypoint)             |
+----------------------------------+
| Layer 2: NetworkPolicy (egress)  | ← Pod → 외부로 나가는 트래픽
+----------------------------------+
| Layer 1: NetworkPolicy (ingress) | ← 외부 → Pod로 들어오는 트래픽
+----------------------------------+
```

각 레이어가 독립적으로 동작하며, 한 곳만 막혀도 통신 실패. **3개 모두 통일된 의도로 설정해야 함**.

---

## 체크리스트

### Layer 1: NetworkPolicy ingress

- [ ] **Default deny** ingress policy가 namespace에 존재 (`spec.podSelector: {}`)
- [ ] Pod별 ingress allow rule 명시 — 다른 namespace에서 접근 시 `namespaceSelector` 필수
- [ ] `from.ports` 명시 (`8080`, `9090` 등) — 모든 포트 열기 금지
- [ ] kube-prometheus-stack scraping을 허용하려면 `release: kube-prometheus-stack` 라벨에 ingress 허용
- [ ] DNS (53 UDP/TCP) ingress 허용 — kube-dns / CoreDNS namespace

### Layer 2: NetworkPolicy egress

- [ ] **Default deny** egress policy가 namespace에 존재 (`policyTypes: [Egress]`)
- [ ] DNS egress 허용 (`kube-dns` 또는 `kube-system/k8s-app=kube-dns` to UDP 53)
- [ ] 외부 API 호출 시 ip block 또는 FQDN(예: Cilium FQDN policy) egress 허용
- [ ] 메트릭/로그/추적 백엔드 egress 허용 (Prometheus / Loki / Tempo / OTLP collector)
- [ ] DB / cache egress 허용 (PostgreSQL 5432, Redis 6379)
- [ ] **메시 컨트롤 플레인 egress** 허용 (`istio-system/istiod:15012,15014`) — Istio injection 시 필수

### Layer 3: AuthorizationPolicy (Istio / 메시)

- [ ] namespace 또는 mesh-wide **default deny** AuthorizationPolicy 존재
- [ ] Service A → Service B 호출 시 source principal (`spiffe://cluster.local/ns/<ns>/sa/<sa>`) 명시
- [ ] 외부 진입점(Gateway)에 RequestAuthentication + AuthorizationPolicy 조합
- [ ] mTLS PeerAuthentication `STRICT` 모드 적용

---

## CNI 호환성

NetworkPolicy 효력은 CNI 구현에 따라 다르다.

| CNI | NP 지원 | 비고 |
|-----|--------|------|
| Cilium | ✅ + FQDN, L7 | CiliumNetworkPolicy로 L7/FQDN 확장 |
| Calico | ✅ + GlobalNetworkPolicy | GlobalNP는 namespace 무관 |
| Flannel | ❌ | NP CRD는 받지만 enforce 안 함 — 위험 |
| AWS VPC CNI | ✅ (1.14+) | Security Group for Pods로 추가 격리 |
| GKE Dataplane V2 | ✅ (Cilium 기반) | FQDN policy 지원 |

CNI가 NP를 enforce하지 않으면 NP 작성이 **보안 흉내**에 그친다 — 실제 enforce 여부 확인 필수.

---

## 트러블슈팅 순서 (NP/AuthZ 의심 시)

```
1. NetworkPolicy 목록 확인
   kubectl get netpol -n <ns>

2. Pod label로 NP 매칭 확인
   kubectl get netpol -n <ns> -o jsonpath='{.items[*].spec.podSelector}'

3. egress 차단 의심 시 — Pod에서 직접 테스트
   kubectl exec <pod> -- bash -c 'echo > /dev/tcp/<host>/<port>'   # bash 필수

4. AuthZ 차단 의심 시 — sidecar 로그
   kubectl logs <pod> -c istio-proxy --tail=100 | grep -i rbac

5. mTLS 의심 시 — PeerAuthentication 확인
   kubectl get peerauthentication -A
```

---

## 실제 사고 패턴

| 사고 | 누락 레이어 | 증상 |
|------|---------|------|
| Kafka producer connection refused | egress NP (broker 포트 9092 미허용) | CrashLoopBackOff |
| metrics-collector → Mimir push 실패 | egress NP (monitoring namespace 미허용) | 메트릭 누락 |
| Service A → Service B 401 | AuthZ default deny + source 미명시 | 401 reject |
| Istio sidecar inject 후 모든 통신 실패 | egress NP (istiod 15012 미허용) | Pod ready 안 됨 |
| Pod → Pod 통신 작동 안 함 | CNI가 Flannel — NP 미enforce | NP 작성 무용 |

---

## PR 작성 시 자기 점검

NP / AuthZ 변경 PR 작성 후:

- [ ] ingress / egress / AuthZ 3 레이어 모두 의도가 맞는가?
- [ ] default deny가 namespace에 존재하는가?
- [ ] DNS / 메시 컨트롤 플레인 egress 누락 안 했는가?
- [ ] CNI가 실제로 NP를 enforce 하는가?
- [ ] AuthZ source principal이 SPIFFE ID 형식인가?
- [ ] `kubectl exec ... bash -c 'echo > /dev/tcp/...'` 로 통신 검증했는가?
