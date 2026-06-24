---
name: dx-ai-agents-orchestration
description: "AI Agent 오케스트레이션 가이드 — 멀티 에이전트 협업, 가드레일, Self-Healing 인프라, 메트릭 수집 Use when working with dx 도메인의 패턴 / 구현 선택."
effort: low
deprecated: false
---

# AI Agent 오케스트레이션 가이드

멀티 에이전트 협업, 가드레일, Self-Healing 인프라, 메트릭 수집

## AI Agent 오케스트레이션

### Conductor vs Orchestrator 모드 (2026)

| 특성 | Conductor 모드 | Orchestrator 모드 |
|------|-------------|-----------------|
| Agent 수 | 1개 | 다수 (병렬) |
| 실행 방식 | 동기, 순차 | 비동기, 병렬 |
| Context | 공유 context | 각자 독립 context window |
| 인간 개입 | 매 응답 검토 | 전략적 체크포인트만 |
| 적합 | 단일 작업, 탐색 | 대규모 기능, cross-module |

### 멀티 에이전트 협업 패턴

```
+------------------------------------------------------------------+
|                  Multi-Agent Orchestration                         |
+------------------------------------------------------------------+
|                                                                    |
|  ┌─────────────────────────────────────────────────────────────┐  |
|  │                    Orchestrator Agent                        │  |
|  │  - 작업 분해 및 할당                                         │  |
|  │  - 결과 통합                                                 │  |
|  │  - 품질 검증                                                 │  |
|  └─────────────────────────────────────────────────────────────┘  |
|                               │                                    |
|          ┌────────────────────┼────────────────────┐              |
|          │                    │                    │              |
|          ▼                    ▼                    ▼              |
|  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        |
|  │ Code Agent   │    │ Test Agent   │    │ Review Agent │        |
|  │ - 코드 생성  │    │ - 테스트 작성│    │ - 코드 리뷰  │        |
|  │ - 리팩토링   │    │ - 테스트 실행│    │ - 보안 검사  │        |
|  └──────────────┘    └──────────────┘    └──────────────┘        |
|          │                    │                    │              |
|          └────────────────────┼────────────────────┘              |
|                               ▼                                    |
|  ┌─────────────────────────────────────────────────────────────┐  |
|  │                    Human Review Gate                         │  |
|  │  - 최종 승인/거부                                            │  |
|  │  - 피드백 제공                                               │  |
|  └─────────────────────────────────────────────────────────────┘  |
|                                                                    |
+------------------------------------------------------------------+
```

### 루프 방지 & 안전장치

```yaml
constraints:
  maxIterations: 8              # 반복 제한 (필수)
  reflectionBeforeRetry: true   # 재시도 전 "왜 실패했나" 반성
  timeoutMinutes: 30            # 시간 제한
  escalateOnStuck: true         # 막히면 인간 에스컬레이션
```

### Model Routing (비용/성능 최적화)

| 작업 | 모델 계층 | 비용 |
|------|---------|------|
| 포맷팅, 린트 수정 | Economy (Haiku) | $ |
| 테스트 생성, 코드 작성 | Standard (Sonnet) | $$ |
| 아키텍처, 복잡 디버깅 | Frontier (Opus) | $$$$ |

### 실전 사례 (2026)

- **TELUS**: 30% 속도↑, 50만 시간 절약, 13,000+ AI 솔루션
- **Zapier**: 89% AI 채택, 800+ agent 배포
- **Rakuten**: 1250만줄 코드, 7시간 자율 실행
- **Gartner**: multi-agent 조회 1,445% 급증 (2024→2025)

### 오케스트레이션 구현

```yaml
# ai-orchestrator-config.yaml
apiVersion: platform.company.io/v1
kind: AIOrchestrator
metadata:
  name: development-orchestrator
spec:
  # 에이전트 정의
  agents:
    - name: code-agent
      type: code-generation
      model: claude-opus-4-7
      capabilities:
        - code_generation
        - refactoring
        - bug_fix
      constraints:
        maxTokensPerRequest: 100000
        maxFilesModified: 10

    - name: test-agent
      type: test-generation
      model: claude-sonnet-4-6
      capabilities:
        - unit_test_generation
        - integration_test
        - test_execution
      constraints:
        maxTestFiles: 20
        timeout: 300s

    - name: review-agent
      type: code-review
      model: claude-opus-4-7
      capabilities:
        - security_review
        - performance_review
        - style_check
      constraints:
        reviewDepth: thorough

  # 워크플로우 정의
  workflows:
    feature-development:
      steps:
        - agent: code-agent
          action: generate_code
          input: ${{ issue.description }}
          output: code_changes

        - agent: test-agent
          action: generate_tests
          input: ${{ steps.code_changes }}
          output: test_files

        - agent: test-agent
          action: run_tests
          input: ${{ steps.test_files }}
          continueOnError: false

        - agent: review-agent
          action: review
          input: ${{ steps.code_changes }}
          output: review_comments

        - gate: human-approval
          condition: ${{ steps.review_comments.severity == 'high' }}
          timeout: 24h
          fallback: reject

  # 가드레일
  guardrails:
    - name: no-secrets
      check: "!contains(output, 'API_KEY') && !contains(output, 'SECRET')"
      action: reject

    - name: max-changes
      check: "changedFiles.length <= 20"
      action: require-approval

    - name: critical-files
      check: "!modifies(['**/security/**', '**/auth/**'])"
      action: require-senior-review
```

### 가드레일 상세 설정

