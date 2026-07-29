---
date: 2026-07-29
category: meta
tier: 2
importance: major
status: resolved
tags: [adr, craft-standards, rust, module-structure, error-catalog, gate-gap, layering-p7]
related:
  - adr/0022-module-structure-rust.md
  - adr/0019-package-by-feature-java.md
  - adr/0018-error-catalog.md
  - dev-logs/2026-07-29-m2-phase34-engine-restore.md
  - dev-logs/2026-07-28-rules-do-not-cross-repo.md
---

# 표준이 Rust에서 덜 발화한 지점 — ADR-0022가 나온 경위

> 사용자 지적("구조 없이 할 거냐")에서 시작해 **ADR 체계의 공백 3개**가 드러났다.
> 다음 세션의 ADR 분석용 재료로 쓰라고 근거를 전부 남긴다.

## 계기

M2 Phase 4에서 스냅샷 포트를 `engine.rs`에 추가했고 게이트를 **통과**했다. 사용자가 물었다 —
"이거 큰 구조를 안 잡고 대강 이런 식으로만 하는 거야? Spring이나 Gin처럼 구조가 없이 할 거야?"

그 시점 상태: `src/`가 평면 5파일, `engine.rs`가 **서로 다른 변경 이유 4개**(DocId 경계검증 ·
`EngineError` · 스냅샷 포트 · `DocRegistry`)를 보유. C4 어댑터·C6 스위퍼가 더 들어올 예정.

## 공백 1 — `layering-readability.md` P7의 내용이 Java 형태다

게이트(`rust-expert`)는 P7을 "통패키지 **신설** 없음"으로 PASS 처리했다. **틀린 판정이 아니다.**

원인 실측:

| 룰 | Java 어휘 | Rust 어휘 | TS |
|---|---|---|---|
| **layering-readability.md** | **23행** | **6행** | 0 |
| error-handling.md | 16 | 18 | 0 |
| concurrency.md | 10 | 18 | 0 |
| design-patterns.md | 12 | 7 | 0 |
| secure-coding.md | 12 | 11 | 1 |
| observability.md | 5 | 3 | 0 |

**발화 실패한 P7이 있는 파일이 유일하게 Java 쪽으로 4배 기운 룰이다.** 나머지 5종은 균형이거나
Rust 우세 → **체계적 편중이 아니라 P7 국소 문제.**

`paths:`는 문제가 아니었다 — 6종 모두 `**/*.java` + `**/*.rs`를 포함해 스코프는 맞다.
문제는 **내용**이다: P7 본문은 Spring Modulith 근거 + `api/`·`service/`·`repository/` 예시 +
`workspace/`·`page/` feature 예시로 채워져 있고, 근거 ADR은 **이름부터 `0019-package-by-feature-java.md`**다.
그래서 Rust 파일에 적용할 때 "전역 계층 통패키지 신설"이라는 **Java 형태의 질문만** 남고,
"이 모듈이 관심사 하나인가"라는 언어 무관 질문이 없다.

### 함께 드러난 것 — frontend는 아예 커버가 없다

6종 어느 `paths:`에도 `**/*.ts`/`**/*.tsx`가 없다. 그런데 `current.md`는 C2에서 프론트가
P7 위반으로 **실제 반려됐다**고 기록한다. 즉 그 게이트는 **룰 로딩이 아니라 사람/에이전트의
유추로** 발화했다. 재현성이 없다.

## 공백 2 — ADR-0018의 "Rust는 thiserror enum이 카탈로그"는 절반만 맞다

ADR-0018 §결과 51행이 그렇게 적어뒀고, 도메인 쪽으로는 맞다(`EngineError`가 존재).
**그런데 wire 매핑 SSOT가 없었다.**

실측: `Status::*` 생성이 `service.rs` **11곳**에 흩어져 문구가 대부분 리터럴 하드코딩
(`INVALID_DOC_ID_MSG`만 상수). 이건 ADR-0018 §맥락이 **Java에서 고쳤던 결함과 같은 것**이다 —
*"gRPC 어댑터가 별도 description을 하드코딩 → HTTP/gRPC 메시지가 이미 드리프트"*.

