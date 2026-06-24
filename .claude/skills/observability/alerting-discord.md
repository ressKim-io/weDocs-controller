---
name: alerting-discord
description: "Alerting & Discord 가이드 — Prometheus AlertManager 설정 및 Discord 웹훅 연동 Use when working with observability 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Alerting & Discord 가이드

Prometheus AlertManager 설정 및 Discord 웹훅 연동

## Quick Reference (결정 트리)

```
알림 채널 선택?
    │
    ├─ 긴급 (Critical) ────> PagerDuty / Opsgenie + Discord
    ├─ 경고 (Warning) ─────> Discord / Slack
    └─ 정보 (Info) ────────> Discord (별도 채널)

알림 설정 방식?
    │
    ├─ Prometheus Stack ──> AlertManager (기본)
    ├─ Grafana ───────────> Grafana Alerting
    └─ 클라우드 ──────────> CloudWatch / Azure Monitor
```

---

## CRITICAL: AlertManager 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    AlertManager Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Prometheus ──(alert rules)──> AlertManager                  │
│                                      │                       │
│                               ┌──────┴──────┐                │
│                               │             │                │
│                          Grouping      Routing               │
│                               │             │                │
│                          Inhibition    Silencing             │
│                               │             │                │
│                               └──────┬──────┘                │
│                                      │                       │
│                              ┌───────┼───────┐               │
│                              │       │       │               │
│                          Discord  Slack  PagerDuty           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 개념

| 개념 | 설명 |
|------|------|
| **Grouping** | 유사 알림 그룹화 (노이즈 감소) |
| **Routing** | 조건에 따른 알림 전송 경로 |
| **Inhibition** | 특정 알림이 다른 알림 억제 |
| **Silencing** | 일시적 알림 음소거 |

---

## AlertManager 설정

### 기본 설정 (alertmanager.yaml)

```yaml
global:
  resolve_timeout: 5m
  # SMTP 설정 (이메일)
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'alertmanager@example.com'
  smtp_auth_password: 'password'

# 라우팅 규칙
route:
  # 기본 수신자
  receiver: 'discord-warning'
  # 그룹화 기준
  group_by: ['alertname', 'namespace', 'severity']
  # 그룹 대기 시간
  group_wait: 30s
  # 그룹 재전송 간격
  group_interval: 5m
  # 반복 전송 간격
  repeat_interval: 4h

  # 하위 라우트
  routes:
    # Critical 알림 → PagerDuty + Discord
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true  # 다음 라우트도 적용

    - match:
        severity: critical
      receiver: 'discord-critical'

    # Warning 알림 → Discord
    - match:
        severity: warning
      receiver: 'discord-warning'

    # 특정 팀 알림
    - match:
        team: backend
      receiver: 'discord-backend'

    - match:
        team: infra
      receiver: 'discord-infra'

# 알림 억제 규칙
inhibit_rules:
  # Critical이 있으면 같은 alertname의 Warning 억제
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'namespace']

# 수신자 정의
receivers:
  - name: 'discord-critical'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/yyy'
        title: '🔴 CRITICAL Alert'
        message: |
          **{{ .Status | toUpper }}**: {{ .CommonAnnotations.summary }}
          {{ range .Alerts }}
          *Alert:* {{ .Labels.alertname }}
          *Namespace:* {{ .Labels.namespace }}
          *Description:* {{ .Annotations.description }}
          {{ end }}

  - name: 'discord-warning'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/zzz'
        title: '🟡 Warning Alert'
        message: |
          **{{ .Status | toUpper }}**: {{ .CommonAnnotations.summary }}
          {{ range .Alerts }}
          *Alert:* {{ .Labels.alertname }}
          *Description:* {{ .Annotations.description }}
          {{ end }}

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: 'your-pagerduty-service-key'
        severity: critical

  - name: 'discord-backend'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/backend/xxx'

  - name: 'discord-infra'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/infra/xxx'
```

---

## Discord 웹훅 설정

### 웹훅 생성

```
1. Discord 서버 설정 → 연동 → 웹후크
2. 새 웹후크 만들기
3. 채널 선택 (alerts-critical, alerts-warning 등)
4. 웹후크 URL 복사
```

### AlertManager 0.25+ 네이티브 Discord

```yaml
# alertmanager.yaml (v0.25+)
receivers:
  - name: 'discord'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/yyy'
        title: '{{ template "discord.title" . }}'
        message: '{{ template "discord.message" . }}'
```

### 커스텀 템플릿

```yaml
# alertmanager-templates.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-templates
  namespace: monitoring
data:
  discord.tmpl: |
    {{ define "discord.title" }}
    {{ if eq .Status "firing" }}🔥{{ else }}✅{{ end }} {{ .CommonLabels.alertname }}
    {{ end }}

    {{ define "discord.message" }}
    **Status**: {{ .Status | toUpper }}
    **Severity**: {{ .CommonLabels.severity }}
    {{ if .CommonAnnotations.summary }}
    **Summary**: {{ .CommonAnnotations.summary }}
    {{ end }}

    {{ range .Alerts }}
    ---
    **Alert**: {{ .Labels.alertname }}
    **Namespace**: {{ .Labels.namespace | default "N/A" }}
    **Pod**: {{ .Labels.pod | default "N/A" }}
    {{ if .Annotations.description }}
    **Description**: {{ .Annotations.description }}
    {{ end }}
    {{ if .Annotations.runbook_url }}
    **Runbook**: {{ .Annotations.runbook_url }}
    {{ end }}
    {{ end }}
    {{ end }}
```

