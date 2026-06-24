---
paths:
  - "**/*.tf"
  - "**/*.tfvars"
---

# Terraform Rules

Terraform 코드 작성/수정 시 반드시 준수.
실전 운영 사고 기록 + 보안 검증에서 추출.

---

## Security Group

- NEVER inline `ingress`/`egress` 블록과 별도 `aws_security_group_rule` 리소스 동시 사용
  - Terraform이 동일 규칙을 두 곳에서 관리 → plan 시 perpetual diff, apply 시 규칙 삭제
  - 근거: 2026-04-01 SG 규칙 삭제로 RDS 접근 불가 사고
- PREFER `aws_vpc_security_group_ingress_rule` / `aws_vpc_security_group_egress_rule` 사용 (신규 리소스)
- 기존 inline → separate 마이그레이션 시: inline에 `ingress = []`, `egress = []` 설정 후 separate 생성

---

## VPC / Networking

### ENI Prefix Delegation IP 계산
- VPC CIDR 계획 시 prefix delegation IP 소모량 반드시 계산:
  ```
  Max Pods = (ENIs × ((IPs_per_ENI - 1) × 16)) + 2
  실제 IP 소모 = Nodes × ENIs_per_Node × 16 (per /28 prefix)
  ```
- `/24` 서브넷(256 IPs)으로 18+ 노드 운영 불가 — prefix delegation 시 노드당 48~80 IP 소모
- PREFER `/20` 이상 서브넷 (4,096 IPs)
- 근거: 2026-04-01 IP 고갈 → 신규 Pod 스케줄링 불가, 노드 조인 실패

### WARM_IP_TARGET vs WARM_PREFIX_TARGET
- 정상 운영: `WARM_PREFIX_TARGET=1` (권장, 빠른 할당)
- IP 절약 모드: `WARM_IP_TARGET=2` (WARM_PREFIX_TARGET 제거 필수 — 동시 설정 시 IP_TARGET이 우선)

---

## EKS

### 필수 IAM Policy
- MUST 클러스터 IAM Role에 다음 정책 확인:
  - `AmazonEKSClusterPolicy`
  - `AmazonEKSVPCResourceController`
- 근거: 2026-04-07 노드 조인 401 Unauthorized (정책 누락)

### Bottlerocket user_data
- TOML 형식 필수. `max-pods` 오버라이드:
  ```toml
  [settings.kubernetes]
  max-pods = 110
  ```
- Prefix delegation 활성화 시 Bottlerocket 기본 `max-pods=35` (secondary IP 모드) → 반드시 오버라이드
- 근거: 2026-04-01 max-pods=35 고정으로 ENI secondary IP 미할당

---

## 리소스 보호

### prevent_destroy
- MUST critical 리소스에 `lifecycle { prevent_destroy = true }` 설정:
  - RDS 인스턴스/클러스터
  - S3 버킷 (데이터 저장용)
  - KMS Key
  - Route53 Hosted Zone
- AWS 레벨 보호 병행:
  - RDS: `deletion_protection = true`, `skip_final_snapshot = false`
  - S3: bucket versioning 활성화

---

## State 보안

- Terraform state 파일에는 **모든 리소스 속성이 평문 저장** (`sensitive = true` 포함)
- MUST 원격 backend + 암호화:
  ```hcl
  backend "s3" {
    bucket         = "terraform-state"
    encrypt        = true
    kms_key_id     = "alias/terraform"
    dynamodb_table = "terraform-locks"
  }
  ```
- MUST `.gitignore`에 포함: `*.tfstate`, `*.tfstate.backup`, `*.tfvars` (시크릿 포함 시)
- State 접근 IAM: 최소 권한 (terraform-admin role만)
- NEVER `terraform state pull` 출력을 로그/채팅에 공유 (시크릿 노출)

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| SG inline + separate rule 혼용 | 규칙 충돌/삭제 |
| `/24` 서브넷에 prefix delegation | IP 고갈 |
| Bottlerocket max-pods 미설정 | 35 고정 → 실질적 Pod 배치 불가 |
| critical 리소스 `prevent_destroy` 미설정 | 실수로 삭제 |
| State 파일 Git 커밋 | 시크릿 평문 노출 |
| EKS IAM Role 정책 누락 | 노드 조인 실패 |
