---
name: disaster-recovery
description: "Disaster Recovery 가이드 — DR 전략, RTO/RPO 정의, Velero 백업, 멀티 클러스터 복구 Use when working with sre 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Disaster Recovery 가이드

DR 전략, RTO/RPO 정의, Velero 백업, 멀티 클러스터 복구

## Quick Reference (결정 트리)

```
DR 전략 선택?
    │
    ├─ 비용 최소화 ─────────> Backup & Restore (Cold)
    │   └─ RTO: 시간 단위, RPO: 일 단위
    │
    ├─ 균형 잡힌 접근 ──────> Pilot Light / Warm Standby
    │   └─ RTO: 분~시간, RPO: 분 단위
    │
    └─ 무중단 요구 ─────────> Active-Active
        └─ RTO: 초~분, RPO: 0 (동기 복제)

백업 도구?
    │
    ├─ Kubernetes ─────────> Velero (CNCF)
    ├─ 데이터베이스 ───────> 네이티브 백업 + 스냅샷
    └─ 엔터프라이즈 ───────> Kasten K10
```

---

## CRITICAL: RTO/RPO 정의

```
┌─────────────────────────────────────────────────────────────┐
│                    RTO vs RPO                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│         장애 발생                                             │
│            │                                                 │
│  ◄─────────┼──────────────────────────────────────►         │
│     RPO    │              RTO                                │
│   (데이터  │           (복구 시간)                            │
│    손실)   │                                                 │
│            │                                                 │
│  마지막    │    서비스    복구     정상                       │
│  백업      │    중단      시작     운영                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘

RPO (Recovery Point Objective): 허용 가능한 최대 데이터 손실
RTO (Recovery Time Objective): 허용 가능한 최대 복구 시간
```

### 서비스별 RTO/RPO 예시

| 서비스 | RTO | RPO | DR 전략 |
|--------|-----|-----|---------|
| 결제 시스템 | 5분 | 0 | Active-Active |
| 주문 서비스 | 1시간 | 15분 | Warm Standby |
| 백오피스 | 4시간 | 1시간 | Pilot Light |
| 개발 환경 | 24시간 | 24시간 | Backup Only |

---

## DR 전략 비교

### 전략별 특성

| 전략 | RTO | RPO | 비용 | 복잡도 |
|------|-----|-----|------|--------|
| **Backup & Restore** | 시간 | 일 | 낮음 | 낮음 |
| **Pilot Light** | 분~시간 | 분 | 중간 | 중간 |
| **Warm Standby** | 분 | 초~분 | 높음 | 높음 |
| **Active-Active** | 초 | 0 | 매우 높음 | 매우 높음 |

```
┌─────────────────────────────────────────────────────────────┐
│                    DR Strategies                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Backup & Restore    Pilot Light    Warm Standby    Active  │
│  ┌─────────┐        ┌─────────┐    ┌─────────┐    ┌──────┐  │
│  │ Backup  │        │Min Infra│    │Scaled   │    │ Full │  │
│  │ Files   │        │ (DB on) │    │ Down    │    │Active│  │
│  └─────────┘        └─────────┘    └─────────┘    └──────┘  │
│                                                              │
│  비용: $           비용: $$       비용: $$$     비용: $$$$   │
│  RTO: 시간         RTO: 1시간     RTO: 분        RTO: 초     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Velero 설치 및 설정

### 설치

```bash
# Velero CLI 설치
brew install velero

# AWS S3 버킷 생성
aws s3 mb s3://my-velero-backups --region ap-northeast-2

# Velero 설치 (Helm)
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set-file credentials.secretContents.cloud=./credentials-velero \
  --set configuration.backupStorageLocation[0].name=aws \
  --set configuration.backupStorageLocation[0].provider=aws \
  --set configuration.backupStorageLocation[0].bucket=my-velero-backups \
  --set configuration.backupStorageLocation[0].config.region=ap-northeast-2 \
  --set configuration.volumeSnapshotLocation[0].name=aws \
  --set configuration.volumeSnapshotLocation[0].provider=aws \
  --set configuration.volumeSnapshotLocation[0].config.region=ap-northeast-2 \
  --set initContainers[0].name=velero-plugin-for-aws \
  --set initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0 \
  --set initContainers[0].volumeMounts[0].mountPath=/target \
  --set initContainers[0].volumeMounts[0].name=plugins
