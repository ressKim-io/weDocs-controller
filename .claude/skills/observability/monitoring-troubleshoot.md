---
name: monitoring-troubleshoot
description: "Monitoring Troubleshooting Guide — 알림 대응, 역할별 가이드, 트러블슈팅 패턴 Use when working with observability 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Monitoring Troubleshooting Guide

알림 대응, 역할별 가이드, 트러블슈팅 패턴

## Quick Reference (결정 트리)

```
알림 우선순위
    │
    ├─ P1 Critical ─────> 즉시 대응 (5분 이내)
    │   └─ 서비스 다운, 에러율 > 5%
    │
    ├─ P2 Warning ──────> 업무시간 내 (4시간)
    │   └─ 에러율 > 1%, 지연 > 2초
    │
    └─ P3 Info ─────────> 일일 리뷰 (24시간)
        └─ 디스크 > 70%, 메모리 > 80%
```

---

## 역할별 모니터링 가이드

### 개발자 (Developer)

**봐야 할 skill:**
- `/observability` - 기본 로깅, 메트릭
- `/monitoring-grafana` - RED 대시보드

**주요 관심사:**
| 메트릭 | 정상 범위 | 알림 임계값 |
|--------|----------|------------|
| 에러율 | < 0.1% | > 1% |
| P95 응답시간 | < 200ms | > 500ms |
| 요청/초 | 베이스라인 ±20% | ±50% |

**주요 대시보드:** RED Dashboard
```promql
# 내 서비스 에러율
sum(rate(http_requests_total{service="$my_service",status=~"5.."}[5m]))
  / sum(rate(http_requests_total{service="$my_service"}[5m])) * 100
```

### DevOps/SRE

**봐야 할 skill:**
- `/monitoring-metrics` - Prometheus 스케일링
- `/monitoring-logs` - 로그 파이프라인
- `/monitoring-grafana` - 인프라 대시보드

**주요 관심사:**
| 메트릭 | 정상 범위 | 알림 임계값 |
|--------|----------|------------|
| CPU 사용률 | < 70% | > 85% |
| 메모리 사용률 | < 80% | > 90% |
| 디스크 사용률 | < 70% | > 85% |
| Pod 재시작 | 0 | > 3/시간 |

**주요 대시보드:** Infrastructure, SLO Dashboard

### 기획자/PM

**봐야 할 skill:**
- `/monitoring-grafana` (읽기 전용)

**주요 관심사:**
| 메트릭 | 의미 |
|--------|------|
| 가용성 (%) | 서비스 정상 시간 비율 |
| 에러 버짓 | 허용된 오류 예산 잔여량 |
| 월간 요청 수 | 서비스 사용량 |

**주요 대시보드:** Summary Dashboard (SLO 요약)

---

## CRITICAL: 알림 대응 프로세스

### P1 Critical 대응 플로우

```
알림 수신
    │
    ▼
┌─────────────────────────────────────┐
│ 1. 영향 범위 확인 (2분)              │
│    - 어떤 서비스가 영향받는가?        │
│    - 사용자 영향은?                  │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│ 2. 최근 변경 확인 (1분)              │
│    - 최근 배포가 있었나?             │
│    - 설정 변경이 있었나?             │
└─────────────────┬───────────────────┘
                  ▼
          ┌───────┴───────┐
          │ 최근 배포 있음? │
          └───────┬───────┘
          YES     │     NO
          ▼       │     ▼
      롤백 실행    │   스케일업/재시작
          │       │     │
          └───────┼─────┘
                  ▼
┌─────────────────────────────────────┐
│ 3. 상태 확인 및 에스컬레이션          │
│    - 복구 확인                       │
│    - RCA 문서 작성                   │
└─────────────────────────────────────┘
```

### 영향 범위 파악 쿼리

```promql
# 영향받는 서비스 목록
sum by (service) (
  rate(http_requests_total{status=~"5.."}[5m])
) > 0

# 영향받는 사용자 수 (추정)
count(
  count by (user_id) (
    http_requests_total{status=~"5.."}
  )
)
```

---

## 일반적인 문제 및 해결

### 높은 에러율

**증상:** 에러율 > 5%

**진단:**
```promql
# 에러 분포 확인
sum by (status, endpoint) (
  rate(http_requests_total{status=~"5.."}[5m])
)
```

