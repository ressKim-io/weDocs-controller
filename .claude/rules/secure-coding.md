---
paths:
  - "**/*.java"
  - "**/*.rs"
  - "**/*.py"
---

# 시큐어 코딩 표준 (언어 무관 원칙 + 언어별 관용구)

> **위상**: 프로젝트 전체·언어 공통 표준. 개인 컬렉션(`ress-claude-agents`) 승격 대상.
> **왜 있나**: 보안이 🔒 렌즈(인프라: securityContext·RBAC·TLS)에만 있고 **앱 diff를 보는 게이트가 없어**, 무검증 입력·무상한 자원이 리뷰를 통과해 왔다 — 실증: 3-레포 관통 DoS 체인(frontend 무검증 room → gateway 무검증 전달 → engine 무한 문서 생성+eviction 없음)·WS Origin `*`·프레임/메시지 크기 무상한(런타임 기본값 암묵 의존)·gRPC deadline 부재. 아는데 안 쓴 것 → 체크리스트로 강제.
> **여섯 번째 표준(2026-07-03)** — 틀은 `error-handling.md`. `security.md`(전역 베이스라인)를 재정의하지 않고 **게이트로 승격**한다.
> **역할 분담**: `security.md` = 금지 목록 SSOT(시크릿·주입·해시·PII — 재서술 없이 체크리스트 1줄로 위임 집행) / `concurrency.md` P7 = 내부 채널 백프레셔(이 표준 P2는 **외부 입력이 유발하는 자원**만) / `observability.md` P4 = 로그로 새는 시크릿(이 표준 P4는 **응답·close로 나가는 정보**만) / 인프라 하드닝(mTLS·NetworkPolicy·securityContext) = 🔒 렌즈 + `k8s-manifest.md`·`istio.md`(M5). 심화 지식: `skills/security/secure-coding.md`(동명 스킬 = 지식, 이 룰 = 게이트)·`owasp-top10.md`·`auth-patterns.md`. 인증·인가 **경계 결정** = ADR-0014·SDD §8.

---

## 원칙 (P) — 언어 무관

**P1. 모든 외부 입력은 경계에서 검증 후 도메인 타입으로.** 신뢰 경계(WS 핸드셰이크·HTTP·gRPC 메타데이터·프레임 페이로드)를 명시하고 진입 즉시 구문 검증(길이 상한·문자집합·형식). 검증 통과 = 도메인 타입 생성(`design-patterns.md` P5/P6과 같은 관문) — 미검증 원시값의 내부 유입 금지. gRPC 메타데이터도 클라이언트 통제 값이다 — 신뢰하지 않는다.

**P2. 모든 자원·조회에 상한과 수명.** 무상한 = DoS. 외부 입력이 만들 수 있는 **상태**(맵·세션·문서), 받아들이는 **크기**(프레임·메시지·본문), 돌려주는 **양**(질의 결과)에 상한을 — 그리고 생성에는 소멸(eviction/TTL/명시 해제)을 짝짓는다. 신규 상태·수신 경로마다 묻는다: **"누가 이걸 무한히 만들 수 있나?"**

**P3. 인가는 접근점마다, 기본 거부.** 인증(누구냐) ≠ 인가(이 리소스에 되냐) — 모든 리소스 접근이 소유/멤버십 검증을 지난다(IDOR 방지). 배선 위치 SSOT = ADR-0014(gateway 핸드셰이크 검증 · doc-service `CheckPermission` · viewer write-block 다층). 내부 전용 RPC는 신뢰 경계 전제(mTLS/NetworkPolicy — M5)를 **코드 주석으로 문서화**한다.

**P4. 밖으로는 최소, 안으로는 최대.** 에러 응답·close 사유에 내부 상태(서버측 기대값·스택·설정·버전) 에코백 금지 — 클라이언트에는 분류(code)만, 상세는 trace id로 연결된 내부 로그에(`error-handling.md` P6 · `observability.md` P3 연동).

**P5. 안전 기본값 — 완화는 근거를 남긴다.** 평문 채널·와일드카드 Origin·무제한(deadline/한도 부재)·dev 크리덴셜은 "임시"라도 **근거 주석+이슈 링크** 없이는 반려. 하드닝 보류는 코드 TODO가 아니라 SDD §15/plan에 등록해 추적. **런타임 기본값에 암묵 의존 금지** — 한도는 명시 설정이 곧 문서다(`config-contract-audit.md` 3단계 검증과 동일 정신).

---

## Java / Spring 실현

