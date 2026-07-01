---
paths:
  - "**/*.rs"
  - "**/*.java"
---

# 동시성 표준 (언어 무관 원칙 + 언어별 관용구)

> **위상**: 프로젝트 전체·언어 공통 엔지니어링 표준. 개인 컬렉션(`ress-claude-agents`)으로 승격.
> **왜 있나**: "대규모 트래픽 고려"라고 써놓고 전역 락으로 직렬화되는 코드가 나온다(엔진 `Arc<tokio::sync::Mutex<HashMap>>` 사례). 아는데 안 쓴 것 → 체크리스트로 강제한다.
> **두 번째 표준(2026-06-30)** — 틀은 `error-handling.md`와 동일. 다음 = layering-readability.

---

## 원칙 (P) — 언어 무관

**P1. 공유 가변 상태를 최소화한다.** 불변(immutable) + 스레드 국한(confinement)을 우선. 공유가 불가피할 때만 락. 공유 자체가 병목·버그의 근원.

**P2. 락은 좁게·짧게.** 자료구조 "전체"가 아니라 "필요한 항목"만 잠근다. 임계구역은 최소.

**P3. 락 보유 중 대기/블로킹/외부호출 금지.** 락 쥔 채로 `.await`·I/O·네트워크·외부 시스템 호출 금지. → 데드락(Rust)·VT pinning(Java)·커넥션 풀 고갈의 원인.

**P4. 컬렉션 전체 락 대신 샤딩된 동시성 자료구조.** `HashMap`+전역 락 ❌ → 버킷 단위로 쪼갠 동시성 맵(Rust `DashMap` / Java `ConcurrentHashMap`). **두 언어 같은 교훈.**

**P5. 락 도구를 워크로드에 맞춘다.** CPU-bound·`await` 없는 짧은 임계구역 = **동기 락**. `await`를 임계구역 안에서 해야만 = **비동기 락**. 오용(동기 작업에 async 락) 금지.

**P6. 공유보다 소유 이전을 우선 검토.** 락으로 상태를 공유하기 전에 — **메시지 패싱/Actor**(단일 태스크가 상태를 소유, 밖에서는 채널로 요청)를 고려. 락 없는 구조가 더 단순하고 빠를 때가 많다.

**P7. 백프레셔는 설계에 내장.** 무한 버퍼 금지 — bounded 채널/세마포어로 느린 소비자에 자연 역압.

---

## Rust 실현 (tokio)

**P5 — 락 종류 선택 (tokio 공식 기준):**
```
임계구역 안에서 .await 하나 ?
  ├─ 아니오 (데이터만·CPU-bound·짧음)  → std::sync::Mutex 또는 parking_lot::Mutex (더 빠름)
  └─ 예 (임계구역 안에서 반드시 await)  → tokio::sync::Mutex
```

**P3 — 락 보유 중 `.await` 금지 (치명적).**
```rust
// ⚠️ 일부 MutexGuard는 Send라 "컴파일은 되는데 데드락" — 컴파일러가 안 막아줌
let g = data.lock();          // 동기 락
something_async().await;      // 🚨 락 쥔 채 await → deadlock 위험
// 규칙: 락은 non-async 메서드 안에서만 걸고 풀어라(구조체로 감싸기)
```

**P4 — 전역 Map 락 → 샤딩.** (엔진 `DocRegistry`의 정확한 처방)
```rust
// ❌ 현재: 문서 A 편집이 문서 B를 막음 (전역 직렬화)
docs: Arc<tokio::sync::Mutex<HashMap<String, DocEntry>>>

// ✅ 샤딩: 문서별 독립 락. 게다가 apply는 CPU-bound(await 없음) → 동기락
docs: Arc<DashMap<String, Arc<parking_lot::Mutex<DocEntry>>>>
//        └ 버킷 단위 동시 접근        └ 항목별 짧은 동기 락
```

**P6 — 궁극: Actor(락 프리).** `Doc` 하나당 단일 태스크가 소유, 외부는 `mpsc`로 메시지만 전달 → 락 자체가 없어지고 lost-update도 원자적. (엔진 Level-2 리팩터, 벤치 방법론 §5)

**P7 — bounded 채널.** `broadcast`/`mpsc` 용량 명시 + `Lagged`/`full` 정책 정의. (엔진은 이미 준수: FANOUT=256 > OUTBOUND=64 2단 백프레셔)

---

## Java 실현

**P1 — 불변 + 스레드 국한 우선.** 공유 가변 필드 최소화, `record`/불변 객체, `final`. 공유가 필요하면 `java.util.concurrent`.

