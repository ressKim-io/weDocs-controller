# Cloud CLI Safety Rules

AI 코딩 어시스턴트가 실행해서는 안 되는 위험한 클라우드 CLI 명령 **활성화 가이드**.
상세 명령 카탈로그는 [`/cloud-cli-safety`](../skills/operations/cloud-cli-safety.md) skill 참조.

> 2026-03 기준 작성. 실제 사고 사례 기반.

---

## 기본 원칙 (MANDATORY)

- **모든 destructive operation 은 사전 승인 필수** ([`user-approval.md`](user-approval.md) §외부 작업)
- **`--force` / `--quiet` 플래그**: AI 어시스턴트 자동 추가 금지 (확인 프롬프트 생략 / 의존성 체크 우회)
- **예상 비용 사고 의무**: GPU/TPU, 대형 인스턴스, 프로비저닝 용량 급증, 무효화 과다 호출 시 사용자 고지

---

## 활성화 절차

1. 프로젝트가 사용하는 클라우드 식별 (AWS / GCP / 멀티클라우드)
2. [`/cloud-cli-safety` skill](../skills/operations/cloud-cli-safety.md) 의 해당 서비스 섹션 (예: `## AWS 위험 CLI 명령 → ### S3`) 의 `<!-- ... -->` 주석을 제거
3. 활성화한 항목을 본 rule 에 복사하거나 skill 자체 활성화로 적용
4. 실제 사고 케이스를 사용자가 추가 (`> 2026-MM-DD 사고: ...`)

---

## 위험 명령 분류 (상세는 skill)

| 클라우드 | 분류 | 주요 위험 |
|---|---|---|
| **AWS** | CloudFront / S3 / EC2 / RDS / IAM / EKS / ECS / Route 53 / KMS / DynamoDB / ElastiCache / CloudFormation / Lambda | 데이터 영구 삭제 / 권한 escalation / 다운타임 / 비용 폭증 |
| **GCP** | Project / Compute / GKE / Cloud SQL / Storage / IAM / KMS / VPC / DNS / Pub/Sub / BigQuery / Cloud Functions | 동일 카테고리 |
| **공통 위험 패턴** | Full Replace API (PUT) / `--force` `--quiet` / 과금 폭증 | 누락 필드 기본값 초기화 / 무확인 / 시간당 수십 달러 |

각 카테고리의 구체 명령은 [`.claude/skills/operations/cloud-cli-safety.md`](../skills/operations/cloud-cli-safety.md) 참조.

---

## 관련 룰

- [`user-approval.md`](user-approval.md) — 외부 작업 사전 승인
- [`security.md`](security.md) — 시크릿 / 입력 검증
- [`debugging.md`](debugging.md) — destructive operation 대신 진단 우선
