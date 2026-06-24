---
name: compliance-frameworks
description: "Compliance Frameworks Guide — SOC2, HIPAA, GDPR, PCI-DSS 컴플라이언스 프레임워크 매핑 및 자동화 증거 수집 Use when working with security 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Compliance Frameworks Guide

SOC2, HIPAA, GDPR, PCI-DSS 컴플라이언스 프레임워크 매핑 및 자동화 증거 수집

## Quick Reference (결정 트리)

```
어떤 프레임워크가 필요한가?
    │
    ├─ 미국 B2B SaaS ────────> SOC2 Type II (필수)
    ├─ 의료/헬스케어 데이터 ──> HIPAA (PHI 보호)
    ├─ EU 사용자 데이터 ──────> GDPR (개인정보 보호)
    ├─ 결제/카드 데이터 ──────> PCI-DSS (카드홀더 데이터)
    └─ 복수 프레임워크 ───────> 공통 컨트롤 매핑 (아래 참조)

프레임워크 우선순위?
    │
    ├─ 스타트업 ──────> SOC2 먼저 → 나머지 점진적 추가
    ├─ 헬스케어 ─────> HIPAA + SOC2 동시
    ├─ 핀테크 ───────> PCI-DSS + SOC2
    └─ 글로벌 SaaS ──> GDPR + SOC2 + 지역별 추가

Kubernetes 환경 컴플라이언스?
    │
    ├─ 접근 제어 ──────> RBAC + OPA/Kyverno
    ├─ 네트워크 격리 ──> NetworkPolicy + Service Mesh
    ├─ 암호화 ─────────> etcd encryption + mTLS
    └─ 감사 로깅 ──────> Audit Policy + Falco
```

---

## Framework Overview

| 프레임워크 | 대상 | 핵심 요구사항 | 인증/감사 주기 | 위반 시 벌금 |
|-----------|------|-------------|--------------|------------|
| SOC2 | B2B SaaS | Trust Service Criteria (5개 원칙) | 연 1회 (Type II) | 계약 위반/신뢰 손실 |
| HIPAA | 헬스케어 | PHI 보호 (기술적/관리적/물리적) | 상시 (OCR 감사) | $100~$50,000/건 |
| GDPR | EU 개인정보 | 데이터 주체 권리, DPO, DPIA | 상시 (DPA 감사) | 매출 4% 또는 2000만 EUR |
| PCI-DSS | 결제 카드 | 12개 요구사항, 카드홀더 데이터 보호 | 연 1회 (QSA/SAQ) | $5,000~$100,000/월 |

---

## SOC2 Trust Service Criteria

### 5대 원칙 (Trust Service Principles)

```
┌──────────────────────────────────────────────────────┐
│                   SOC2 Framework                      │
├────────────┬────────────┬──────────┬────────┬────────┤
│  Security  │Availability│Processing│Confid- │Privacy │
│  (필수)    │            │Integrity │ential  │        │
│  CC1-CC9   │  A1        │  PI1     │  C1    │  P1    │
│            │            │          │        │        │
│ 접근 제어  │ SLA/SLO    │ 데이터   │ 데이터 │개인정보│
│ 변경 관리  │ 장애 복구  │ 정확성   │ 기밀성 │처리    │
│ 리스크 관리│ 백업/DR    │ 검증     │ 분류   │동의    │
└────────────┴────────────┴──────────┴────────┴────────┘
```

### CC (Common Criteria) 주요 항목

| CC 번호 | 영역 | K8s 매핑 |
|---------|------|---------|
| CC1 | COSO: 통제 환경 | 조직 정책 문서화 |
| CC2 | 커뮤니케이션 | 보안 정책 배포, 교육 기록 |
| CC3 | 리스크 평가 | 위협 모델링, 취약점 스캔 |
| CC4 | 모니터링 활동 | Prometheus/Grafana 대시보드 |
| CC5 | 통제 활동 | RBAC, NetworkPolicy, OPA |
| CC6 | 논리적/물리적 접근 | K8s RBAC, Pod Security, 암호화 |
| CC7 | 시스템 운영 | 인시던트 대응, 변경 관리 |
| CC8 | 변경 관리 | GitOps, PR 리뷰, CI/CD 파이프라인 |
| CC9 | 리스크 완화 | 벤더 관리, 보험 |

### SOC2 증거 수집 자동화