**P1 — 핸드셰이크에서 room 검증.** 게이트웨이는 URL 마지막 세그먼트를 무검증으로 doc-id로 전달(→ 엔진 무한 문서 연쇄). 처방: `HandshakeInterceptor`에서 길이·문자집합 검증 → 도메인 타입(`RoomId`) 생성 후 세션 attributes로 전달. REST 입력은 Bean Validation `@Valid`(`spring.md` 연동).

**P2 — WS 컨테이너 상한 명시.** 컨테이너 기본값(Tomcat binary/text 버퍼 8192B)에 암묵 의존하면 (a) 정상적인 대형 Yjs sync-step2가 세션을 끊는 결함 (b) 의도적 상한의 부재 — 양방향 결함이다.
```java
@Bean
ServletServerContainerFactoryBean wsContainer() {
    var c = new ServletServerContainerFactoryBean();
    c.setMaxBinaryMessageBufferSize(/* 프로토콜 최대 프레임 근거로 명시 */);
    c.setMaxSessionIdleTimeout(/* 유휴 세션 수명 — P2 "소멸" */);
    return c;
}
```

**P5 — Origin은 화이트리스트.** Spring WS 기본 = same-origin만. `setAllowedOriginPatterns("*")`는 **명시적 완화**이며, 네이티브 WS엔 CSRF 토큰 방어가 없어 Origin이 유일 방어선 — 배포 프로파일은 화이트리스트 필수, `*`는 근거 주석+이슈가 있어야만.

**P5 — 아웃바운드 gRPC.** gRPC는 기본 deadline이 없다(무기한 대기 → VT·풀 고갈) → 신규 unary 호출은 `withDeadlineAfter` 필수(M2 1b `DocService` 4 RPC 직결). 채널 keepalive·재연결 정책 명시. dev 크리덴셜(`application.yml` 기본값)은 프로파일 분리.

**P2 — 조회 상한.** 무한 성장 테이블(page·snapshot·outbox) 조회는 `Pageable`/limit — 무상한 `List` 반환은 OOM 벡터.

---

## Rust 실현

**P2 — tonic 인바운드 상한 명시.** tonic 디코딩 기본 한도 4MB — 존재하지만 **암묵**. CRDT update 최대 크기 근거와 함께 명시하고, 서버 자원도 무제한 금지:
```rust
CrdtEngineServer::new(svc).max_decoding_message_size(LIMIT); // 근거 주석과 함께 (P2/P5)
Server::builder()
    .concurrency_limit_per_connection(N)                     // 무제한 금지 (P5)
    .timeout(Duration::from_secs(T))
```

**P1 — DocId 검증 생성자.** `DocId::from` = 순수 wrap(검증 없음)인데 doc-id는 gRPC 메타데이터(클라이언트 통제 값)로 들어온다 → `TryFrom<&str>`(길이·문자집합)로 경계 검증. `design-patterns.md` P5(validated construction)와 같은 처방의 보안면.

**P2 — 레지스트리 상한+수명.** `open()`은 DashMap 삽입만 하고 remove가 어디에도 없다 → 모든 세션 종료 후에도 `DocEntry`(yrs Doc+broadcast) 영구 잔존 = 메모리 DoS. 처방: 문서 수 상한(초과 시 `Status::resource_exhausted`)은 즉시, eviction은 영속화(ADR-0013) 선행 조건(durable 전 evict = 데이터 유실 — SDD §15에 M2 Phase 3+ 등록).

**P3/P4 — 내부 RPC 신뢰 경계·에코백 제거.** `GetSnapshot`은 무인가 전체 상태 덤프 — 내부 전용이면 신뢰 경계 주석+이슈, 외부 노출이면 인가 배선(ADR-0014). doc-id mismatch 에러가 서버측 stream doc-id를 에코백 — 분류(code)만 반환한다.

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3에서 `rust-expert`/`java-expert`가 diff에 대고 실행. **[B]=blocking(반려), [A]=advisory(코멘트).**
> **칼리브레이션**: `[B]`는 **diff가 생성·변경하는 코드**에 적용 — diff 밖 기존 위반은 `[A]` 코멘트 + retrofit 이슈로. 정당한 예외는 **근거 주석+이슈 링크**로 `[B]` 통과(escape hatch — 근거 없는 위반만 반려).

