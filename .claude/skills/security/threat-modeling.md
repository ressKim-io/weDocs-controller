---
name: threat-modeling
description: "Threat Modeling Guide — STRIDE/DREAD 위협 모델링, Microsoft Kubernetes Threat Matrix, 위협 분석 프로세스 Use when working with security 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Threat Modeling Guide

STRIDE/DREAD 위협 모델링, Microsoft Kubernetes Threat Matrix, 위협 분석 프로세스

## Quick Reference (결정 트리)

```
위협 모델링 시작점?
    │
    ├─ 신규 시스템 설계 ────> STRIDE 분석 (아래 참조)
    ├─ 기존 시스템 보안 평가 → STRIDE + DREAD 스코어링
    ├─ K8s 환경 위협 평가 ──> Microsoft K8s Threat Matrix
    └─ 규정 준수 요구 ─────> STRIDE + Compliance Mapping

위협 심각도 판단?
    │
    ├─ 정량적 평가 필요 ───> DREAD 스코어링 (5개 기준)
    ├─ 빠른 분류 필요 ────> STRIDE 카테고리별 High/Medium/Low
    └─ 비즈니스 영향 중심 → Risk Matrix (Likelihood x Impact)

도구 선택?
    │
    ├─ 다이어그램 기반 ───> threat-composer (AWS), IriusRisk
    ├─ 코드 기반 ─────────> pytm (Python), Threagile (YAML)
    └─ 수동 워크숍 ───────> STRIDE 카드 + 화이트보드
```

---

## STRIDE Model

Microsoft에서 개발한 위협 분류 모델. 각 카테고리는 보안 속성의 위반을 나타낸다.

### STRIDE 카테고리 상세

| 위협 | 보안 속성 위반 | 설명 | 대응 원칙 |
|------|-------------|------|----------|
| **S**poofing | Authentication | 다른 사용자/시스템으로 위장 | 강력한 인증 |
| **T**ampering | Integrity | 데이터/코드 무단 변경 | 무결성 검증 |
| **R**epudiation | Non-Repudiation | 행위 부인 (증거 부재) | 감사 로깅 |
| **I**nformation Disclosure | Confidentiality | 비인가 정보 노출 | 암호화/접근 제어 |
| **D**enial of Service | Availability | 서비스 가용성 저해 | 가용성 보호 |
| **E**levation of Privilege | Authorization | 권한 상승 | 최소 권한 원칙 |

### Spoofing (위장)

```
위협 시나리오:
  - 도난된 JWT 토큰으로 API 호출
  - 서비스 간 mTLS 없이 임의 서비스 위장
  - K8s ServiceAccount 토큰 탈취

완화 조치:
  - JWT 만료 시간 단축 (15분 이내)
  - mTLS 필수 (Istio STRICT mode)
  - ServiceAccount 자동 마운트 비활성화
  - OIDC 기반 클러스터 인증
```

### Tampering (변조)

```
위협 시나리오:
  - 컨테이너 이미지 변조 (supply chain attack)
  - etcd 데이터 직접 수정
  - ConfigMap/Secret 무단 변경
  - Man-in-the-middle 공격으로 API 요청 변조

완화 조치:
  - 이미지 서명 검증 (cosign/sigstore)
  - etcd 암호화 at rest
  - OPA/Kyverno Admission Controller
  - mTLS로 통신 채널 보호
  - Immutable ConfigMap/Secret
```

### Repudiation (부인)

```
위협 시나리오:
  - 관리자의 kubectl 명령 실행 기록 부재
  - 데이터 삭제 후 증거 없음
  - 배포 변경 추적 불가

완화 조치:
  - K8s Audit Policy (RequestResponse 레벨)
  - 감사 로그 외부 전송 (변조 방지)
  - GitOps로 모든 변경 Git 기록
  - WORM(Write Once Read Many) 스토리지
```

### Information Disclosure (정보 노출)

