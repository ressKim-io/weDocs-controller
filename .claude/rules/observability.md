---
paths:
  - "**/*.java"
  - "**/*.rs"
  - "**/*.py"
---

# 관측성 표준 (코드 레벨 — 로깅·트레이싱·메트릭)

> **위상**: 프로젝트 전체·언어 공통 표준. 개인 컬렉션(`ress-claude-agents`)으로 승격.
> **`monitoring.md`와의 구분**: `monitoring.md` = **운영 레벨**(PromQL·Grafana·OTel 수집/대시보드). 이 문서 = **코드 레벨**(코드에서 어떻게 로그·span·메트릭을 남기나). 둘은 상호보완.
> **네 번째 표준(2026-06-30)** — 세트 완성. `error-handling.md` P6("한 번, 경계에서")를 구체화.

---

## 원칙 (P) — 언어 무관

**P1. 구조적 로깅.** 문자열 보간 대신 **key-value 필드**(JSON/logfmt). `"user " + id + " failed"` ❌ → `error(event, user_id=id)` ✅. 2026 표준: 로그 도구가 JSON 필드 쿼리 전제.

**P2. 로그 레벨 규율.**
```
ERROR  조치가 필요한 실패           WARN   처리된 이상(재시도 성공·캐시 미스)
INFO   기본(중요 상태 전이)          DEBUG  진단용(운영 기본 비활성)
```
남발 금지 — INFO에 디버그 쏟거나, 처리한 예외를 ERROR로 올리지 말 것.

**P3. 상관관계(correlation).** 요청 진입점에서 trace/correlation id를 부여·전파하고 **모든 로그 라인에 포함**. W3C: `trace_id`(32 hex)·`span_id`(16 hex). → 너희 폴리글랏 `traceparent`가 이미 이 축(가드레일 4).

**P4. 시크릿/PII 금지.** 토큰·비밀번호·JWT·개인정보를 로그에 남기지 말 것. 쿼리 파라미터·헤더·SQL·스택트레이스에 딸려 새는 것도 주의(경계에서 마스킹).

**P5. 한 번만, 경계에서.** 같은 실패를 계층마다 중복 로깅 금지 → 경계 핸들러에서 1회(`error-handling.md` P6). 삼키고 로그만 찍기도 금지.

**P6. 작업을 span으로 감싸고 로그·메트릭·트레이스를 잇는다.** 의미 있는 작업 단위를 span으로, 로그 라인에 trace id를 넣어 3축(log/metric/trace) 연결(RED: Rate·Errors·Duration).

---

## Java 실현 (SLF4J)

**P1 — 파라미터화 로깅(문자열 concat 금지).**
```java
// ❌ log.info("doc " + id + " opened by " + user);   (concat + 비구조적)
// ✅ 플레이스홀더 + MDC 구조 필드
log.atInfo().addKeyValue("docId", id).addKeyValue("userId", user).log("page opened");
```
- ⛔ `System.out.println`/`printStackTrace()` 금지 → 로거만.

**P3 — MDC에 상관 id.** 진입 필터에서 `MDC.put("traceId", ...)` → 모든 로그에 자동 포함. (OTel javaagent가 이미 trace 주입 — MDC 패턴으로 로그와 연결)

**P4 — 민감정보 마스킹.** JWT/비번/이메일 원문 로깅 금지.

---

## Rust 실현 (`tracing`)

**P1/P6 — 구조적 필드 + span.**
```rust
// ✅ 구조적 필드 (엔진이 이미 이렇게 함 — 준수 예시)
tracing::warn!(%doc_id, error = %e, "apply_v1 failed");

// ✅ 작업을 span으로 감싸 로그를 trace에 연결 (엔진 .instrument(span) — 준수)
let span = tracing::info_span!("crdt.sync", doc_id = %doc_id);
async move { ... }.instrument(span)
```
- ⛔ `println!`/`eprintln!` 금지 → `tracing`만. (엔진이 M1 Phase4에서 `eprintln!`→`tracing` 전환 = 이 표준 준수)
- 레벨: 예상 실패는 `warn!`(스트림 유지), 치명은 `error!`. `%`=Display, `?`=Debug 필드.

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3에서 `rust-expert`/`java-expert`가 실행. **[B]=blocking, [A]=advisory.**

**공통**
- [ ][B] 시크릿/PII(토큰·비번·JWT·개인정보) 로그 없음 (P4)
- [ ][B] `System.out`/`println!`/`eprintln!`/`printStackTrace` 없음 → 로거만 (P1)
- [ ][B] 같은 실패 중복 로깅 없음(경계 1회) (P5)
- [ ][A] 구조적 필드(key-value), 문자열 concat 아님 (P1)
- [ ][A] 로그 레벨 적절(처리된 이상=WARN, 조치필요=ERROR) (P2)
- [ ][A] 의미 단위를 span으로, 로그에 trace/correlation id (P3/P6)

---

## 게이트 배선 (활용 강제)

`code-review.md` 크래프트 렌즈(🦀/☕)가 이 체크리스트 실행. `[B]`(시크릿 로깅·println·중복로깅)=반려. 운영 대시보드/알람 설계는 `monitoring.md` 소관. 새 함정은 `review-gaps.md` → 이 문서로 승격.

---

## 출처

- 로깅: [Structured Logging Best Practices 2026 (Grepr)](https://www.grepr.ai/blog/structured-logging-best-practices) · [Application Logging (Coralogix)](https://coralogix.com/guides/application-performance-monitoring/application-logging-best-practices/) · [SigNoz — Structured Logs](https://signoz.io/blog/structured-logs/)
- 트레이스: W3C Trace Context(`trace_id`/`span_id`) · [Distributed Tracing Logs (groundcover)](https://www.groundcover.com/learn/logging/distributed-tracing-logs)
- 내부 연계: `monitoring.md`(운영), `error-handling.md` P6(1회 로깅)