```yaml
# ai-guardrails.yaml
apiVersion: platform.company.io/v1
kind: AIGuardrails
metadata:
  name: enterprise-guardrails
spec:
  # 입력 검증
  inputValidation:
    - name: prompt-injection-check
      type: regex
      patterns:
        - "ignore.*previous.*instructions"
        - "system.*prompt"
        - "jailbreak"
      action: block

    - name: pii-filter
      type: ml-classifier
      model: pii-detector
      threshold: 0.8
      action: mask

  # 출력 검증
  outputValidation:
    - name: secret-detection
      type: pattern
      patterns:
        - "\\bAKIA[0-9A-Z]{16}\\b"  # AWS Access Key
        - "\\b[A-Za-z0-9+/]{40}\\b"  # Generic secret
      action: redact

    - name: code-quality
      type: linter
      tools:
        - eslint
        - pylint
      minScore: 7.0
      action: warn

    - name: security-scan
      type: sast
      tools:
        - semgrep
        - bandit
      severity: high
      action: block

  # 행동 제한
  behaviorLimits:
    maxOutputTokens: 50000
    maxFileCreations: 5
    maxFileModifications: 15
    forbiddenOperations:
      - delete_branch
      - force_push
      - modify_workflow

  # 승인 게이트
  approvalGates:
    - name: production-changes
      trigger:
        paths:
          - "k8s/production/**"
          - "**/Dockerfile"
          - ".github/workflows/**"
      approvers:
        - team: platform
          minCount: 1
        - team: security
          minCount: 1
          conditions:
            - modifies("**/security/**")

    - name: database-changes
      trigger:
        paths:
          - "**/migrations/**"
          - "**/schema/**"
      approvers:
        - team: dba
          minCount: 1
```

### Self-Healing 인프라

```yaml
# ai-self-healing.yaml
apiVersion: platform.company.io/v1
kind: AISelfHealing
metadata:
  name: infrastructure-healer
spec:
  # 모니터링 연동
  monitoring:
    prometheus:
      url: http://prometheus:9090
    alertmanager:
      url: http://alertmanager:9093

  # 자동 복구 규칙
  healingRules:
    - name: pod-crash-loop
      trigger:
        alert: KubePodCrashLooping
        duration: 5m
      actions:
        - type: analyze
          agent: diagnostics-agent
          input: "${{ alert.labels }}"

        - type: remediate
          agent: remediation-agent
          options:
            - restart_pod
            - scale_replicas
            - rollback_deployment
          requireApproval: false
          maxAttempts: 3

    - name: high-error-rate
      trigger:
        alert: HighErrorRate
        threshold: "error_rate > 0.05"
      actions:
        - type: analyze
          agent: root-cause-agent

        - type: remediate
          agent: traffic-agent
          options:
            - shift_traffic
            - enable_circuit_breaker
          requireApproval: true
          approvalTimeout: 5m

    - name: resource-exhaustion
      trigger:
        alert: HighMemoryUsage
        threshold: "memory_usage > 0.9"
      actions:
        - type: scale
          direction: up
          increment: 2
          maxReplicas: 10

        - type: notify
          channel: "#platform-alerts"
          message: "Auto-scaled due to memory pressure"

  # 학습 및 개선
  learning:
    enabled: true
    feedbackLoop:
      - recordActions: true
      - evaluateOutcomes: true
      - improveDecisions: true
    retentionDays: 90
```

### 에이전트 메트릭 수집

```yaml
# ai-agent-metrics.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ai-agent-metrics
spec:
  selector:
    matchLabels:
      app: ai-orchestrator
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics
---
# Grafana Dashboard 쿼리 예시

# 에이전트별 작업 성공률
sum(rate(ai_agent_tasks_total{status="success"}[1h])) by (agent)
/
sum(rate(ai_agent_tasks_total[1h])) by (agent)

# 평균 응답 시간
histogram_quantile(0.95,
  sum(rate(ai_agent_response_duration_seconds_bucket[5m])) by (le, agent)
)

# 토큰 사용량 (비용 추적)
sum(increase(ai_agent_tokens_used_total[1d])) by (agent, model)

# 가드레일 트리거 횟수
sum(increase(ai_guardrail_triggered_total[1h])) by (rule, action)
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| AI에게 프로덕션 접근 허용 | 심각한 보안 리스크 | 개발 환경만 허용 |
| AI PR 무검토 머지 | 품질/보안 문제 | 인간 리뷰 필수 |
| 토큰 예산 미설정 | 비용 폭증 | 팀별 예산 할당 |
| 가드레일 없이 자율 운영 | 예측 불가 행동 | 가드레일 필수 적용 |
| 메트릭 미수집 | ROI 증명 불가 | 사용량/품질 추적 |

---

## AI Agent 오케스트레이션 체크리스트

### 설계
- [ ] 에이전트 역할 정의
- [ ] 워크플로우 설계
- [ ] 가드레일 규칙 정의
- [ ] 승인 게이트 설정

### 구현
- [ ] 오케스트레이터 배포
- [ ] 에이전트 연동
- [ ] 가드레일 적용
- [ ] 모니터링 설정

### 운영
- [ ] 메트릭 대시보드
- [ ] 알림 설정
- [ ] 비용 모니터링
- [ ] 피드백 수집

---

## 참조 스킬

- `dx-ai-agents.md` — AI 에이전트 거버넌스, 엔지니어 역할 전환
- `agentic-coding.md` — Agentic Coding 4가지 모드 상세, Agent Supervision
- `spring-ai.md` — Spring AI MCP 통합, Function Calling
- `finops-ai.md` — AI 비용 관리, Model Routing 비용
- `observability-genai.md` — GenAI 관측성, Agent 루프 감지
- `/dx-ai-security` — 보안/품질
- `/aiops` — AIOps

---

## Sources

- [GitHub Copilot Coding Agent](https://docs.github.com/en/copilot)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [MCP Protocol](https://modelcontextprotocol.io/)