```
위협 시나리오:
  - Secret이 환경변수로 노출 (kubectl describe pod)
  - 에러 스택트레이스에 민감 정보 포함
  - etcd 백업 파일 비암호화 노출
  - 로그에 PII/PHI 데이터 기록

완화 조치:
  - External Secrets Operator 사용
  - 프로덕션 에러 응답 마스킹
  - etcd 암호화 + 백업 암호화
  - 로그 필터링/마스킹 파이프라인
```

### Denial of Service (서비스 거부)

```
위협 시나리오:
  - Pod에 리소스 제한 미설정 → 노드 자원 고갈
  - API Server 과부하 (대량 API 호출)
  - 네트워크 공격으로 서비스 불능
  - 스토리지 볼륨 고갈

완화 조치:
  - ResourceQuota/LimitRange 설정
  - API Priority and Fairness (APF)
  - NetworkPolicy로 불필요한 트래픽 차단
  - PDB(PodDisruptionBudget) 설정
  - Rate limiting (Istio/Gateway API)
```

### Elevation of Privilege (권한 상승)

```
위협 시나리오:
  - 컨테이너 escape → 노드 접근
  - 과도한 RBAC (cluster-admin 남용)
  - Privileged 컨테이너 실행
  - hostPath 마운트로 노드 파일시스템 접근

완화 조치:
  - Pod Security Standards (restricted)
  - 최소 권한 RBAC (네임스페이스 스코프)
  - seccomp/AppArmor 프로필 적용
  - hostPath 마운트 금지 (Admission Policy)
```

---

## DREAD Scoring

위협의 심각도를 정량적으로 평가하는 모델.

### 평가 기준 (각 1~10점)

| 기준 | 설명 | 점수 기준 |
|------|------|----------|
| **D**amage | 피해 규모 | 1: 사소한 정보 노출 → 10: 전체 시스템 장악 |
| **R**eproducibility | 재현 용이성 | 1: 거의 불가 → 10: 항상 재현 |
| **E**xploitability | 공격 용이성 | 1: 고급 기술 필요 → 10: 초보자도 가능 |
| **A**ffected Users | 영향 범위 | 1: 단일 사용자 → 10: 전체 사용자 |
| **D**iscoverability | 발견 용이성 | 1: 거의 불가능 → 10: 공개 정보 |

### DREAD 계산

```
DREAD Score = (D + R + E + A + D) / 5

등급:
  12~15: Critical (즉시 조치)
   8~11: High (2주 이내 조치)
   5~7 : Medium (분기 내 조치)
   1~4 : Low (백로그 등록)
```

### 예시: JWT 토큰 탈취

```
위협: 만료되지 않은 JWT 토큰 탈취를 통한 API 접근
  Damage:          8 (전체 사용자 데이터 접근 가능)
  Reproducibility: 9 (토큰만 있으면 항상 재현)
  Exploitability:  7 (네트워크 스니핑 또는 XSS 필요)
  Affected Users:  6 (토큰 소유자의 데이터 범위)
  Discoverability: 5 (토큰이 로그/브라우저에 노출 가능)

  DREAD = (8+9+7+6+5)/5 = 7.0 → Medium-High
  권장: 토큰 만료 15분, Refresh Token Rotation, HttpOnly Cookie
```

---

## Microsoft Kubernetes Threat Matrix

MITRE ATT&CK 프레임워크를 Kubernetes 환경에 매핑한 위협 매트릭스.

### Threat Matrix 전체 맵

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Initial  │Execution │Persist-  │Privilege │Defense   │
│ Access   │          │ence      │Escalation│Evasion   │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│Compromised│Exec into │Backdoor  │Privileged│Clear     │
│Image     │Container │Container │Container │Container │
│          │          │          │          │Logs      │
│Kubeconfig│bash/cmd  │Writable  │Cluster-  │Delete    │
│Theft     │in pod    │hostPath  │admin     │K8s Events│
│          │          │          │Binding   │          │
│Exposed   │New       │K8s       │hostPath  │Pod Name  │
│Dashboard │Container │CronJob   │Mount     │Similarity│
│          │          │          │          │          │
│Vulnerable│App       │Malicious │Access    │Connect   │
│App       │Exploit   │Admission │Cloud     │from Proxy│
│          │          │Controller│Metadata  │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘

