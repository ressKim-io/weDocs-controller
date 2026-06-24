---
paths:
  - "**/monitoring/**"
  - "**/grafana/**"
  - "**/*dashboard*"
  - "**/*alert*"
  - "**/*recording*"
  - "**/tempo/**"
  - "**/loki/**"
  - "**/mimir/**"
  - "**/alloy/**"
  - "**/otel*/**"
  - "**/pyroscope/**"
---

# Monitoring Rules

모니터링 관련 코드 작업 시 반드시 따라야 할 규칙.
Grafana 대시보드 JSON, Tempo/Loki/Mimir/Alloy/Pyroscope 설정, PromQL/LogQL/TraceQL 쿼리, recording/alerting rule 작업에 적용된다.

---

## 모니터링 최우선 원칙 (MANDATORY)

모든 코드/인프라 작업에서 모니터링은 사후 추가가 아닌 **기본 요구사항**으로 다룬다.

- 새 서비스/엔드포인트 추가 시 메트릭 + 로그 + 추적 동시 설계
- 새 의존성 도입(외부 API, DB, 캐시) 시 SLI/SLO 우선 정의
- 인프라 변경(스케일링, 노드그룹, NetworkPolicy 등)은 관련 대시보드/알림 영향 동시 확인
- "기능 동작 확인됨" ≠ "관찰 가능". 관찰 불가능한 기능은 production-ready 아님

---

## 라벨 변경 시 일괄 영향 검사 (MANDATORY)

대시보드/쿼리에서 사용하는 label을 변경하면 **반드시 아래 항목을 일괄 검사**한다:

- [ ] alerting rules (`PrometheusRule`) 전체 — label 매처 일치 여부
- [ ] recording rules — `by ()` 절 변경 여부
- [ ] Grafana 대시보드 JSON 전체 — variable / panel 쿼리
- [ ] ServiceMonitor / PodMonitor selector
- [ ] cross-service join 쿼리 (`*_info` metric의 label join)

단일 label 변경 누락이 alert 미발화 / 대시보드 No data / SLO 미산정으로 이어진다.

---

## OTel → Prometheus job label 매핑 스펙 (MANDATORY)

OTel Collector/Alloy로 수집한 메트릭이 Prometheus의 `job` label로 매핑될 때 다음 spec을 따른다:

```
job="<namespace>/<service.name>"
```

- `service.name` (resource attribute) → job 의 후반부
- namespace (K8s) → 전반부
- 대시보드/recording rule은 이 형식을 가정해서 작성 (`job=~"<ns>/.+"`)
- OTel SDK에서 `service.namespace` 별도 설정해도 Prometheus `job` 라벨로는 위 형식 유지

매핑이 깨지면(예: `job="service.name"`만) ServiceMap, app dashboard 전체에서 No data.

---

## 필수 참조 (MANDATORY)

모니터링 관련 코드를 작성하거나 수정하기 전, 반드시 `docs/monitoring-pitfalls.md`를 읽고 해당 섹션을 확인하라.

---

## 핵심 체크리스트 (Quick Reference)

### TraceQL

- `=~` regex에 Grafana multi-value 변수 사용 금지 → `select()`로 대체
- Tempo v2 API: tag key에 scope prefix 필수 (`resource.service.name`, `span.http.route`)
- 서비스 필터: `{resource.service.name="$svc"}` (`$service_name` 아님)
- **serviceMap 쿼리는 PromQL** (TraceQL 아님): `["{client=\"$svc\"}", "{server=\"$svc\"}"]`

### LogQL (Loki Native OTLP)

- 로그 레벨 필터: `detected_level="ERROR"` (대문자) — `level="error"` 사용 금지
- 서비스 필터: `{service_name=~"$svc", service_name=~".+"}` — `{job=...}` 사용 금지. **`service_name=~".+"` 필수** — `$svc`가 `.*`로 치환 시 Loki가 empty-compatible matcher 거부
- kube-events: `{job="kube-events"} | json | namespace=~"$ns"` — `namespace`는 post-extraction 필터이지 **stream selector가 아님**. `{namespace=~"$ns"}`로 쓰면 No data
- Loki label API (`/loki/api/v1/labels`): 기본 최근 1시간만 조회 — 트래픽 적은 환경에서 `start`/`end` 파라미터 필수

### PromQL

- `histogram_quantile`에 `by (le)` 필수 — 누락 시 결과 NaN
- 나눗셈에 `> 0` 보호: `/ (sum(rate(total[...])) > 0)`
- multi-value 변수는 반드시 `=~` 사용

### Recording Rule

- MSA: `or (0 * sum by (job) (rate(...)))` — `on() vector(0)`은 job 레이블 미보존
- MSA: `by (job)` 필수 — `job=~"{namespace}/.+"` + `by (job)` 또는 `by (job, le)`
- Helm template: `{{ $labels.job }}` → `{{ "{{" }} $labels.job {{ "}}" }}` 이스케이프

### OTel Semantic Conventions

- stable conventions 사용: `http.request.method`, `http.response.status_code`
- 구버전(`http.method`, `http.status_code`) 사용 금지