**공통**
- [ ][B] 신규/변경 외부 입력(파라미터·경로 세그먼트·gRPC 메타데이터·프레임)에 경계 구문 검증(길이·문자집합·형식) + 도메인 타입화 (P1)
- [ ][B] 신규 상태 저장(맵·캐시·세션·레지스트리)에 상한 + 제거 경로(eviction/TTL/명시 해제) 동반 (P2)
- [ ][B] 신규 수신 경로의 페이로드 크기 상한 명시 — 런타임 기본값 암묵 의존 금지 (P2/P5)
- [ ][B] 리소스 접근 신규 엔드포인트/RPC에 인가 배선(ADR-0014), 내부 전용이면 신뢰 경계 주석+이슈 (P3)
- [ ][B] 에러 응답·close 사유로 서버측 기대값·바인딩을 재구성 가능한 에코백 없음(값의 출처 무관) · 스택/설정/버전 노출 없음 (P4)
- [ ][B] `security.md` 전역 금지 위반 없음 — 하드코딩 시크릿·문자열 연결 쿼리·평문/약한 해시 비밀번호·PII/토큰 로깅 (위임 집행)
- [ ][B] 무한 성장 가능 대상의 신규 조회에 페이지/상한 (P2)
- [ ][A] 커넥션·세션·스트림 동시성 캡 검토 — 정량은 SDD §15(M3 부하 검증) 추적 (P2/P5)

**Java/Spring**
- [ ][B] WS Origin 와일드카드 없음 — 화이트리스트 또는 근거 주석+이슈 (P5)
- [ ][B] WS 프레임/버퍼 상한·세션 idle timeout 명시 설정 (P2)
- [ ][B] 신규 unary gRPC 호출에 deadline 명시 — 장수 bidi 스트림은 예외(keepalive로) (P5)
- [ ][A] 채널 keepalive·재연결 정책 명시 · dev 크리덴셜/평문은 프로파일 분리 + 근거 (P5)

**Rust**
- [ ][B] tonic 서버 인바운드 크기 상한(`max_decoding_message_size`) 명시 (P2/P5)
- [ ][B] 무상한 컬렉션에 삽입하는 신규 경로 없음 — 상한 검사(초과 = `resource_exhausted`) 동반 (P2)
- [ ][A] 바인드 주소·`concurrency_limit`·timeout 명시 — 무제한은 근거 주석+이슈 (K8s에선 0.0.0.0 바인드가 정상이라 문맥 판단) (P5)
- [ ][A] 내부 전용 RPC에 신뢰 경계 주석(mTLS/NetworkPolicy 전제 — M5) (P3)

> `[B]`는 전부 "배포 시 사고로 직결되는 결함"(DoS 벡터·인가 부재·정보 노출·전역 금지)에, 로컬 개발 현실과 절충이 필요한 항목은 `[A]`+추적에 있다.

---

## 게이트 배선 (활용 강제)

`code-review.md` 크래프트 렌즈(🦀 rust-expert / ☕ java-expert)가 이 체크리스트도 실행. `[B]` 위반=반려(escape hatch: 근거 주석+이슈 링크 — 예: `// MVP 로컬: 평문 채널, mTLS는 M5 #NN`). 인프라 레이어(🔒 렌즈)와 이중 지적 시 앱 코드 소견이 이 표준 기준. 새 함정은 `review-gaps.md` → 이 문서 체크리스트로 승격(gap→standard loop).

### 자동 스캔 게이트(gitleaks/audit류) — 배선의 완료 조건 (2026-07-17 학습)

**완료 조건은 "워크플로 파일 존재"가 아니라 "모든 트리거가 green"이다.** red가 상시화된 게이트는 배선 안 한 것보다 나쁘다 — 신호가 죽어 진짜 유출을 덮는다.