```bash
# CC6: RBAC 바인딩 감사
kubectl get clusterrolebindings -o json | \
  jq '[.items[] | {name: .metadata.name, role: .roleRef.name, subjects: .subjects}]'

# CC6: 클러스터 관리자 권한 사용자 목록
kubectl get clusterrolebindings -o json | \
  jq '[.items[] | select(.roleRef.name=="cluster-admin") | .subjects[]?]'

# CC8: 최근 배포 이력 (변경 관리 증거)
kubectl get events --field-selector reason=ScalingReplicaSet \
  --sort-by='.lastTimestamp' -A | tail -20
```

---

## HIPAA Technical Safeguards

### 기술적 보호조치 (Section 164.312)

| 항목 | 요구사항 | 구현 방법 |
|------|---------|----------|
| Access Control (a)(1) | 고유 사용자 식별 | K8s RBAC + OIDC 연동 |
| Audit Controls (b) | 활동 기록 및 검토 | K8s Audit Policy + SIEM |
| Integrity (c)(1) | PHI 무결성 보호 | etcd 암호화 + 변경 감지 |
| Transmission (e)(1) | 전송 중 암호화 | mTLS (Istio/Linkerd) + TLS 1.3 |
| Authentication (d) | 사용자/엔티티 인증 | MFA + 서비스 메시 mTLS |

### HIPAA K8s 보안 구성

```yaml
# PHI 데이터 네임스페이스 격리
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: phi-isolation
  namespace: healthcare
spec:
  podSelector:
    matchLabels:
      data-classification: phi
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              hipaa-compliant: "true"
        - podSelector:
            matchLabels:
              phi-access: authorized
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              hipaa-compliant: "true"
```

### HIPAA 감사 로깅 설정

```yaml
# K8s Audit Policy for HIPAA
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # PHI 관련 리소스 접근 전체 기록
  - level: RequestResponse
    namespaces: ["healthcare", "phi-data"]
    resources:
      - group: ""
        resources: ["secrets", "configmaps", "pods"]
    omitStages:
      - RequestReceived
  # Secret 접근 기록
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets"]
```

---

## GDPR Technical Requirements

### 핵심 원칙과 기술 구현

| GDPR 원칙 | 조항 | 기술 구현 |
|-----------|------|----------|
| 합법성/투명성 | Art. 6 | 동의 관리 시스템, 처리 목적 명시 |
| 목적 제한 | Art. 5(1)(b) | 데이터 접근 정책, 용도별 격리 |
| 데이터 최소화 | Art. 5(1)(c) | 필드 레벨 암호화, 익명화 |
| 정확성 | Art. 5(1)(d) | 데이터 검증, 수정 API |
| 보존 제한 | Art. 5(1)(e) | TTL 정책, 자동 삭제 CronJob |
| 무결성/기밀성 | Art. 5(1)(f) | 암호화, 접근 제어, 감사 로그 |

### 데이터 주체 권리 (DSAR) 구현

```
┌─────────────────────────────────────────────────┐
│              Data Subject Rights                 │
├──────────────┬──────────────────────────────────┤
│ 접근권 (Art.15)  │ GET /api/v1/gdpr/data-export  │
│ 정정권 (Art.16)  │ PATCH /api/v1/gdpr/rectify    │
│ 삭제권 (Art.17)  │ DELETE /api/v1/gdpr/erase     │
│ 이동권 (Art.20)  │ GET /api/v1/gdpr/portability  │
│ 반대권 (Art.21)  │ POST /api/v1/gdpr/object      │
│ 처리제한 (Art.18)│ POST /api/v1/gdpr/restrict    │
└──────────────┴──────────────────────────────────┘
```

### GDPR 데이터 보존 자동화

```yaml
# 보존 기간 만료 데이터 자동 삭제 CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gdpr-data-retention
  namespace: compliance
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: retention-cleanup
            image: company/gdpr-tools:latest
            command:
            - /bin/sh
            - -c
            - |
              # 보존 기간 초과 개인정보 삭제
              gdpr-cli purge --older-than 730d --data-class personal
              # 삭제 로그 기록
              gdpr-cli audit-log --action purge --timestamp $(date -u +%Y-%m-%dT%H:%M:%SZ)
          restartPolicy: OnFailure
```

---

## PCI-DSS Network Security

### 12대 요구사항 개요