```

### IRSA 설정 (권장)

```yaml
# velero-irsa.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: velero
  namespace: velero
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/velero-backup-role
```

```hcl
# IAM Policy for Velero
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:CreateTags",
        "ec2:CreateVolume",
        "ec2:CreateSnapshot",
        "ec2:DeleteSnapshot"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": "arn:aws:s3:::my-velero-backups/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::my-velero-backups"
    }
  ]
}
```

---

## 백업 설정

### 수동 백업

```bash
# 전체 클러스터 백업
velero backup create full-backup

# 특정 네임스페이스 백업
velero backup create production-backup \
  --include-namespaces production

# 라벨 기반 백업
velero backup create app-backup \
  --selector app=my-app

# PV 포함 백업
velero backup create full-backup \
  --default-volumes-to-fs-backup
```

### 스케줄 백업

```yaml
# schedule.yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # 매일 새벽 2시
  template:
    includedNamespaces:
      - production
      - staging
    excludedResources:
      - events
      - pods
    storageLocation: aws
    volumeSnapshotLocations:
      - aws
    ttl: 720h  # 30일 보관
    defaultVolumesToFsBackup: true
---
# 더 자주 백업 (중요 서비스)
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: hourly-critical-backup
  namespace: velero
spec:
  schedule: "0 * * * *"  # 매시간
  template:
    includedNamespaces:
      - payment
    ttl: 168h  # 7일 보관
    defaultVolumesToFsBackup: true
```

### 백업 확인

```bash
# 백업 목록
velero backup get

# 백업 상세 정보
velero backup describe daily-backup-20240115020000

# 백업 로그
velero backup logs daily-backup-20240115020000
```

---

## 복구 절차

### 기본 복구

```bash
# 전체 복구
velero restore create --from-backup full-backup

# 특정 네임스페이스만 복구
velero restore create --from-backup full-backup \
  --include-namespaces production

# 기존 리소스 덮어쓰기
velero restore create --from-backup full-backup \
  --existing-resource-policy update

# 네임스페이스 매핑 (다른 네임스페이스로 복구)
velero restore create --from-backup production-backup \
  --namespace-mappings production:production-restored
```

### 복구 확인

```bash
# 복구 상태 확인
velero restore get

# 복구 상세 정보
velero restore describe <restore-name>

# 복구 로그
velero restore logs <restore-name>
```

### CRITICAL: DR 복구 절차서

```markdown
# DR 복구 절차서

## 1. 상황 파악 (5분)
- [ ] 장애 범위 확인 (리전/AZ/클러스터)
- [ ] 영향받는 서비스 식별
- [ ] DR 발동 승인 획득

## 2. DR 환경 준비 (10분)
- [ ] DR 클러스터 상태 확인
- [ ] 네트워크 연결 확인
- [ ] 스토리지 접근 확인

## 3. 데이터 복구 (15-30분)
- [ ] 최신 백업 확인: velero backup get
- [ ] 복구 실행: velero restore create --from-backup <backup>
- [ ] 복구 상태 모니터링: velero restore get

## 4. 서비스 검증 (10분)
- [ ] Pod 상태 확인: kubectl get pods -A
- [ ] 헬스 체크 확인
- [ ] 핵심 기능 테스트

## 5. 트래픽 전환 (5분)
- [ ] DNS 전환 또는 Load Balancer 설정
- [ ] 트래픽 확인

## 6. 모니터링 (지속)
- [ ] 에러율 모니터링
- [ ] 성능 모니터링
- [ ] 알림 설정

## 7. 사후 처리
- [ ] 인시던트 보고서 작성
- [ ] 원인 분석
- [ ] 개선 사항 도출
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 백업 테스트 안함 | 복구 실패 | 정기 복구 테스트 |
| 동일 리전에 백업 | 리전 장애 시 손실 | 교차 리전 복제 |
| RTO/RPO 미정의 | 복구 우선순위 혼란 | 서비스별 정의 |
| 수동 백업만 | 백업 누락 | 스케줄 백업 |
| DB 백업 누락 | 데이터 손실 | 별도 DB 백업 |

---

## 체크리스트

- [ ] Velero 설치 및 IRSA 설정
- [ ] 스케줄 백업 설정 (daily/hourly)
- [ ] 백업 보관 정책 (TTL) 설정
- [ ] 서비스별 RTO/RPO 정의
- [ ] DR 전략 선택 (비용 vs 복구 시간)
- [ ] 복구 절차서 작성
- [ ] 월간 복구 테스트

---

## 참조 스킬

- `/disaster-recovery-advanced` - 멀티 클러스터 DR, 데이터베이스 DR, 테스트
- `/sre-sli-slo` - SLI/SLO 기반 가용성 목표
- `/aws-eks` - EKS 클러스터 설정
- `/k8s-helm` - Helm 차트 관리