- MUST **트리거별 스캔 범위 차이를 확인**한다 — gitleaks-action: `push`=마지막 커밋만(`--log-opts=-1`) / `schedule`·`workflow_dispatch`=전체 히스토리. **push green이 전체 히스토리 red를 은폐**한다(실증: controller 주간 red가 최초 실행부터 2주간 미발견). `workflow_dispatch`를 배선해 주 1회를 기다리지 말고 즉시 검증한다.
- NEVER **오탐 억제를 커밋 SHA에 핀하지 않는다** — gitleaks fingerprint는 `<commit>:<path>:<rule>:<line>`이라 **squash 머지의 SHA 재작성에 즉사**한다(실증: backend PR #7 → PR green/main red = 게이트 false pass). `.gitleaksignore`는 공식 문서상 *experimental*. 억제는 `.gitleaks.toml` allowlist로.
- NEVER **경로 통째 허용(blanket)** — `condition="AND"`로 경로 + 값/모양까지 좁힌다. 오탐이 난 파일이 오히려 진짜 시크릿이 붙을 위험이 큰 파일일 수 있다(예: `JwtKeys.java`).
- MUST **억제 후 대조군으로 "룰이 죽지 않았음"을 증명**한다 — 허용 경로에 **진짜 시크릿을 심어 발화하는지** 확인(확인 후 반드시 제거). 억제가 룰 자체를 무력화하면 "no leaks found"는 거짓 안심이다.
- MUST **CI와 동일 버전 바이너리로 로컬 재현** — 기능이 버전에 종속된다(예: allowlist `targetRules`는 **8.25.0 신설** — `action@v3`가 해소하는 8.24.3엔 없다). 버전 확인은 실행 로그의 `gitleaks version:` 줄.
- MUST 억제 엔트리마다 **"왜 오탐인가" 1줄** — 억제는 리뷰 대상이다. 스캐너에 맞춰 프로덕션 코드·문서를 비트는 것은 반려(`clean-code.md`).
- MUST **제출형 의존성 그래프(Dependency Submission) 알림은 SBOM 실버전으로 트리아지**한다 — Dependabot이 **manifest 파일** 기반이면 버전 상향 시 자동 해제하지만, **제출형 스냅샷** 알림은 실 해석이 패치 버전으로 올라가도 **자동 해제되지 않는다**(GitHub 한계). 오래된 스냅샷이 SBOM에 잔존해 오탐 red를 상시화한다(실증: backend `commons-lang3` 3.16.0 스테일 — 실 해석은 전 구성 3.20.0, 알림 2주 방치). 트리아지: `gh api .../dependency-graph/sbom`으로 **실제 해석 버전 확인** → `./gradlew :m:dependencies`로 취약 버전이 "최종 해석 노드"인지 검증(‘requested X→Y’ 업그레이드 표시와 구분) → 미사용이면 `inaccurate`로 dismiss + 근거 코멘트. 실 취약이면 constraint/BOM으로 상향.

---

## 부록 — 엔진 적용 시연 (loop 증명, 게이트 시뮬레이션 2026-07-03)

crdt-engine HEAD `0355a58`의 `src/` 3파일을 "diff가 신규 작성한 코드"로 간주하고 rust-expert가 이 표준+`design-patterns.md` 체크리스트를 실행한 결과:

```
[B] fire (배포 시 사고 직결 — retrofit plan 원천):
  P1  DocId 무검증 경계 변환          engine.rs:39-49 + service.rs:127-133 (gRPC 메타데이터 신뢰)
  P2  open() 삽입-only·상한/제거 없음  engine.rs:109-123 (remove/evict 전무 = 메모리 DoS)
  P2  수신 크기 상한 미설정            main.rs:23-24 (tonic 4MB 기본값 암묵 의존)
  P3  무인가 RPC·신뢰 경계 주석 없음   service.rs:71(Sync)·107(GetSnapshot)
  P4  doc-id mismatch 에코백           service.rs:193 (서버측 stream 바인딩 재구성 가능)
  DP  ServerFrame 수동 조립 4곳        service.rs:149·204·235·246 (상호배타 미강제)
[A] fire: 세션/커넥션 캡 없음(main.rs:23 + service.rs:91) · concurrency_limit/timeout 미명시 · 신뢰 경계 주석
오탐 0: thiserror·DashMap 샤딩·바운디드 채널(FANOUT 256>OUTBOUND 64)·DocId newtype 존재·unwrap 0건 — 전부 미발화
```

시뮬레이션이 교정한 표준 문구 2건: ① design-patterns A2 — 교체점은 ADR 원문 seam으로 특정(레지스트리 trait 강제는 오지목·과설계였음, ADR-0013 실제 seam = 엔진→doc-service 아웃바운드) ② "실패 가능 변환"→"검증 필요 변환"으로 트리거 재정의. → **escape hatch("근거 주석+이슈 링크")도 실효 검증**: `DocId` 주석은 근거는 있으나 이슈 링크가 없어 정발화 = 요건이 실제로 일함.

---

## 출처

- 표준: [OWASP ASVS 4.0 — V4 접근 통제·V5 입력 검증](https://owasp.org/www-project-application-security-verification-standard/) · [OWASP Cheat Sheet — DoS·WebSocket·Error Handling](https://cheatsheetseries.owasp.org/) · [CWE-770 — Allocation of Resources Without Limits](https://cwe.mitre.org/data/definitions/770.html)
- 기술 사실(검증 2026-07-03): [gRPC deadlines — 기본 deadline 없음](https://grpc.io/docs/guides/deadlines/) · [tonic — 디코딩 기본 4MB](https://docs.rs/tonic/latest/tonic/server/struct.Grpc.html) · [Tomcat WebSocket — 버퍼 기본 8192B](https://tomcat.apache.org/tomcat-11.0-doc/web-socket-howto.html) · [Spring WebSocket — 기본 same-origin](https://docs.spring.io/spring-framework/reference/web/websocket/server.html)
- 내부: `security.md`(전역 금지 SSOT) · [ADR-0014](../../docs/adr/0014-auth-authz-boundary.md)(인가 경계) · [ADR-0013](../../docs/adr/0013-snapshot-persistence-lifecycle.md)(eviction 선행 조건)