---

## Prometheus Alert Rules (참조)

기본 알림 규칙(PodCrashLooping, NodeNotReady, HighErrorRate 등)은 아래 skill에 상세 정의:
- `/monitoring-troubleshoot` — Pod/Node 알림 규칙 + 진단 가이드
- `/kube-prometheus-stack` — kube-prometheus-stack 기본 제공 규칙
- `/observability-incident-playbook` — 알림 기반 인시던트 대응 워크플로우

### 커스텀 규칙 작성 요점

```yaml
# PrometheusRule 작성 시 필수 체크
spec:
  groups:
    - name: my-rules
      rules:
        - alert: MyAlert
          expr: <PromQL>
          for: 5m                    # MUST: 플래핑 방지
          labels:
            severity: warning        # MUST: critical/warning/info
            team: backend            # 팀 라우팅용
          annotations:
            summary: "설명"
            runbook_url: "링크"      # MUST: 대응 가이드
```

---

## 알림 라우팅 예시

### 팀별 라우팅

```yaml
route:
  receiver: 'default-discord'
  routes:
    # Backend 팀
    - match:
        team: backend
      receiver: 'discord-backend'
      routes:
        - match:
            severity: critical
          receiver: 'pagerduty-backend'
          continue: true

    # Infra 팀
    - match:
        team: infra
      receiver: 'discord-infra'
      routes:
        - match:
            severity: critical
          receiver: 'pagerduty-infra'

    # 특정 서비스
    - match:
        service: payment
      receiver: 'discord-payment-critical'
```

### 시간대별 라우팅

```yaml
route:
  receiver: 'discord-default'
  routes:
    # 업무 시간 (09-18시)
    - match:
        severity: critical
      active_time_intervals:
        - business-hours
      receiver: 'slack-critical'

    # 업무 외 시간
    - match:
        severity: critical
      active_time_intervals:
        - off-hours
      receiver: 'pagerduty-critical'

time_intervals:
  - name: business-hours
    time_intervals:
      - weekdays: ['monday:friday']
        times:
          - start_time: '09:00'
            end_time: '18:00'
  - name: off-hours
    time_intervals:
      - weekdays: ['monday:friday']
        times:
          - start_time: '00:00'
            end_time: '09:00'
          - start_time: '18:00'
            end_time: '24:00'
      - weekdays: ['saturday', 'sunday']
```

---

## Silencing (알림 음소거)

### CLI로 Silence 생성

```bash
# amtool로 silence 생성
amtool silence add alertname=PodCrashLooping namespace=staging \
  --comment="Staging maintenance" \
  --author="admin" \
  --duration=2h

# Silence 목록
amtool silence query

# Silence 해제
amtool silence expire <silence-id>
```

### API로 Silence 생성

```bash
curl -X POST http://alertmanager:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "PodCrashLooping", "isRegex": false},
      {"name": "namespace", "value": "staging", "isRegex": false}
    ],
    "startsAt": "2024-01-15T10:00:00Z",
    "endsAt": "2024-01-15T12:00:00Z",
    "createdBy": "admin",
    "comment": "Staging maintenance"
  }'
```

---

## 모니터링

### AlertManager 메트릭

```promql
# 발송된 알림 수
sum(alertmanager_notifications_total) by (integration)

# 알림 발송 실패
sum(alertmanager_notifications_failed_total) by (integration)

# 활성 알림 수
alertmanager_alerts{state="active"}

# Silenced 알림 수
alertmanager_silences{state="active"}
```

### Grafana 대시보드

```json
{
  "panels": [
    {
      "title": "Active Alerts by Severity",
      "targets": [{
        "expr": "sum(ALERTS{alertstate=\"firing\"}) by (severity)",
        "legendFormat": "{{severity}}"
      }]
    },
    {
      "title": "Notifications Sent",
      "targets": [{
        "expr": "rate(alertmanager_notifications_total[1h])",
        "legendFormat": "{{integration}}"
      }]
    }
  ]
}
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 모든 알림 Critical | 알림 피로 | severity 적절히 구분 |
| group_wait 너무 짧음 | 알림 폭탄 | 30초 이상 권장 |
| runbook 없음 | 대응 지연 | 알림마다 runbook 링크 |
| 테스트 없이 적용 | 알림 누락 | 스테이징 테스트 |
| 단일 채널만 사용 | 노이즈 | 심각도별 채널 분리 |

---

## 체크리스트

### AlertManager
- [ ] 기본 설정 (group_wait, group_interval)
- [ ] 라우팅 규칙 (severity, team)
- [ ] 수신자 설정 (Discord, Slack, PagerDuty)
- [ ] 억제 규칙 (inhibit_rules)

### Alert Rules
- [ ] 핵심 메트릭 알림 (Pod, Node, SLO)
- [ ] 적절한 severity 지정
- [ ] runbook_url 포함
- [ ] for 절로 플래핑 방지

### Discord
- [ ] 채널 분리 (critical, warning, info)
- [ ] 웹훅 설정
- [ ] 커스텀 템플릿 적용

### 운영
- [ ] Silence 절차 문서화
- [ ] 알림 대시보드 구성
- [ ] 정기 알림 리뷰

**관련 skill**: `/sre-sli-slo`, `/monitoring-metrics`, `/monitoring-troubleshoot`
