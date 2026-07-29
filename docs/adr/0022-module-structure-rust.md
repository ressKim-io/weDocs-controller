# ADR-0022 — crdt-engine 모듈 구조 (Rust)

- 상태: **Accepted**
- 날짜: 2026-07-29
- 관련: [ADR-0019](0019-package-by-feature-java.md)(Java 대응 결정) · `layering-readability.md` P1/P7 · [ADR-0011](0011-engine-sync-fanout-bridge.md)(엔진 = sync 권위) · [ADR-0013](0013-snapshot-persistence-lifecycle.md) · 가드레일 5
- 범위: `weDocs-crdt-engine` 레포의 `src/` 배치. Java(ADR-0019)·frontend(feature 평면)와 **별개 결정**이다.

## 맥락

4레포 중 **Rust 엔진만 모듈 구조 표준이 없다.** backend는 ADR-0019(package-by-feature),
frontend는 feature 평면(2026-07-29 C2에서 실제 반려까지 발생)으로 표준이 있는데,
엔진은 파일이 5개뿐이라 문제가 표면화되지 않았을 뿐이다.

**계기**(2026-07-29, M2 Phase 4): `src/engine.rs`에 스냅샷 저장소 포트(`SnapshotStore` ·
`StoredSnapshot` · `SnapshotStoreError` · `NoopSnapshotStore`)를 추가하면서 한 파일이
**서로 다른 변경 이유 4개**를 갖게 됐다 — ① `DocId` 경계 검증 ② `EngineError` ③ 스냅샷 포트
④ `DocRegistry`. C4(어댑터)·C6(스위퍼)가 더 들어오면 계속 커진다.

⚠️ **크래프트 게이트가 이걸 안 잡았다.** `rust-expert`는 P7을 "통패키지 **신설** 없음"으로
PASS 처리했고, 그건 틀린 판정이 아니다 — P7과 그 근거 ADR-0019는 **이름부터 `-java`**이고
본문 예시도 Spring 패키지다. 즉 룰의 공백이지 리뷰어의 실수가 아니다. 이 ADR이 그 공백을 메운다.

### 기각한 전제 — "파일이 869줄이라 크다"

착수 시 그렇게 판단했으나 **실측이 반박한다.** 실제 배포된 크레이트의 `.rs` 파일 줄 수
(로컬 cargo registry 실측, 2026-07-29):

| 크레이트 | 파일 수 | 중앙값 | 평균 | 최대 |
|---|---|---|---|---|
| **yrs 0.27.2** (본 엔진이 쓰는 CRDT 라이브러리) | 58 | **502** | 693 | 2,847 |
| tokio 1.52.3 | 373 | 122 | 278 | 2,699 |
| tonic 0.14.6 | 60 | 146 | 253 | 2,745 |
| dashmap 6.2.1 | 21 | 118 | 221 | 1,544 |

`engine.rs` 869줄(프로덕션 471 / 테스트 398)은 Rust 실무에서 **큰 축이 아니다**.
Rust는 단위 테스트를 같은 파일 `#[cfg(test)] mod tests`에 두는 것이 관용이라 줄 수가
구조적으로 부풀고, 그래서 **줄 수는 이 결정의 기준이 될 수 없다.**
→ 기준은 **응집도(변경 이유의 수)** 로 삼는다.

## 대안 비교

**증거 수집 방법**: ① 로컬 cargo registry의 실제 배포 크레이트 실측 ② 프로덕션 Rust
**서비스** 레포의 `src/` 구성(GitHub API 실측) ③ hexagonal 아키텍처 가이드 원문.
라이브러리와 서비스를 구분해 봤다 — 엔진은 바이너리 서비스지 라이브러리가 아니다.

