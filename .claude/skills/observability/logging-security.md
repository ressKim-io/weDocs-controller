---
name: logging-security
description: "Security & Bot Detection Logging — 보안 감사, 봇/매크로 탐지, AI 공격 방어를 위한 로그 패턴 Use when working with observability 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Security & Bot Detection Logging

보안 감사, 봇/매크로 탐지, AI 공격 방어를 위한 로그 패턴

## Quick Reference (결정 트리)
```
보안 로그 종류
    ├─ 인증/인가 ─────> 로그인, 권한 변경, 세션
    ├─ 봇/매크로 탐지 ─> 행동 분석, 패턴 매칭
    ├─ AI 공격/방어 ──> ML 탐지 결과, 공격 시도
    └─ 감사 로그 ─────> SIEM 연동, 이상 탐지
```

---

## CRITICAL: 티켓 예매 봇/매크로 탐지

### 매크로 탐지 지표
```
실제 탐지 사례 (예스24 도입 결과)
─────────────────────────────────
- 총 트래픽 2억 건 중 21% (4,300만 건) 매크로 탐지
- 해외 IP 매크로: 전체의 84.6%
- 연속 조회 패턴: 하루 평균 1만 건 차단 (코레일)
```

### 봇 탐지 로그 스키마
```json
{
  "log_type": "bot_detection",
  "timestamp": "2026-01-24T10:30:00.123Z",
  "request_id": "req-abc123",

  "client": {
    "ip": "203.0.113.45",
    "user_agent": "Mozilla/5.0...",
    "device_fingerprint": "fp-xyz789",
    "geo": {
      "country": "US",
      "is_proxy": true,
      "is_datacenter": true
    }
  },

  "behavior": {
    "requests_per_second": 15.2,
    "time_between_clicks_ms": 50,
    "mouse_movement": false,
    "keyboard_timing_variance": 0.01,
    "captcha_solve_time_ms": 800
  },

  "detection": {
    "is_bot": true,
    "confidence": 0.95,
    "signals": [
      "high_request_rate",
      "datacenter_ip",
      "no_mouse_movement",
      "uniform_timing"
    ],
    "model_version": "bot-detect-v3.2"
  },

  "action_taken": "challenge_captcha"
}
```

---

## 봇 탐지 신호 (Detection Signals)

### 네트워크 레벨
```json
{
  "network_signals": {
    "ip_reputation": {
      "is_proxy": true,
      "is_vpn": true,
      "is_tor": false,
      "is_datacenter": true,
      "abuse_score": 85
    },
    "geo_anomaly": {
      "country_mismatch": true,
      "impossible_travel": true
    },
    "connection": {
      "tls_fingerprint": "ja3-abc123",
      "http2_fingerprint": "akamai-h2",
      "is_headless_browser": true
    }
  }
}
```

### 행동 분석 레벨
```json
{
  "behavior_signals": {
    "timing": {
      "click_interval_ms": 50,
      "typing_speed_cpm": 2000,
      "timing_variance": 0.01
    },
    "mouse": {
      "has_movement": false,
      "movement_pattern": "linear",
      "hover_before_click": false
    },
    "session": {
      "pages_per_minute": 120,
      "form_fill_time_ms": 200,
      "scroll_behavior": "instant"
    }
  }
}
```

### 비즈니스 로직 레벨
```json
{
  "business_signals": {
    "ticket_behavior": {
      "search_to_purchase_ratio": 500,
      "concurrent_sessions": 15,
      "same_event_attempts": 50,
      "purchase_timing": "instant_after_open"
    },
    "account_pattern": {
      "new_account_age_hours": 2,
      "bulk_registration": true,
      "similar_email_pattern": true
    }
  }
}
```

---

## AI 공격/방어 로그

### AI 매크로 공격 탐지
```json
{
  "log_type": "ai_attack_detection",
  "timestamp": "2026-01-24T10:30:00Z",

  "attack": {
    "type": "ai_enhanced_bot",
    "characteristics": {
      "human_like_timing": true,
      "captcha_solve_method": "ai_vision",
      "behavioral_mimicry": true,
      "adaptive_retry": true
    }
  },

  "defense_response": {
    "challenge_type": "invisible_recaptcha_v3",
    "score": 0.3,
    "fallback": "interactive_challenge",
    "result": "blocked"
  },

  "ml_analysis": {
    "model": "anti-bot-ai-v2",
    "prediction": "malicious",
    "confidence": 0.92,
    "features_triggered": [
      "session_fingerprint_anomaly",
      "request_pattern_ml_score"
    ]
  }
}
```

### 방어 매크로 (테스트용) 로그
```json
{
  "log_type": "defense_bot_test",
  "timestamp": "2026-01-24T10:30:00Z",
  "test_id": "test-20260124-001",

  "attack_simulation": {
    "type": "ai_macro",
    "target": "ticket_reservation",
    "requests_sent": 1000,
    "success_rate": 0.02
  },

  "defense_evaluation": {
    "detection_rate": 0.98,
    "false_positive_rate": 0.001,
    "avg_response_time_ms": 15,
    "blocked_requests": 980
  },

  "model_feedback": {
    "new_patterns_detected": 3,
    "model_update_required": true
  }
}
```