**해결:**
1. 특정 엔드포인트 문제 → 해당 코드 확인
2. 전체적 문제 → 최근 배포 롤백 검토
3. 외부 의존성 → 업스트림 서비스 확인

### 높은 지연시간

**증상:** P95 > 2초

**진단:**
```promql
# 느린 엔드포인트 확인
histogram_quantile(0.95,
  sum by (endpoint, le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)
```

**해결:**
1. DB 쿼리 확인 → 슬로우 쿼리 로그
2. 외부 API 지연 → 타임아웃/서킷브레이커
3. 리소스 부족 → 스케일업

### 메모리/CPU 급증

**증상:** 리소스 > 90%

**진단:**
```promql
# 상위 메모리 사용 Pod
topk(10,
  container_memory_usage_bytes{namespace="production"}
)
```

**해결:**
1. 메모리 릭 의심 → 힙 덤프 분석
2. 트래픽 급증 → HPA 확인/수동 스케일
3. 비효율적 코드 → 프로파일링

### 디스크 부족

**증상:** 디스크 사용률 > 85%

**진단:**
```bash
# 큰 파일/디렉토리 확인
du -sh /var/log/* | sort -rh | head -10
```

**해결:**
1. 로그 정리 → logrotate 확인
2. 임시 파일 정리 → /tmp, /var/cache
3. 볼륨 확장 → PVC resize

### Healthcheck 프로토콜 문제

**증상:** 컨테이너 healthcheck 실패, `unhealthy` 상태 반복

**진단:**
```bash
# 컨테이너 healthcheck 로그 확인
docker inspect --format='{{json .State.Health}}' <container>

# 직접 healthcheck 명령 실행
docker exec <container> wget --spider -q http://localhost:3100/ready
docker exec <container> wget -qO /dev/null http://localhost:3100/ready
```

**원인 및 해결:**
| 원인 | 증상 | 해결 |
|------|------|------|
| HEAD 메서드 미지원 | `wget --spider` 실패 (405) | `wget -qO /dev/null` (GET) 사용 |
| 인증 필요 엔드포인트 | 401/403 응답 | Spring Security에서 healthcheck 경로 제외 |
| 서비스 미기동 완료 | Connection refused | `start_period` 설정 또는 `depends_on: condition` 활용 |

### ALB 타겟 헬스 검증

**증상:** 배포 후 서비스 접근 불가, ALB 502/503

**진단:**
```bash
# 타겟 그룹 헬스 확인
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>

# unhealthy 원인 확인
# - "Target.Timeout": 응답 시간 초과
# - "Target.FailedHealthChecks": healthcheck 경로/포트 문제
# - "Target.NotInService": 인스턴스 미등록
```

**일반적 원인:**
1. **포트 바인딩**: `127.0.0.1` 바인딩 → ALB 접근 불가 → `0.0.0.0` 필요
2. **Healthcheck 경로**: 인증 필요 경로 → `/actuator/health` 등 인증 제외 경로 사용
3. **Security Group**: ALB → EC2 인바운드 포트 미허용

### CD 파이프라인 대기 메커니즘

**증상:** 배포 파이프라인에서 서비스 기동 대기 중 timeout

**AWS SSM waiter:**
- 기본 timeout: ~100초 (`aws ssm send-command --timeout-seconds`)
- 대규모 Spring Boot 앱은 기동에 30-120초 소요 → 기본 waiter timeout 초과 가능

**대안: Shell polling 루프**
```bash
MAX_WAIT=300  # 최대 5분
INTERVAL=10   # 10초 간격
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  if curl -sf http://localhost:8080/actuator/health > /dev/null 2>&1; then
    echo "Service is healthy"
    exit 0
  fi
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Service failed to start within ${MAX_WAIT}s"
exit 1
```

---

## 로그 기반 디버깅

### Grafana Explore 사용

```logql
# trace_id로 전체 요청 흐름 추적
{namespace="production"}
  | json
  | trace_id="abc123def456"

# 에러와 관련 컨텍스트 (전후 5줄)
{app="order-service"} |= "error"
```

### Trace-Log 연동

```
1. Grafana에서 Trace 확인 (Tempo)
2. Span 클릭 → "View Logs" 버튼
3. 해당 trace_id의 모든 로그 확인 (Loki)
```

