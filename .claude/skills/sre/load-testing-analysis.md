---
name: load-testing-analysis
description: "부하 테스트 분석 가이드 — nGrinder, 결과 분석, SLO 기반 Threshold Use when working with sre 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# 부하 테스트 분석 가이드

nGrinder, 결과 분석, SLO 기반 Threshold

## nGrinder

### 설치 (Docker)

```bash
# Controller
docker run -d --name ngrinder-controller \
  -p 80:80 -p 16001:16001 -p 12000-12009:12000-12009 \
  ngrinder/controller

# Agent
docker run -d --name ngrinder-agent \
  ngrinder/agent controller-host:80
```

### Groovy 스크립트

```groovy
import static net.grinder.script.Grinder.grinder
import static org.junit.Assert.*
import static org.hamcrest.Matchers.*
import net.grinder.script.GTest
import net.grinder.script.Grinder
import net.grinder.scriptengine.groovy.junit.GrinderRunner
import net.grinder.scriptengine.groovy.junit.annotation.BeforeProcess
import net.grinder.scriptengine.groovy.junit.annotation.BeforeThread
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.ngrinder.http.HTTPRequest
import org.ngrinder.http.HTTPResponse

@RunWith(GrinderRunner)
class TestRunner {
    public static GTest test
    public static HTTPRequest request
    public static Map<String, String> headers = [:]

    @BeforeProcess
    public static void beforeProcess() {
        test = new GTest(1, "API Test")
        request = new HTTPRequest()
        headers.put("Content-Type", "application/json")
        grinder.logger.info("Process initialized")
    }

    @BeforeThread
    public void beforeThread() {
        test.record(this, "testAPI")
        grinder.statistics.delayReports = true
        grinder.logger.info("Thread initialized")
    }

    @Test
    public void testAPI() {
        HTTPResponse response = request.GET(
            "https://api.example.com/users",
            headers
        )

        if (response.statusCode == 200) {
            grinder.logger.info("Success: ${response.statusCode}")
        } else {
            grinder.logger.warn("Failed: ${response.statusCode}")
            grinder.statistics.forLastTest.success = false
        }

        assertThat(response.statusCode, is(200))
    }
}
```

---

## 결과 분석

### 핵심 메트릭

| 메트릭 | 설명 | 목표 예시 |
|--------|------|----------|
| **RPS** | 초당 요청 수 | 서비스별 다름 |
| **Response Time (p50)** | 중간값 응답시간 | < 200ms |
| **Response Time (p95)** | 95% 응답시간 | < 500ms |
| **Response Time (p99)** | 99% 응답시간 | < 1s |
| **Error Rate** | 에러 비율 | < 1% |
| **Throughput** | 처리량 (bytes/s) | 병목 확인 |

### Grafana 대시보드 (K6 + InfluxDB)

```bash
# InfluxDB + Grafana 설치
docker-compose up -d

# K6 실행 (InfluxDB 출력)
k6 run --out influxdb=http://localhost:8086/k6 load-test.js
```

```yaml
# docker-compose.yml
version: '3'
services:
  influxdb:
    image: influxdb:1.8
    ports:
      - "8086:8086"
    environment:
      - INFLUXDB_DB=k6

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
```

### 결과 보고서 작성

```markdown
# 부하 테스트 결과 보고서

## 테스트 개요
- 일시: 2024-01-15 14:00 KST
- 대상: Order API (https://api.example.com/orders)
- 시나리오: 100 VU, 10분간 지속

## 결과 요약

| 메트릭 | 결과 | 목표 | 상태 |
|--------|------|------|------|
| p95 응답시간 | 320ms | < 500ms | Pass |
| p99 응답시간 | 890ms | < 1s | Pass |
| 에러율 | 0.3% | < 1% | Pass |
| 최대 RPS | 1,250 | > 1,000 | Pass |

## 병목 지점
- DB 커넥션 풀 (150 VU 이상에서 대기 발생)
- Redis 캐시 미스율 증가 (p99 지연 원인)

## 권장 사항
1. DB 커넥션 풀 50 → 100 증가
2. Redis 캐시 TTL 조정 (300s → 600s)
3. HPA 트리거 CPU 70% → 60%로 조정
```

---

## SLO 기반 Threshold

```javascript
export const options = {
  thresholds: {
    // 가용성 SLO: 99.9%
    http_req_failed: ['rate<0.001'],

    // 응답시간 SLO
    http_req_duration: [
      'p(50)<200',   // p50 < 200ms
      'p(95)<500',   // p95 < 500ms
      'p(99)<1000',  // p99 < 1s
    ],

    // 특정 엔드포인트 SLO
    'http_req_duration{endpoint:orders}': ['p(95)<300'],
    'http_req_duration{endpoint:search}': ['p(95)<1000'],

    // 시나리오별 SLO
    'http_req_duration{scenario:checkout}': ['p(99)<2000'],
  },
};
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| Think Time 없음 | 비현실적 부하 | sleep() 추가 |
| 단일 엔드포인트만 | 실제 시나리오 미반영 | 다양한 API 조합 |
| 로컬에서 대규모 테스트 | 네트워크 병목 | K6 Operator 분산 |
| Threshold 없이 실행 | Pass/Fail 기준 없음 | SLO 기반 threshold |
| 프로덕션 직접 테스트 | 서비스 영향 | 스테이징 환경 사용 |
| 결과 분석 없이 반복 | 개선 없음 | 보고서 작성 및 추적 |
| nGrinder Agent 부족 | 부하 생성 한계 | Agent 스케일아웃 |

---

## 체크리스트

### nGrinder
- [ ] Controller/Agent 설치
- [ ] Groovy 스크립트 작성
- [ ] Agent 수 충분 확인
- [ ] 테스트 결과 저장

### 결과 분석
- [ ] 핵심 메트릭 수집 (RPS, p95, p99, Error Rate)
- [ ] Grafana 대시보드 구성
- [ ] 병목 지점 식별
- [ ] 결과 보고서 작성

### SLO 기반 Threshold
- [ ] 서비스 SLO 정의
- [ ] 엔드포인트별 threshold 설정
- [ ] CI/CD 연동 (자동 Pass/Fail)
- [ ] threshold 위반 알림 설정

**관련 skill**: `/sre-sli-slo`, `/k8s-autoscaling`, `/monitoring-metrics`

---

## 참조 스킬

- `load-testing.md` - K6 기본/고급 시나리오, K6 on Kubernetes
- `/sre-sli-slo` - SLI/SLO 정의 및 관리
- `/k8s-autoscaling` - 오토스케일링 연동
- `/monitoring-metrics` - 모니터링 메트릭