---

## 인증/인가 보안 로그

### 로그인 이벤트
```json
{
  "log_type": "auth",
  "timestamp": "2026-01-24T10:30:00Z",
  "event": "login_attempt",

  "user": {
    "user_id": "USR-12345",
    "username": "user@example.com"
  },

  "auth_detail": {
    "method": "password",
    "mfa_used": true,
    "mfa_type": "totp"
  },

  "result": {
    "success": true,
    "failure_reason": null,
    "account_locked": false,
    "consecutive_failures": 0
  },

  "context": {
    "ip": "203.0.113.45",
    "device_fingerprint": "fp-abc123",
    "user_agent": "Mozilla/5.0...",
    "geo": "KR"
  },

  "risk_score": 15
}
```

### 권한 변경 이벤트
```json
{
  "log_type": "authorization",
  "timestamp": "2026-01-24T10:30:00Z",
  "event": "permission_change",

  "actor": {
    "user_id": "ADMIN-001",
    "role": "system_admin"
  },

  "target": {
    "user_id": "USR-12345",
    "previous_role": "user",
    "new_role": "vip_user"
  },

  "change_detail": {
    "permissions_added": ["early_access", "priority_queue"],
    "permissions_removed": []
  }
}
```

---

## SIEM 연동

### 로그 포맷 (CEF - Common Event Format)
```
CEF:0|TicketSystem|BotDetector|1.0|BOT_DETECTED|Bot Detection Alert|8|
  src=203.0.113.45
  dst=ticket-api.example.com
  request=/api/v1/tickets/reserve
  outcome=blocked
  reason=high_request_rate
  confidence=0.95
  cs1Label=device_fingerprint cs1=fp-xyz789
  cs2Label=detection_model cs2=bot-detect-v3.2
```

### Elasticsearch 인덱스 매핑
```json
{
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "log_type": { "type": "keyword" },
      "client.ip": { "type": "ip" },
      "client.geo.country": { "type": "keyword" },
      "detection.is_bot": { "type": "boolean" },
      "detection.confidence": { "type": "float" },
      "detection.signals": { "type": "keyword" },
      "behavior.requests_per_second": { "type": "float" }
    }
  }
}
```

### 알림 규칙
```yaml
# Elasticsearch Watcher / OpenSearch Alert
trigger:
  schedule:
    interval: "1m"
condition:
  compare:
    ctx.payload.hits.total: { gt: 100 }
input:
  search:
    request:
      indices: ["security-logs-*"]
      body:
        query:
          bool:
            must:
              - range: { "@timestamp": { gte: "now-1m" } }
              - term: { "detection.is_bot": true }
              - range: { "detection.confidence": { gte: 0.9 } }
actions:
  slack_alert:
    webhook:
      url: "${SLACK_WEBHOOK}"
      body: "🚨 고신뢰도 봇 공격 탐지: {{ctx.payload.hits.total}}건/분"
```

---

## 실시간 대시보드 쿼리

### 봇 탐지 현황 (Grafana)
```promql
# 분당 봇 탐지 수
sum(rate(bot_detection_total{is_bot="true"}[5m])) by (signal)

# 봇 탐지율
sum(rate(bot_detection_total{is_bot="true"}[5m]))
  / sum(rate(http_requests_total[5m])) * 100

# 국가별 봇 비율
topk(10, sum(rate(bot_detection_total{is_bot="true"}[1h])) by (country))
```

### 로그인 이상 탐지
```promql
# 실패율
sum(rate(login_attempts_total{success="false"}[5m]))
  / sum(rate(login_attempts_total[5m])) * 100 > 10

# 동일 IP 다중 실패
sum by (ip) (
  increase(login_attempts_total{success="false"}[5m])
) > 5
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| IP만으로 차단 | VPN/프록시 우회 | 다중 신호 조합 |
| 고정 규칙만 사용 | AI 봇 우회 | ML 기반 탐지 병행 |
| 실시간 차단만 | 학습 불가 | 로그 저장 + 분석 |
| 과도한 차단 | 정상 사용자 이탈 | 신뢰도 기반 단계적 대응 |
| CAPTCHA만 의존 | AI가 풀 수 있음 | 행동 분석 병행 |

---

## 체크리스트

### 봇 탐지
- [ ] 네트워크 신호 수집 (IP, TLS 핑거프린트)
- [ ] 행동 분석 구현 (마우스, 타이밍)
- [ ] ML 모델 연동
- [ ] 단계적 대응 (challenge → block)

### 보안 로그
- [ ] 인증 이벤트 로깅
- [ ] 권한 변경 추적
- [ ] SIEM 연동

### 모니터링
- [ ] 실시간 대시보드
- [ ] 알림 규칙 설정
- [ ] 정기 분석 리포트

**관련 skill**: `/logging-compliance`, `/monitoring-grafana`

---

## 참고 자료
- [HUMAN Security - Bot Detection](https://www.humansecurity.com/platform/solutions/bot-detection-mitigation/)
- [Cloudflare Bot Management](https://www.cloudflare.com/application-services/products/bot-management/)
- [예스24 매크로 차단 솔루션 도입 사례](https://www.e-science.co.kr/news/articleView.html?idxno=105899)