```
┌──────────────────────────────────────────────────────┐
│              PCI-DSS v4.0 Requirements                │
├──────────────────────────────────────────────────────┤
│ Build & Maintain Secure Network                       │
│  1. 네트워크 보안 컨트롤 설치 및 유지                 │
│  2. 보안 구성 적용                                    │
├──────────────────────────────────────────────────────┤
│ Protect Account Data                                  │
│  3. 저장된 계정 데이터 보호                           │
│  4. 전송 중 강력한 암호화                             │
├──────────────────────────────────────────────────────┤
│ Maintain Vulnerability Management                     │
│  5. 악성 소프트웨어 방어                              │
│  6. 안전한 시스템/소프트웨어 개발                     │
├──────────────────────────────────────────────────────┤
│ Implement Strong Access Control                       │
│  7. 비즈니스 필요에 따른 접근 제한                    │
│  8. 사용자 식별 및 인증                               │
│  9. 물리적 접근 제한                                  │
├──────────────────────────────────────────────────────┤
│ Monitor & Test Networks                               │
│  10. 네트워크/리소스 접근 모니터링                    │
│  11. 보안 시스템 정기적 테스트                        │
├──────────────────────────────────────────────────────┤
│ Maintain Information Security Policy                  │
│  12. 정보 보안 정책 유지                              │
└──────────────────────────────────────────────────────┘
```

### PCI-DSS K8s 네트워크 세그멘테이션

```yaml
# CDE (Cardholder Data Environment) 격리
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cde-isolation
  namespace: payment
spec:
  podSelector:
    matchLabels:
      pci-zone: cde
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              pci-zone: cde
        - podSelector:
            matchLabels:
              pci-zone: dmz
      ports:
        - protocol: TCP
          port: 8443
  egress:
    - to:
        - podSelector:
            matchLabels:
              pci-zone: cde
      ports:
        - protocol: TCP
          port: 5432
```

---

## Kubernetes Compliance Mapping

### 공통 컨트롤 매핑 (Cross-Framework)

| 컨트롤 영역 | SOC2 | HIPAA | GDPR | PCI-DSS | K8s 구현 |
|------------|------|-------|------|---------|---------|
| 접근 제어 | CC6.1 | 164.312(a) | Art.32 | Req.7 | RBAC + OPA |
| 암호화(저장) | CC6.1 | 164.312(a)(2)(iv) | Art.32 | Req.3 | etcd encryption |
| 암호화(전송) | CC6.7 | 164.312(e)(1) | Art.32 | Req.4 | mTLS, TLS 1.2+ |
| 감사 로깅 | CC7.2 | 164.312(b) | Art.30 | Req.10 | Audit Policy |
| 네트워크 격리 | CC6.6 | 164.312(e)(1) | Art.32 | Req.1 | NetworkPolicy |
| 취약점 관리 | CC7.1 | 164.308(a)(5) | Art.32 | Req.6 | Trivy, Kyverno |
| 변경 관리 | CC8.1 | 164.312(c)(1) | Art.32 | Req.6 | GitOps, PR Review |
| 인시던트 대응 | CC7.3 | 164.308(a)(6) | Art.33 | Req.12 | PagerDuty, Runbook |

### RBAC 컴플라이언스 구성

```bash
# 네임스페이스별 RBAC 적용 확인
for ns in $(kubectl get ns -o jsonpath='{.items[*].metadata.name}'); do
  bindings=$(kubectl get rolebindings -n "$ns" -o json 2>/dev/null | jq '.items | length')
  echo "namespace=$ns rolebindings=$bindings"
done

# 과도한 권한 탐지 (wildcard 사용)
kubectl get clusterroles -o json | \
  jq '[.items[] | select(.rules[]?.resources[]? == "*" or .rules[]?.verbs[]? == "*") | .metadata.name]'
```

---

## Automated Evidence Collection

### 통합 증거 수집 스크립트

```bash
#!/bin/bash
# compliance-evidence-collector.sh
EVIDENCE_DIR="./evidence/$(date +%Y-%m-%d)"
mkdir -p "$EVIDENCE_DIR"

# 1. RBAC 구성 증거
kubectl get clusterroles,clusterrolebindings -o yaml > "$EVIDENCE_DIR/rbac-config.yaml"

# 2. NetworkPolicy 증거
kubectl get networkpolicies -A -o yaml > "$EVIDENCE_DIR/network-policies.yaml"

# 3. Pod Security 증거
kubectl get pods -A -o json | \
  jq '[.items[] | {
    namespace: .metadata.namespace,
    name: .metadata.name,
    securityContext: .spec.securityContext,
    containerSecurity: [.spec.containers[] | {
      name: .name,
      securityContext: .securityContext
    }]
  }]' > "$EVIDENCE_DIR/pod-security.json"

# 4. 암호화 상태 확인
kubectl get secrets -A --field-selector type=kubernetes.io/tls -o json | \
  jq '[.items[] | {namespace: .metadata.namespace, name: .metadata.name, created: .metadata.creationTimestamp}]' \
  > "$EVIDENCE_DIR/tls-certificates.json"

# 5. 컨테이너 이미지 목록
kubectl get pods -A -o json | \
  jq '[.items[] | {ns: .metadata.namespace, pod: .metadata.name,
       images: [.spec.containers[].image]}]' > "$EVIDENCE_DIR/container-images.json"

echo "Evidence collected in $EVIDENCE_DIR"
```