┌──────────┬──────────┬──────────┬──────────┐
│Credential│Discovery │Lateral   │Impact    │
│Access    │          │Movement  │          │
├──────────┼──────────┼──────────┼──────────┤
│List K8s  │Access K8s│Access    │Data      │
│Secrets   │API Server│Cloud     │Destruction│
│          │          │Resources │          │
│Mount     │Network   │Container │Resource  │
│Service   │Scanning  │Service   │Hijacking │
│Account   │          │Account   │(Crypto)  │
│Token     │          │          │          │
│Access    │Instance  │Cluster   │Denial of │
│Managed   │Metadata  │Internal  │Service   │
│Identity  │API       │Networking│          │
└──────────┴──────────┴──────────┴──────────┘
```

### Initial Access (초기 접근)

| 공격 벡터 | 설명 | 탐지/완화 |
|----------|------|----------|
| Compromised Image | 악성 코드가 포함된 컨테이너 이미지 | Trivy 스캔 + 이미지 서명 검증 |
| Kubeconfig Theft | kubeconfig 파일 유출 | 감사 로그에서 비정상 IP 탐지 |
| Exposed Dashboard | K8s Dashboard 인터넷 노출 | NetworkPolicy + 인증 강제 |
| Vulnerable App | 애플리케이션 취약점 (RCE 등) | WAF + 런타임 보안 (Falco) |
| Cloud Credential | 클라우드 자격증명 탈취 | IMDS v2 강제 + 최소 권한 IAM |

### Execution (실행)

| 공격 벡터 | 설명 | 완화 조치 |
|----------|------|----------|
| Exec into Container | kubectl exec로 컨테이너 접근 | RBAC으로 exec 권한 제한 |
| New Container | 악성 Pod/Container 생성 | Admission Controller (OPA/Kyverno) |
| Application Exploit | 앱 취약점 악용 (RCE, SSRF) | seccomp, read-only rootfs |
| SSH Server | 컨테이너 내 SSH 서버 실행 | 이미지 스캔, 프로세스 모니터링 |

### Persistence (지속성)

| 공격 벡터 | 설명 | 완화 조치 |
|----------|------|----------|
| Backdoor Container | 백도어가 포함된 컨테이너 배포 | 이미지 허용 목록, 서명 검증 |
| Writable hostPath | 호스트 파일시스템에 악성 파일 배치 | hostPath 마운트 금지 정책 |
| K8s CronJob | 악성 CronJob 생성 | CronJob 생성 RBAC 제한 |
| Malicious Admission | 악성 Webhook으로 모든 배포 변조 | Webhook 감사 + 서명 검증 |

### Privilege Escalation (권한 상승)

| 공격 벡터 | 설명 | 완화 조치 |
|----------|------|----------|
| Privileged Container | 특권 컨테이너로 노드 접근 | Pod Security Standards (restricted) |
| cluster-admin Binding | 과도한 RBAC 바인딩 | 정기적 RBAC 리뷰, 자동 탐지 |
| hostPath Mount | 노드 파일시스템 마운트 | Admission Policy로 차단 |
| Cloud Metadata | 169.254.169.254 접근으로 IAM 탈취 | NetworkPolicy로 메타데이터 차단 |

### Defense Evasion (방어 회피)

| 공격 벡터 | 설명 | 완화 조치 |
|----------|------|----------|
| Clear Container Logs | 컨테이너 로그 삭제 | 중앙화된 로그 수집 (외부 전송) |
| Delete K8s Events | K8s 이벤트 삭제 | Events 외부 전송, RBAC 제한 |
| Pod Name Similarity | 정상 Pod과 유사한 이름 사용 | 라벨 기반 정책, 이미지 allowlist |
| Connect from Proxy | 프록시를 통한 우회 접근 | 네트워크 모니터링, Falco 규칙 |

### Credential Access (자격증명 접근)

| 공격 벡터 | 설명 | 완화 조치 |
|----------|------|----------|
| List K8s Secrets | kubectl get secrets 실행 | RBAC으로 Secret 접근 제한 |
| Mount SA Token | ServiceAccount 토큰 탈취 | automountServiceAccountToken: false |
| Managed Identity | 클라우드 IAM 토큰 탈취 | Workload Identity + 최소 권한 |
| App Credential in Config | ConfigMap/env에 자격증명 | External Secrets + Vault |

---

## Threat Modeling Process (4단계)

### Step 1: 시스템 분해 (Decompose)

```
1. 데이터 흐름 다이어그램(DFD) 작성
   - 외부 엔티티 (사용자, 외부 API)
   - 프로세스 (마이크로서비스)
   - 데이터 저장소 (DB, 캐시, 큐)
   - 데이터 흐름 (화살표 + 프로토콜)
   - 신뢰 경계 (Trust Boundary)