---

## Grafana RBAC 빠른 설정

| 역할 | Org Role | 폴더 접근 | 권한 |
|------|----------|----------|------|
| 개발자 | Viewer | /Application | 읽기 |
| DevOps | Editor | 전체 | 편집 |
| SRE | Admin | 전체 | 관리 |
| PM | Viewer | /Summary | 읽기 |

### API로 권한 설정

```bash
# 팀에 폴더 Viewer 권한 부여
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"teamId": 1, "permission": 1}
    ]
  }' \
  http://admin:admin@localhost:3000/api/folders/app/permissions
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 알림 무시 | 장애 확대 | 에스컬레이션 정책 |
| 로그 없이 디버깅 | 추측 기반 수정 | trace_id 기반 추적 |
| 롤백 주저 | 장애 시간 증가 | 빠른 롤백 원칙 |
| 혼자 대응 | 피로/실수 | 온콜 로테이션 |
| 문서화 안 함 | 같은 문제 반복 | RCA 필수 작성 |

---

## 체크리스트

### 알림 대응
- [ ] P1/P2/P3 분류 기준 숙지
- [ ] 에스컬레이션 경로 확인
- [ ] 롤백 절차 숙지

### 진단 도구
- [ ] Grafana 대시보드 접근
- [ ] 로그 쿼리 방법 숙지
- [ ] Trace 조회 방법 숙지

### 사후 처리
- [ ] RCA 템플릿 준비
- [ ] 장애 리뷰 일정 (24-48시간 내)
- [ ] 개선 항목 추적

---

## Pod 알림 설정 (PrometheusRule)

### 핵심 Pod 알림 규칙

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pod-alerts
  namespace: monitoring
spec:
  groups:
    - name: pod-alerts
      rules:
        # Pod CrashLoopBackOff
        - alert: PodCrashLooping
          expr: |
            sum(rate(kube_pod_container_status_restarts_total[15m])) by (namespace, pod) > 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} is crash looping"
            description: "Pod {{ $labels.namespace }}/{{ $labels.pod }} has restarted"

        # Pod Not Ready
        - alert: PodNotReady
          expr: |
            sum by (namespace, pod) (kube_pod_status_phase{phase!="Running",phase!="Succeeded"}) > 0
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} is not ready"

        # Container High Memory
        - alert: ContainerHighMemory
          expr: |
            (container_memory_working_set_bytes / container_spec_memory_limit_bytes) > 0.9
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Container memory usage > 90%"

        # High Error Rate (SLO)
        - alert: HighErrorRate
          expr: |
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
            / sum(rate(http_requests_total[5m])) by (service) > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Service {{ $labels.service }} error rate > 5%"
```

---

## Discord 웹훅 연동

### AlertManager 설정 (v0.25+)

```yaml
# alertmanager.yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'discord-default'
  group_by: ['alertname', 'namespace']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'discord-critical'
    - match:
        severity: warning
      receiver: 'discord-warning'

receivers:
  - name: 'discord-critical'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/yyy'
        title: '🔴 CRITICAL: {{ .CommonLabels.alertname }}'
        message: |
          **Status**: {{ .Status | toUpper }}
          **Namespace**: {{ .CommonLabels.namespace }}
          {{ range .Alerts }}
          **Description**: {{ .Annotations.description }}
          {{ end }}

  - name: 'discord-warning'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/zzz'
        title: '🟡 Warning: {{ .CommonLabels.alertname }}'
        message: |
          **Status**: {{ .Status | toUpper }}
          {{ range .Alerts }}
          **Description**: {{ .Annotations.description }}
          {{ end }}

  - name: 'discord-default'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/default/xxx'
```

### Discord 웹훅 생성 방법

```
1. Discord 서버 설정 → 연동 → 웹후크
2. 새 웹후크 만들기
3. 채널 선택 (alerts-critical, alerts-warning 등)
4. 웹후크 URL 복사 → AlertManager 설정에 사용
```

상세한 알림 설정은 `/alerting-discord` 스킬 참조

**관련 skill**: `/monitoring-grafana`, `/monitoring-metrics`, `/monitoring-logs`, `/alerting-discord`, `/sre-sli-slo`