| 방안 | 실무 근거 | 엔진 적합성 | 판정 |
|---|---|---|---|
| **A. 현행 평면 유지**(`engine.rs`·`service.rs`에 계속 추가) | — | C4·C6이 들어오면 한 파일이 포트·어댑터·스위퍼·레지스트리를 전부 소유 | ❌ 응집도 붕괴가 이미 시작됨 |
| **B. hexagonal 계층**(`domain/`·`inbound/`·`outbound/`) | [howtocodeit 가이드](https://www.howtocodeit.com/guides/master-hexagonal-architecture-in-rust)가 `domain`+`inbound`+`outbound`를 제시("여러 팀에서 스케일에 잘 작동") | ⚠️ **같은 가이드가 명시적으로 제외하는 대상에 우리가 두 번 해당한다** — "high-performance systems(전송↔도메인 모델 변환 오버헤드가 수용 불가)"와 "solo projects(추상화 계층이 이득 없이 속도만 늦춤)". 엔진은 가드레일 5가 걸린 머지 핫패스 최적화 대상이고 솔로 레포다 | ❌ 출처 자신의 제외 조건에 걸림 |
| **C. 관심사 모듈**(concern이 자라면 `foo.rs` → `foo/`) | **프로덕션 Rust 서비스 2건 실측**: [linkerd2-proxy](https://github.com/linkerd/linkerd2-proxy) `linkerd/app/core/src` = `classify.rs`·`control.rs`·`metrics.rs`·`svc.rs`… 평면 + 자란 것만 `dns/`·`errors/`·`transport/` 디렉토리. [vector](https://github.com/vectordotdev/vector) `src` = `http.rs`(41KB)·`topology/`·`sources/`·`sinks/` — **둘 다 계층 폴더가 없다** | ✅ 고성능 네트워크 서비스의 수렴 패턴이고, 프로젝트 자체 원칙(P7 "패키지는 계층이 아니라 기능 기준")과도 같은 방향 | ✅ **채택** |

> B를 기각한 것은 hexagonal 자체를 부정해서가 아니다. **포트-어댑터는 이미 쓰고 있다** —
> `SnapshotStore` 트레이트를 도메인이 소유하고 어댑터가 구현한다(ADR-0013). 기각한 것은
> 그 개념을 **디렉토리 이름으로 새기는 것**이다. 개념은 트레이트로 이미 강제되고 있으므로
> 폴더까지 계층 이름으로 만들면 P7이 금지하는 "계층 통패키지"를 Rust에서 재현할 뿐이다.

## 결정

**모듈 = 하나의 관심사(도메인 개념). 계층이 아니다.**
관심사가 파일 하나로 안 되면 그때 `foo.rs` → `foo/`로 자란다 — 미리 빈 디렉토리를 만들지 않는다.

```
src/
  main.rs         부트스트랩(서버 빌더·graceful shutdown) — env는 읽지 않는다
  lib.rs          proto 재수출 + 모듈 선언
  config.rs       기동 설정 — 코드가 env를 읽는 유일한 지점 (아래 §설정 일원화, 규칙 7)
  telemetry.rs    OTel/tracing 초기화 (`TelemetryConfig`를 받는다)
  doc.rs          CRDT 문서 도메인 — DocId·EngineError·DocRegistry·DocEntry·DocSlot·Subscription
  snapshot/       스냅샷 영속화 관심사 (파일 3개가 확정적이라 처음부터 디렉토리)
    mod.rs          SnapshotStore 포트 · StoredSnapshot · SnapshotStoreError · Noop
    doc_service.rs  doc-service tonic 어댑터            (C4)
    sweeper.rs      저장 스위퍼 · 재시도 분류           (C6)
  sync/           gRPC 전송 경계 (P7이 명시 허용한 "크로스-feature 전송 어댑터")
    mod.rs          CrdtEngineService(tonic impl) · open_rejection(로그 레벨만)
    session.rs      run_session · handle_inbound · handle_broadcast · SessionCtx
    metadata.rs     MetadataExtractor/Injector · extract_* · SessionRole
    status.rs       WireFault — wire 실패 전체 집합·문구 (아래 §에러 일원화, 규칙 6)
```

### 함께 고정하는 규칙

1. **`DocEntry`·`DocSlot`·`DocRegistry`는 한 파일에 남긴다.** 이들의 안전성이 private 필드와
   `DocSlot::ready()` 은닉에 걸려 있다 — 파일을 가르면 `pub(crate)`로 열어야 하고, 그건 P7이
   "같은 패키지여야 package-private 은닉이 가능"이라고 말한 손해를 Rust에서 그대로 재현한다.
2. **포트와 어댑터는 같은 관심사 디렉토리에 평면으로.** `snapshot/`이 포트(도메인)와
   어댑터(인프라)를 함께 담는다 — 계층으로 가르지 않는다(P7).
3. **단위 테스트는 대상과 같은 파일** `#[cfg(test)] mod tests`(Rust 관용). 통합 테스트만 `tests/`.
4. **분할 트리거 = 응집도**(변경 이유 2개 이상이 한 파일에 상주). **줄 수는 트리거가 아니다** —
   위 실측 표가 근거. 다만 관심사가 하나인데 1,000줄을 넘으면 재점검 신호로 본다.
5. **`pub`은 최소로**, 크레이트 내부 공유는 `pub(crate)`.
6. **wire 실패 문구는 전송 경계 한 모듈이 소유한다**(`sync/status.rs`) — 아래 §에러 일원화.
7. **env 읽기는 `config.rs` 한 곳**(`Config::from_env`) — 아래 §설정 일원화.

## 에러 일원화 — Spring `@ControllerAdvice`의 Rust 대응

**Rust엔 예외가 없다.** 에러가 값(`Result<T, E>`)이라 "throw를 한 곳에서 catch"라는 개념이
성립하지 않고, 중앙화 수단은 **타입 시스템**이다 — `From` 임플 하나를 선언하면 `?`가 컴파일러
수준에서 라우팅한다. 그래서 ADR-0018 §결과가 "Rust는 `thiserror` enum이 그 자체로 카탈로그"라고
적은 것은 맞다. **문제는 그 결정의 나머지 절반이다.**

**실측(2026-07-29)**: `service.rs`에서 `Status::*` 생성이 **11곳**에 흩어져 있고 문구가 대부분
리터럴 하드코딩이다(`INVALID_DOC_ID_MSG`만 상수). 이건 ADR-0018 §맥락이 **Java에서 고쳤던 것과
같은 결함**이다 — *"gRPC 어댑터가 별도 description을 하드코딩 → HTTP/gRPC 메시지가 이미 드리프트"*.
Java는 `DocErrorCode`(slug·message·HttpStatus·grpc Code를 한 줄에)로 고쳤는데 Rust 쪽은 도메인
enum만 있고 **wire 매핑 SSOT가 없다.**

⚠️ **tonic은 이걸 가이드하지 않는다**(✅ verified 2026-07-29,
[docs.rs/tonic Status](https://docs.rs/tonic/latest/tonic/struct.Status.html)):
제공되는 `From`은 `io::Error`·`h2::Error`뿐이고 *"커스텀 애플리케이션 에러 매핑에 대한 명시적
가이드 없음"*. 프레임워크가 안 정해주므로 **우리가 정해야 한다** — 이 절이 그 결정이다.

### 결정

- **`sync/status.rs`가 클라이언트에 노출되는 실패 전체 집합을 소유한다.** `WireFault` enum이
  `Code`와 **고정 문구**를 한 줄에 묶는다(Java `DocErrorCode`와 같은 모양). 한 화면에서
  "이 서비스가 낼 수 있는 실패"가 전부 보인다.
- **도메인 → wire 분류는 `From<&EngineError> for WireFault` 한 곳.** 호출부는 분류하지 않는다.
- **로깅은 변환에 넣지 않는다** — `From`에 부수효과를 두면 놀랍고, 로그 레벨은 `doc_id` 같은
  호출부 컨텍스트를 필요로 한다. 분류(`WireFault`)와 로깅(호출부)을 분리한다.
- **문구 정책은 ADR-0018 §6 그대로 계승**: 고정 영어, 내부 상태·id 보간 금지(secure-coding P4).
  상세 사유는 `EngineError`가 보유하고 **서버 로그로만** 나간다.
- **경계 프로토콜 위반**(메타데이터 부재·role 미인식·`doc_id` 불일치 등)은 ADR-0018 §범위상
  카탈로그 **제외 대상**이지만, 문구 드리프트는 같은 문제라 **같은 enum에 담되 도메인 실패와
  구획을 나눠** 둔다.

## 설정 일원화

**실측**: `std::env::var`가 `main.rs` 1곳 + `telemetry.rs` 2곳에 산재. C4가 `DOC_SERVICE_ADDR`를
추가하면 4곳이 된다. Spring Boot의 `application.yml`+프로파일에 해당하는 것이 Rust엔 프레임워크
차원에서 없고(`figment`·`config` 크레이트가 있으나 현 규모엔 과함), 그래서 **"이 서비스가 읽는
환경변수 전체"를 한 화면에서 볼 수 없다** — 운영에서 가장 아쉬운 지점이다.

→ **`config.rs`의 `Config::from_env()` 한 곳**에서 전부 읽고 파싱·검증한다. 기동 시 파싱 실패는
fail-fast. 크레이트 도입은 하지 않는다(의존성 추가 대비 이득 없음) — 필요해지면 그때.
`RUST_LOG`은 예외로 남긴다(`EnvFilter::try_from_default_env`가 읽는 라이브러리 관례).

⚠️ **"전체"라고 쓰면 거짓이 된다 — 라이브러리 위임분이 있다**(구현 중 발견, 2026-07-29).
`opentelemetry-otlp` 0.32.0은 빌더가 값을 안 받으면 **스스로 env를 읽는다**(✅ verified,
벤더 소스 `exporter/tonic/mod.rs:351-367`): `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` >
`OTEL_EXPORTER_OTLP_ENDPOINT` > 기본 4317. `_PROTOCOL`·`_HEADERS`·`_TIMEOUT`·`_COMPRESSION`도 같다.
그 위임을 **끊지 않는다** — `.with_endpoint()`로 덮으면 signal-specific override가 무력화된다
(M1R-09). 따라서 `config.rs`가 소유하는 것은 **코드가 분기에 쓰는 값**뿐이고, 표시 전용 필드
(`otlp_endpoint`)는 로그 문구와 실제 전송처가 갈릴 수 있다는 경고를 필드 주석에 단다.
**규칙**: 이 파일의 SSOT 주장은 "코드가 읽는 env"로 한정해 쓰고, 위임 목록을 모듈 문서에 남긴다.

## 범위 밖 — M5 운영 기능 트랙

Spring Boot Actuator에 대응하는 것들은 **조각이 다 있으나 조립을 안 했다.** 지금 넣으면 쓸 곳이
없어 YAGNI이고 M2 DoD에도 없다 → **M5(클러스터 배포)에 등록만** 한다(`docs/status/current.md`).

| Spring Boot | Rust 대응 | 상태 |
|---|---|---|
| Actuator health/readiness | `tonic-health` 0.14.6 (tonic과 동일 버전, 누적 57M DL — ✅ verified 2026-07-29 crates.io) | 미도입 → **M5**(K8s probe) |
| Actuator metrics | `metrics` + exporter 또는 OTel metrics | 미도입 → **M5** |
| gRPC reflection(grpcurl) | `tonic-reflection` | 미도입 → M5(개발 편의) |
| Logback 구조화 로깅 | `tracing` + `tracing-subscriber` | ✅ 보유 |
| DI 컨테이너 | `Arc<dyn Trait>` 생성자 주입 | ✅ 보유(`SnapshotStore` 포트) |

## 결과

- `engine.rs` → `doc.rs`(도메인) + `snapshot/mod.rs`(포트) 분리 → 변경 이유 4개 → 2개.
- C4 어댑터·C6 스위퍼가 **들어갈 자리가 미리 정해진다** — 이 ADR이 없으면 또 `engine.rs`로 간다.
- `service.rs`(413 프로덕션 줄, 관심사 5개) → `sync/` 3파일.
- `layering-readability.md` P7의 Java 편중이 드러났다 → 체크리스트에 언어 무관 문구 보강 필요
  (별도 트랙, 이 ADR 범위 밖).

## 트레이드오프 (인정)

- **파일 간 점프가 늘어난다.** 특히 `sync/`는 한 요청 흐름이 3파일에 걸친다. 관심사가 실제로
  다르다는 판단이지만, 흐름 추적 비용은 실재한다.
- **순수 이동 PR 1건의 비용**(리뷰·CI·머지)을 지금 지불한다. C4/C6 이후로 미루면 이동량이
  2배가 되므로 지금이 가장 싸다.
- **`doc.rs`는 여전히 ~360 프로덕션 줄**이고 관심사 경계가 미세하게 남는다(`DocId` 검증 vs
  레지스트리). yrs가 `ids.rs`를 분리한 전례가 있으므로 자라면 `doc/`로 승격한다 — 지금은 규칙 4에
  따라 분할 트리거 미달로 본다.
- **이 구조가 M3(멀티인스턴스 라우팅)·M5를 견딜지는 미검증.** 워크스페이스 분할(크레이트 다중화)이
  필요해지는 시점은 `sccache`/`vector` 사례상 수만 줄부터라 아직 멀다고 보지만, 재점검 조건을
  규칙 4에 남겼다.