2. 자산 식별
   - 보호 대상 데이터 (PII, PHI, 카드정보)
   - 핵심 서비스 (인증, 결제, 주문)
   - 인프라 (K8s API Server, etcd)
```

### Step 2: 위협 식별 (Identify Threats)

```
각 데이터 흐름/컴포넌트에 STRIDE 적용:

[User] --HTTPS--> [API Gateway] --gRPC--> [Order Service] --TCP--> [DB]
  │                    │                       │                    │
  S: 토큰 위조         S: 인증 우회            T: 주문 변조         I: DB 유출
  T: 요청 변조         D: DDoS                R: 주문 부인         D: DB 다운
  I: 토큰 유출         E: 관리자 권한 획득      E: 서비스 권한 상승   T: 데이터 변조
```

### Step 3: 위험 평가 (Assess Risk)

```
각 위협에 DREAD 점수 부여 → 우선순위 결정:

| 위협         | D | R | E | A | D | Score | 우선순위 |
|-------------|---|---|---|---|---|-------|---------|
| JWT 위조     | 8 | 7 | 5 | 9 | 6 | 7.0   | High    |
| DB 인젝션    | 9 | 8 | 6 | 10| 7 | 8.0   | Critical|
| DDoS        | 5 | 9 | 8 | 10| 9 | 8.2   | Critical|
```

### Step 4: 완화 계획 (Mitigate)

```
각 위협에 대한 완화 조치 결정:

Critical/High 위협 → 즉시 구현
Medium 위협       → 스프린트 백로그
Low 위협          → 분기별 리뷰

완화 전략:
  - Eliminate: 기능 제거/간소화
  - Mitigate: 보안 컨트롤 추가
  - Transfer: 보험/외부 서비스 위임
  - Accept: 리스크 수용 (문서화 필수)
```

---

## Example: Microservice Threat Model

### 대상: 주문 처리 시스템

```
┌─────────┐     ┌───────────┐     ┌──────────┐     ┌────────┐
│  User   │────>│API Gateway│────>│Order Svc │────>│  DB    │
│(Browser)│     │(Kong/Istio)│    │(Spring)  │     │(PgSQL) │
└─────────┘     └───────────┘     └──────────┘     └────────┘
                      │                │
                      │                ▼
                      │          ┌──────────┐
                      │          │Payment Svc│───> External PSP
                      │          └──────────┘
                      ▼
                ┌──────────┐
                │Auth Svc  │───> Redis (Session)
                └──────────┘
```

### STRIDE 분석 결과

| 컴포넌트 | S | T | R | I | D | E |
|---------|---|---|---|---|---|---|
| API GW | JWT 위조 | 헤더 변조 | - | 에러 정보 노출 | Rate limit 우회 | - |
| Order | 사용자 위장 | 금액 변조 | 주문 부인 | 내역 유출 | 대량 주문 DoS | 관리자 API 접근 |
| Payment | 결제자 위장 | 금액 변조 | 결제 부인 | 카드 정보 유출 | PSP 타임아웃 | - |
| DB | - | SQL 인젝션 | 로그 삭제 | 데이터 덤프 | 커넥션 고갈 | DB 관리자 접근 |

---

## Mitigations Per Threat Type

### 위협별 자동 점검 명령

```bash
# Spoofing 완화: mTLS 적용 확인
istioctl analyze -n production 2>/dev/null
kubectl get peerauthentication -A -o yaml | grep -A5 "mtls"