### Datasource UID (고정)

- `prometheus`, `loki`, `tempo`, `pyroscope` — 변경 절대 금지

### ServiceMonitor (Alloy Scraping)

- 외부 Helm chart(ArgoCD, Pyroscope 등)의 ServiceMonitor에 **반드시** `release: kube-prometheus-stack` 라벨 추가
- 라벨 없으면 Alloy `prometheus.operator.servicemonitors` selector에 매칭 안 됨 → 메트릭 수집 불가
- chart마다 키 이름 다름: `additionalLabels`, `labels` 등 — `helm show values`로 확인 필수

### Alloy

- River 문법 사용 (표준 OTel Collector YAML 아님)
- `loki.attribute.labels` 미작동 → Loki native OTLP + `otlp_config.index_label` 사용

### Tempo (chart v1.x legacyConfig)

- **overrides 경로 2가지 구분 필수**:
  - `tempo.overrides.defaults` → `tempo.yaml` 본문에 렌더링 (standardOverrides) → `metrics_generator.processors` **사용 가능**
  - `tempo.per_tenant_overrides` → `overrides.yaml` ConfigMap에 렌더링 (**LegacyOverrides**) → `metrics_generator` 필드 **미지원** (파싱 에러 → CrashLoopBackOff)
- 제한값(max_traces, ingestion_rate 등)은 `per_tenant_overrides`로 설정
- metricsGenerator processors 활성화는 `overrides.defaults`로 설정
- `multitenancy_enabled: false`일 때 tenant 키: `"single-tenant"`
- CrashLoopBackOff 중 ConfigMap 업데이트 미반영 가능 → `kubectl delete pod`로 강제 재생성
- `metricsGenerator.processor` config만으로는 processors 미활성화 — `overrides.defaults`에서 명시적 활성화 필수

### Pyroscope

- tag에 `.` 사용 불가 → `_`로 대체 (`service_name`, not `service.name`)

### Apdex

- OTel 기본 버킷에 `le="2.0"` 없음 → `le="2.5"` 사용

---

## 변수 매핑 빠른 참조

```
$service_name = job label ("{namespace}/{service-name}") → PromQL용
$svc          = hidden, regex .*/(.+) → Loki/Tempo용

PromQL:  job="$service_name"
LogQL:   {service_name=~"$svc"}
TraceQL: {resource.service.name="$svc"}
```

---

## 대시보드 수정 후 체크리스트 (MANDATORY)

대시보드 JSON을 수정한 후 반드시 아래 순서를 따른다:

1. `grafana/dashboards/` 수정 (SSOT — 원본은 여기)
2. `charts/{monitoring-chart}/dashboards/`에 복사
3. `{infra-repo}/scripts/validate/extract-queries.sh`에 새 변수 치환 추가
4. `{infra-repo}/scripts/validate/payloads/`에 새 attribute 추가
5. JSON 유효성 검증 (`jq empty` 또는 `python3 -m json.tool`)

---

## 절대 금지 사항

| 금지 행위 | 이유 |
|---|---|
| TraceQL에서 `=~` + Grafana multi-value 변수 | TraceQL plugin이 pipe-separated 변환 미지원, 400 에러 |
| Loki `level="error"` (소문자) | Native OTLP는 `detected_level="ERROR"` (대문자) |
| `histogram_quantile`에서 `by (le)` 누락 | 결과가 NaN |
| Datasource UID 변경 | 모든 대시보드 참조 깨짐 |
| Pyroscope tag에 점(`.`) 사용 | Pyroscope가 invalid로 거부 |
| OTel Java Agent + Spring Boot Starter 동시 사용 | 이중 계측 발생 |
| Tempo span_metrics에 unbounded 차원 추가 (`http.url`, `user.id`) | 카디널리티 폭발 |
| Tempo `per_tenant_overrides`에 `metrics_generator` 키 사용 | LegacyOverrides 파싱 에러 → CrashLoopBackOff. `overrides.defaults`에서 설정 |
| OTel Java Agent 환경에서 `process_start_time_seconds` 사용 | OTel Agent 미노출 (Prometheus client 전용). `kube_pod_start_time` 대체 |
| `grafana/dashboards/` 수정 없이 chart 내 JSON만 수정 | SSOT 위반, 다음 동기화 시 덮어씀 |
| `or on() vector(0)` MSA에서 사용 | job 레이블 미보존 → `or (0 * sum by (job) (...))` 사용 |
| `serviceMapQuery`에 TraceQL 문법 사용 | PromQL 레이블 매처만 허용 (`client`, `server` 레이블) |
| Alloy에서 표준 OTel Collector YAML 문법 사용 | River 문법만 동작 |
| kube-events LogQL에서 `{namespace=~"$ns"}` stream selector 사용 | `namespace`는 stream label 아님 → `| json` 후 post-extraction 필터로 사용 |
| ServiceMonitor에 `release` 라벨 누락 | Alloy selector 매칭 불가 → 메트릭 수집 안 됨 |