---

## Framework Comparison Matrix

| 기준 | SOC2 | HIPAA | GDPR | PCI-DSS |
|------|------|-------|------|---------|
| 적용 범위 | 서비스 전체 | PHI 처리 시스템 | EU 개인정보 처리 | 카드 데이터 환경(CDE) |
| 인증 기관 | AICPA 승인 감사인 | HHS OCR | 국가별 DPA | PCI SSC QSA |
| 인증 유형 | 의견서(Opinion) | 자체 준수 | 자체 준수 | 인증서(Certificate) |
| 갱신 주기 | 연간 | 상시 | 상시 | 연간 |
| 기술적 구체성 | 중간 (원칙 기반) | 중간 (가이드라인) | 낮음 (원칙 기반) | 높음 (구체적 요구사항) |
| 준비 기간 | 6~12개월 | 3~6개월 | 3~6개월 | 6~12개월 |
| 비용 (SMB) | $50K~$150K/년 | $10K~$50K/년 | $20K~$100K/년 | $50K~$200K/년 |

---

## Common Audit Findings

### Top 10 감사 지적 사항

| # | 지적 사항 | 프레임워크 | 심각도 | 해결 방법 |
|---|----------|-----------|-------|----------|
| 1 | 과도한 RBAC 권한 (wildcard) | SOC2/PCI | High | 최소 권한 원칙 적용 |
| 2 | 암호화되지 않은 Secret | SOC2/HIPAA/PCI | Critical | SecretStore + 외부 KMS |
| 3 | 감사 로그 미활성화 | All | High | K8s Audit Policy 설정 |
| 4 | NetworkPolicy 미적용 | PCI/HIPAA | High | 기본 Deny + 허용 목록 |
| 5 | 컨테이너 root 실행 | SOC2/PCI | Medium | Pod Security Standards |
| 6 | 이미지 취약점 미스캔 | SOC2/PCI | Medium | Trivy + Admission Controller |
| 7 | 백업/복구 미테스트 | SOC2/HIPAA | High | DR 테스트 분기별 실행 |
| 8 | 접근 리뷰 미수행 | SOC2/HIPAA | Medium | 분기별 RBAC 리뷰 자동화 |
| 9 | 인시던트 대응 절차 미비 | All | Medium | Runbook + PagerDuty |
| 10 | 데이터 보존 정책 미수립 | GDPR/HIPAA | Medium | 자동 TTL + CronJob |

---

## Remediation Patterns

### Pattern 1: Secret 관리 강화

```yaml
# External Secrets Operator로 안전한 Secret 관리
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: payment
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: production/db/password
```

### Pattern 2: Pod Security Standards 적용

```yaml
# 네임스페이스 레벨 보안 강제
apiVersion: v1
kind: Namespace
metadata:
  name: payment
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
    pci-zone: cde
    hipaa-compliant: "true"
```

### Pattern 3: 컴플라이언스 정책 자동 적용 (Kyverno)

```yaml
# Kyverno: 모든 Pod에 Security Context 강제
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-security-context
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-run-as-non-root
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "Containers must run as non-root"
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
            containers:
              - securityContext:
                  allowPrivilegeEscalation: false
```

---

## Compliance Calendar

| 주기 | 활동 | 프레임워크 |
|------|------|-----------|
| 일간 | 자동 취약점 스캔, 정책 위반 알림 | All |
| 주간 | RBAC 변경 리뷰, 신규 Secret 감사 | SOC2, HIPAA |
| 월간 | 전체 컴플라이언스 리포트 생성 | All |
| 분기 | 접근 리뷰 (Access Review) | SOC2, HIPAA, PCI |
| 반기 | 침투 테스트, DR 테스트 | PCI-DSS, SOC2 |
| 연간 | 외부 감사 (QSA/CPA), 정책 갱신 | All |

---

## Related Skills

| 스킬 | 용도 |
|------|------|
| `kubernetes/k8s-security` | K8s 보안 패턴, RBAC, Pod Security |
| `observability/logging-compliance` | PCI-DSS 로깅, 감사 로그 |
| `cicd/supply-chain-security` | SBOM, SLSA, Sigstore |
| `security/threat-modeling` | STRIDE, DREAD, 위협 모델링 |
| `infrastructure/terraform-security` | IaC 보안 구성 |