# Tampering 완화: 이미지 서명 검증 확인
cosign verify --key cosign.pub registry.example.com/app:latest

# Repudiation 완화: 감사 로그 활성화 확인
kubectl get pods -n kube-system -l component=kube-apiserver \
  -o jsonpath='{.items[0].spec.containers[0].command}' | \
  tr ',' '\n' | grep audit

# Information Disclosure 완화: Secret 암호화 확인
kubectl get apiserver -o jsonpath='{..encryptionConfiguration}' 2>/dev/null

# DoS 완화: 리소스 제한 미설정 Pod 탐지
kubectl get pods -A -o json | \
  jq '[.items[] | select(.spec.containers[].resources.limits == null) |
  {ns: .metadata.namespace, name: .metadata.name}]'

# Elevation of Privilege 완화: 특권 컨테이너 탐지
kubectl get pods -A -o json | \
  jq '[.items[] | select(.spec.containers[].securityContext.privileged == true) |
  {ns: .metadata.namespace, name: .metadata.name}]'
```

---

## Tools

### threat-composer (AWS)

```
- 웹 기반 위협 모델링 도구
- STRIDE 자동 분류
- AWS Well-Architected 통합
- URL: https://github.com/awslabs/threat-composer
```

### pytm (Python Threat Modeling)

```python
# pip install pytm
from pytm import TM, Server, Datastore, Dataflow, Boundary, Actor

tm = TM("Order System Threat Model")
internet = Boundary("Internet")
k8s = Boundary("Kubernetes Cluster")

user = Actor("User")
user.inBoundary = internet

api_gw = Server("API Gateway")
api_gw.inBoundary = k8s

order_svc = Server("Order Service")
order_svc.inBoundary = k8s

db = Datastore("PostgreSQL")
db.inBoundary = k8s
db.isEncrypted = True

Dataflow(user, api_gw, "HTTPS Request")
Dataflow(api_gw, order_svc, "gRPC (mTLS)")
Dataflow(order_svc, db, "TCP/TLS")
tm.process()
```

### Threagile (YAML 기반)

```yaml
# threagile.yaml - YAML로 위협 모델 정의, https://threagile.io
title: Order Processing System
technical_assets:
  api-gateway: { type: process, technologies: [kong] }
  order-service: { type: process, technologies: [spring-boot] }
```

---

## Threat Model Output Template

```markdown
## Threat Model: {시스템 이름}

### 1. System Overview
- 아키텍처 다이어그램
- 신뢰 경계 (Trust Boundaries)
- 데이터 흐름 (Data Flows)

### 2. Assets
| Asset | Classification | Owner |
|-------|---------------|-------|

### 3. Threat Analysis (STRIDE)
| ID | Category | Threat | Component | DREAD Score | Priority |
|----|----------|--------|-----------|-------------|----------|

### 4. Mitigations
| Threat ID | Mitigation | Status | Owner | Deadline |
|-----------|-----------|--------|-------|----------|

### 5. Residual Risks
| Risk | Impact | Likelihood | Decision |
|------|--------|------------|----------|
```

---

## Related Skills

| 스킬 | 용도 |
|------|------|
| `security/compliance-frameworks` | SOC2/HIPAA/GDPR/PCI-DSS 프레임워크 |
| `kubernetes/k8s-security` | K8s 보안 구성 |
| `cicd/supply-chain-security` | 공급망 보안 (이미지 서명, SBOM) |
| `observability/logging-security` | 보안 로깅 |
| `service-mesh/istio-security` | Istio mTLS, AuthorizationPolicy |