**P4 — `ConcurrentHashMap` (전체 락 금지).**
```java
// ❌ Collections.synchronizedMap → 맵 전체 락 (DashMap 없는 Rust 전역락과 같은 병목)
// ✅ ConcurrentHashMap → 버킷 단위 락, 다른 키 동시 접근
private final Map<String, Room> rooms = new ConcurrentHashMap<>();
```

**P3 — VT pinning·락 중 I/O 금지 (게이트웨이 직결).**
- `synchronized` 블록 안에서 blocking I/O 하면 VT가 OS 스레드를 pin(JEP 491로 완화됐지만 원칙은 유효). → **자주·오래 I/O를 감싸는 `synchronized`는 `ReentrantLock`으로**, 또는 락 밖에서 I/O.
- 락 보유 중 외부 호출(HTTP/DB/gRPC) 금지 — 커넥션 풀 고갈.

**P7 — 세마포어 백프레셔.** VT는 task당 생성(풀링 금지), 동시성 상한은 `Semaphore`로. (기존 SDD §3.1 규칙과 일치)

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3에서 `rust-expert`/`java-expert`가 실행. **[B]=blocking, [A]=advisory.**

**공통**
- [ ][B] 락 보유 중 `.await`/블로킹 I/O/외부호출 없음 (P3)
- [ ][B] 컬렉션 전체 락 대신 샤딩 동시성 맵 (DashMap/ConcurrentHashMap) — 핫패스일 때 (P4)
- [ ][A] 공유 가변 상태 최소화(불변·confinement 우선), Actor/메시지 패싱 검토했나 (P1/P6)
- [ ][A] 무한 버퍼 없음 — bounded 채널/세마포어 백프레셔 (P7)

**Rust**
- [ ][B] `await` 없는 CPU-bound 임계구역에 `tokio::sync::Mutex` 오용 없음 → 동기락(std/parking_lot) (P5)
- [ ][B] 핫패스 전역 `Mutex<HashMap>` 없음 → DashMap 샤딩 or 근거 주석+이슈 링크 (P4)
- [ ][A] 락은 non-async 메서드 안에서만(구조체 캡슐화) (P3)

**Java**
- [ ][B] `synchronizedMap`/맵 전체 락 대신 `ConcurrentHashMap` (P4)
- [ ][B] 락/`synchronized` 안에서 I/O·외부호출 없음 (VT pinning·풀 고갈) (P3)
- [ ][A] VT 풀링 금지 + `Semaphore` 동시성 상한 (P7)

---

## 게이트 배선 (활용 강제)

`code-review.md`의 크래프트 렌즈(🦀 rust-expert / ☕ java-expert)가 이 체크리스트도 함께 실행. `[B]` 위반=반려. 새 함정은 `review-gaps.md` → 이 문서로 승격.

**escape hatch (P4 등)**: "MVP라 전역락"이 정당한 경우 → **근거 주석 + 이슈 링크**(`// MVP: 단일인스턴스, 샤딩은 #NN`)가 있으면 `[B]`를 통과 처리. 근거 없는 전역락만 반려. (blocking을 "기능 결함"에, 관용구 권장을 advisory에 두는 D-경계와 일치)

---

## 부록 — 엔진 코드 적용 시연 (loop 증명)

`src/engine.rs` `DocRegistry`에 체크리스트 적용:
```
[B] Rust P4: 핫패스 전역 Mutex<HashMap> → 문서 간 직렬화. 근거 주석·이슈 없음 → 반려
             처방: Arc<DashMap<String, Arc<parking_lot::Mutex<DocEntry>>>>
[B] Rust P5: apply_v1 임계구역에 .await 없음(순수 CPU) → tokio::sync::Mutex 오용 → 동기락
[✅] 공통 P3: 락 보유 중 .await 없음 (코드가 이미 지킴 — "락 중 .await 금지" 주석 존재)
[✅] Rust P7: FANOUT 256 > OUTBOUND 64 2단 백프레셔 — 준수
```
→ 기존 "코드리뷰 8건"이 놓친 **P4/P5 두 blocking**을 이 체크리스트가 잡음. 벤치 방법론 §5(Tier2)가 이 수정의 "N배"를 측정.

---

## 출처

- Rust: [Tokio — Shared state](https://tokio.rs/tokio/tutorial/shared-state) · [tokio::sync::Mutex 문서](https://docs.rs/tokio/latest/tokio/sync/struct.Mutex.html) (동기락 vs async락, await-across-lock 경고) · [Async Rust Mutex vs Lock-Free](https://rust-dd.com/post/async-rust-mutexes-vs-lock-free)
- Java: [Baeldung — Concurrency Pitfalls](https://www.baeldung.com/java-common-concurrency-pitfalls) · [JEP 491 — VT without pinning](https://openjdk.org/jeps/491) · [Oracle — Virtual Threads](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)