Java는 `DocErrorCode`(slug·message·HttpStatus·grpc Code를 한 줄에)로 고쳤는데, Rust 쪽은
"enum이 곧 카탈로그"라는 문장이 **매핑까지 커버하는 것처럼 읽혀** 아무도 후속 작업을 안 했다.

✅ **verified 2026-07-29** — tonic은 이걸 가이드하지 않는다
([docs.rs/tonic Status](https://docs.rs/tonic/latest/tonic/struct.Status.html)): 제공되는 `From`은
`io::Error`·`h2::Error`뿐이고 *"커스텀 애플리케이션 에러 매핑에 대한 명시적 가이드 없음"*.
프레임워크가 안 정해주므로 팀이 정해야 하는 종류의 결정이었다.

→ `sync/status.rs`의 `WireFault` enum(= Java `DocErrorCode`의 Rust 대응)으로 해소.

## 공백 3 — 내가 "줄 수"로 판단했고, 실측이 반박했다

착수 시 나는 사용자의 "줄 수가 너무 많다"에 그냥 동의했다. **성급했다.**

실측(로컬 cargo registry의 실제 배포 크레이트):

| 크레이트 | 파일 수 | 중앙값 | 평균 | 최대 |
|---|---|---|---|---|
| **yrs 0.27.2** (본 엔진이 쓰는 CRDT 라이브러리) | 58 | **502** | 693 | 2,847 |
| tokio 1.52.3 | 373 | 122 | 278 | 2,699 |
| tonic 0.14.6 | 60 | 146 | 253 | 2,745 |
| dashmap 6.2.1 | 21 | 118 | 221 | 1,544 |

`engine.rs` 869줄(프로덕션 471)은 Rust 실무에서 **큰 축이 아니다.** Rust는 단위 테스트를 같은
파일 `#[cfg(test)] mod tests`에 두는 관용이라 줄 수가 구조적으로 부푼다.

**진짜 결함은 응집도**였다 — 스냅샷 포트와 문서 레지스트리가 한 파일에 동거하는 것.
→ ADR-0022 규칙 4가 **"분할 트리거는 응집도이고 줄 수는 명시적으로 배제"**로 고정.

> 이 오판을 `current.md` §알아둘 것에도 올렸다. 안 적으면 다음 세션이 같은 판단을 반복한다.

## 구조 결정의 근거 (ADR-0022)

hexagonal(`domain/`·`inbound/`·`outbound/`)을 기각하고 관심사 모듈을 택했다. 근거 3종:

1. **프로덕션 Rust 서비스 실측** — [linkerd2-proxy](https://github.com/linkerd/linkerd2-proxy)
   `linkerd/app/core/src` = `classify.rs`·`control.rs`·`metrics.rs`·`svc.rs` 평면 + 자란 것만
   `dns/`·`errors/`·`transport/`. [vector](https://github.com/vectordotdev/vector) `src` =
   `http.rs`(41KB) + `topology/`·`sources/`·`sinks/`. **둘 다 계층 폴더가 없다.**
2. **hexagonal 가이드 자신의 제외 조건** —
   [howtocodeit](https://www.howtocodeit.com/guides/master-hexagonal-architecture-in-rust)가
   "high-performance systems(전송↔도메인 변환 오버헤드 수용 불가)"와 "solo projects(추상화가
   이득 없이 속도만 늦춤)"를 명시 제외한다. 엔진은 **둘 다 해당**(가드레일 5 + 솔로 레포).
3. **프로젝트 자체 원칙** — P7 "패키지는 계층이 아니라 기능 기준"과 같은 방향.

핵심 논지: **포트-어댑터는 이미 트레이트가 강제한다**(ADR-0013). 폴더 이름으로 또 새기면
P7이 금지한 계층 통패키지를 Rust에서 재현할 뿐이다.

## 구현 중 발견 — 일원화 주장이 거짓이 되는 지점

`config.rs`에 "이 서비스가 읽는 env **전체**"라고 썼는데 거짓이었다. `opentelemetry-otlp` 0.32.0은
빌더가 값을 안 받으면 스스로 읽는다(✅ 벤더 소스 `exporter/tonic/mod.rs:351-367`):
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` > `OTEL_EXPORTER_OTLP_ENDPOINT` > 기본 4317.

더 나쁜 건 `config.otlp_endpoint`의 **유일한 소비처가 기동 로그 문구**라는 점이다 — 운영자가
signal-specific 변수를 설정하면 **스팬은 거기로 가는데 로그는 다른 값을 말한다.**
리팩터링 전엔 `env::var`가 그 `format!` 세 줄 위에 있어 보이던 갭인데, **스스로 권위라고
선언하는 모듈로 옮기면서 오히려 가려졌다.**

`.with_endpoint()`로 메우는 건 금지(M1R-09 — signal-specific override를 덮는다) → 문서로 관리.

> **일반 교훈**: "일원화"를 선언하는 모듈은 **위임분을 함께 명시**해야 한다. 선언만 하고 예외를
> 안 적으면, 그 선언 자체가 다음 사람이 예외를 못 보게 만드는 장치가 된다.

## 다음 세션의 ADR 분석에서 볼 것 (열린 질문)

1. **P7을 언어 무관하게 재작성할 것인가, 언어별로 쪼갤 것인가?**
   현 P7 = Spring Modulith 근거 + Java 예시 + `-java` ADR. Rust/TS에는 "관심사 하나인가"라는
   언어 무관 질문이 필요하다. `[B]` 체크리스트 행을 언어별로 나눌지, 상위 원칙 1행 + 언어별
   실현으로 갈지.
2. **frontend 커버리지** — 6종 `paths:`에 `**/*.ts{,x}` 추가할지. 추가하면 Java/Rust용 `[B]`
   항목이 프론트에서 오탐을 낼 위험을 어떻게 억제할지(`craft-standards-gate-activation` 메모리의
   "커밋 전 실코드 게이트 시뮬레이션" 절차 적용 대상).
3. **ADR-0018의 Rust 문장 개정** — "thiserror enum이 그 자체로 카탈로그"가 wire 매핑까지
   커버하는 것처럼 읽힌 것이 이번 누락의 원인. ADR-0022 §에러 일원화를 ADR-0018에 역참조할지,
   0018 본문을 고칠지.
4. **ADR 번호 체계와 언어 스코프** — `0019-package-by-feature-java` / `0022-module-structure-rust`로
   언어별 ADR이 둘 생겼다. 앞으로 프론트가 생기면 셋이 된다. 상위 "구조 원칙" ADR 하나 +
   언어별 실현으로 묶을지, 지금처럼 병렬로 둘지.
5. **게이트가 PASS인데 사용자가 문제를 발견한 사례** — 이번이 그 첫 케이스다. 게이트 통과가
   "구조가 옳다"를 뜻하지 않는다는 걸 어디에 기록할지(`code-review.md`? `deep-thinking.md`?).

## 산출

| | |
|---|---|
| ADR | [0022](../adr/0022-module-structure-rust.md) 신설(Accepted) — 구조 규칙 7개 + 에러 일원화 + 설정 일원화 + M5 운영 트랙 |
| 코드 | engine [PR #14](https://github.com/ressKim-io/weDocs-crdt-engine/pull/14) `28e1b9c` — 동작 무변경(기존 40 테스트 통과, 벤치 166µs 동일) |
| 실측 규칙 성립 | `env::var` → `config.rs` 1곳 · `Status::*` 생성 → `status.rs` 1곳(이전 11곳) |
| 미해소 | 위 §열린 질문 5건 — **다음 세션 ADR 분석 대상** |
