---
date: 2026-08-07
slug: m3-presence-multiinstance
status: planned
related:
  - adr/0011-engine-sync-fanout-bridge.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0007-istio-ambient.md
  - design/crdt-engine.md
  - sdd/3-data-sync-ai-auth.md
  - sdd/5-project-milestones-guardrails.md
  - plans/2026-08-03-m5-infra-observability-stub.md
  - status/dod-tracker.md
---

# M3 — Presence + 멀티인스턴스 확장

> **DoD #3**: "타 사용자 커서·선택이 실시간 표시된다"
> **NFR**: p95 수렴 < 100ms @ 50 clients · 동시 WS ~수천 · VT saturation 미발생
>
> M2가 "문서가 살아남는다"였다면 M3는 **"여러 사람이 서로를 본다 + 서버가 늘어난다"**다.

---

## Context

### 현재 상태 (실측 2026-08-07)

**게이트웨이는 룸 개념이 없는 순수 1:1 브리지다.** WS 세션 하나 = 엔진 `Sync` bidi 스트림 하나.

| 구성요소 | 현황 | 위치 |
|---|---|---|
| 세션 보유 | `Map<String sessionId, SessionBridge>` — **키가 sessionId, doc_id 역인덱스 없음** | `DocWebSocketHandler:56` |
| fan-out | **게이트웨이에 없음.** 엔진이 per-doc `tokio::broadcast`로 수행 | engine `doc.rs:177` (`DocEntry::new`) |
| awareness | messageType 상수(`MESSAGE_AWARENESS=1`)는 있으나 **전부 drop** | `YProtocolCodec:38` (`!= MESSAGE_SYNC` → empty) |
| Redis | **전 스택 부재** (gateway·engine 양쪽 의존성 없음) | — |
| doc-id 라우팅 키 | ✅ **이미 gRPC 메타데이터로 전달 중** (`doc-id`, `role`) | `EngineClient:64~66` |
| 세션 캡·백프레셔 | **없음.** 프레임 크기·idle timeout만 존재 | `WebSocketConfig:28~38` |
| 엔진 per-doc 세션 캡 | 없음 — 코드 주석에 "M3 몫"으로 명시 | engine `main.rs:72~77` |
| 엔진 self-echo 필터 | **없음** — 송신자도 자기 update를 되받는다. 낭비는 **룸 전체 fan-out의 1/N**(N=편집자 수)이며 "2배"가 되는 건 N=1일 때뿐이다. ADR-0011이 M1.5로 잡았으나 미구현 | engine `doc.rs:503` 주석 |
| yrs GC/컴팩션 | **미도입** — `Doc::new()` 기본 옵션, `Options`/gc 코드 0건 | engine `doc.rs:179` |

> 라인 번호는 **2026-08-07 실측 ✅**(4레포 워킹트리 기준). 서비스 레포가 앞서 나가면 어긋나므로,
> 인용을 옮길 때 `rg`로 심볼을 다시 잡을 것 — 라인이 아니라 **심볼이 SSOT**다.

재사용 가능한 자산: `RoomId` value type · `SessionRole` · `Lib0` varUint 코덱 · awareness messageType 상수 · `SessionMetrics` 계측 패턴 · `GatewayLogEvent` 구조화 로깅 taxonomy.

### 핵심 판단 3건

#### 판단 1 — awareness는 엔진을 통과하지 않는다 (SDD §6.1 유지)

| 경로 | 장점 | 단점 | 판정 |
|---|---|---|---|
| **A. Gateway ↔ Redis pub/sub** (SDD §6.1) | proto 무변경 · 엔진 CPU 보호 · I/O는 I/O 서비스가 · (서버측 presence 조회로 확장 가능 — M3는 미사용, §3.1) | Redis 인프라 신규 · 게이트웨이에 룸 인덱스 필요 | **채택** |
| B. 엔진 broadcast 재사용 | 인프라 0 · 룸 인덱스 불요(엔진이 이미 함) | **proto 변경 필수**(ClientFrame/ServerFrame에 awareness 필드 → 가드레일 1 전 사이클) · CPU 바운드 엔진이 휘발 릴레이를 짐 · **실패 도메인이 문서 sync와 한 몸** | 기각 |

결정 근거의 핵심은 **실패 격리**다. awareness가 엔진 `Sync` 스트림을 타면 그 경로의 문제(플러딩·손상 프레임·버퍼 포화)가 **문서 편집과 운명을 공유한다.** 분리해 두면 §3.4의 fail-open이 성립한다 — Redis가 죽어도 커서만 사라지고 편집은 계속된다. 부가 기능이 핵심 기능을 끌어내릴 수 없게 만드는 것이 이 선택의 값이다.

여기에 proto 무변경(가드레일 1의 4단계 사이클을 안 밟는다)과 엔진 스코프 보존(가드레일 5)이 더해진다. awareness는 커서 이동마다 발생해 초당 수십 프레임이 나므로, CPU 바운드 엔진의 머지 핫패스에 얹을 트래픽이 아니다.

> ⚠️ **원래 여기 있던 근거("presence는 상태 집합을 요구하므로 Redis Hash가 필요하다")는 폐기했다.**
> Phase 3이 저장 키 0개로 정리되면서(§3.1) 양쪽 다 상태를 읽지 않게 됐다 — 그 논거는 A/B를
> 가르지 못한다. **결정은 유지되지만 이유가 바뀌었다**는 사실을 남긴다. 다음에 이 결정을 재검토할
> 사람이 "집합 조회" 논거의 허구를 발견하고 결정 자체를 뒤집는 일을 막기 위해서다.

> 귀결: **presence 트랙(Phase 1~3)은 proto 무변경**이다. `proto-v0.2.0` 유지 · 다운스트림 `PROTO_REF` bump 불요.
>
> proto를 건드릴 후보는 둘뿐이며 둘 다 M3 후반이다:
> - **Phase 4E** 증분 저장 — 저장 단위가 바뀌면 `SaveSnapshot` 계약과 ADR-0013 개정 동반
> - **Phase 7** 핸드오프 — 엔진 드레인 신호가 SIGTERM으로 부족할 경우
>
> 즉 M3는 "**proto 무변경으로 시작해 필요가 증명되면 한 번 bump**"하는 형태다. bump가 생기면 가드레일 1(controller SSOT → `buf breaking` → 다운스트림 ref bump → 3언어 재생성)을 그대로 밟는다.

#### 판단 2 — **M3 범위에서** 문서 sync는 Redis가 필요 없다

이게 SDD·설계서가 흐릿하게 남긴 지점이다. consistent-hash가 **같은 doc = 같은 엔진 인스턴스**를 보장하는 순간, 게이트웨이가 몇 대든 그 doc의 모든 세션은 같은 엔진의 같은 broadcast 채널에 모인다. 즉 **문서 sync의 크로스-게이트웨이 전파는 이미 해결돼 있다** — 코드를 한 줄도 안 써도 된다.

```
gateway-1 ─┐
gateway-2 ─┼─→ (consistent-hash by doc-id) ─→ engine-A: doc X의 broadcast 허브
gateway-3 ─┘                                  └─ 모든 게이트웨이의 doc X 세션이 여기 모인다
```

따라서 **M3 범위에서** Redis의 유일한 용도는 **awareness**다. 세 문서를 정정해야 한다:
- SDD §6.3 "WS Gateway: 무상태, 크로스-인스턴스 전파는 Redis pub/sub" → **awareness 한정**임을 명시
- SDD §6.2 신규 접속 시퀀스 마지막 줄 "이후: update가 bidi 스트림으로 양방향 흐름 **+ Redis fan-out**" → 문서 update는 Redis를 경유하지 않는다. 삭제
- `design/crdt-engine.md` §6 "멀티인스턴스 fan-out: **Redis pub/sub** 크로스 인스턴스 **+** docId consistent-hash" → 둘은 **대안이지 보완이 아니다**. consistent-hash를 택했으므로 **엔진은 Redis를 쓰지 않는다**

> ⚠️ **"유일한 용도"에 예외가 하나 있고, 그건 M3 밖이다.** SDD §6.3이 별도로 배정한
> **"무손실(Redis 버퍼) = M5"** — 인스턴스 전환 중 in-flight update를 잃지 않기 위한 버퍼다
> (설계서 부록A-2의 질문 "리밸런싱 중 그 doc의 in-flight update는 어디로 가나"와 같은 것).
> 이것은 awareness pub/sub과 **다른 Redis 용도**이며, 이 plan은 그것을 구현하지 않는다.
> Phase 7이 그 지점(3→4 사이 in-flight update의 운명)을 **설계 미결 질문으로만** 든다.
>
> **문서 간 불일치 1건 — C11에서 정리**: `status/current.md` §다음 액션 6이 "Redis 버퍼 복원 설계"를
> **M3 진입 준비**로 드는데 SDD §6.3은 **M5**로 배정한다. 이 plan은 SDD(M5)를 따른다 —
> 무손실 버퍼는 핸드오프 **구현**과 한 몸이고 그 구현이 M5이기 때문이다. current.md 쪽을 정정한다.

#### 판단 3 — consistent-hash 검증은 Istio 없이 한다

**주된 이유는 순환 의존이 아니라 "게이트웨이 설계가 걸린 미검증 가정"이다.**

**게이트웨이는 모든 세션이 단일 `ManagedChannel`을 공유한다**(`EngineClient:48`). 단일 HTTP/2 커넥션이 한 업스트림에 고정되면 doc별 분산이 **무력화된다**. L7 프록시가 HTTP/2 **스트림 단위**로 라우팅해주는 것이 전제인데, 이 전제는 **실측 전까지 가정일 뿐이다.** 깨지면 필요한 대응은 인프라가 아니라 **게이트웨이 코드 변경**(doc별 채널 분리 등)이다 — 즉 이 검증 결과가 backend 설계를 바꿀 수 있다. 그런 발견은 M5 인프라 작업 *전에*, 그리고 Phase 3~4의 게이트웨이 작업과 같은 시기에 나와야 한다.

**해소 수단**: **standalone Envoy를 로컬 해시 라우터로 쓴다.** `ring_hash` LB + `doc-id` 헤더 hash policy는 waypoint가 쓰는 것과 동일한 Envoy 기능이다. 엔진 2 인스턴스를 띄워 계약을 실측하고, M5는 같은 의미의 `DestinationRule`로 갈아끼운다.

부수 효과로 순환도 풀린다 — 다만 **그 순환은 원래도 약했다**:
- M5 stub §선결조건: "**M3 완료** (consistent hash 라우팅 = waypoint 설정의 전제)"
- M3의 라우팅 = Istio **waypoint**가 수행 (ADR-0007) → M5 인프라 필요
- 그러나 같은 stub이 이미 탈출구를 둔다: "**또는 M3/M4 없이 2-hop(Java→Rust) 부분 배포로 시작 가능**"

즉 M5는 M3 없이도 착수할 수 있었고, 막혀 있던 건 M5 전체가 아니라 **waypoint hash 설정 한 조각**이다. Envoy standalone은 그 조각의 값을 M5보다 먼저 확정해준다.

---

## Phase 구조

| Phase | 내용 | 레포 | 산출 게이트 |
|---|---|---|---|
| **1** | 게이트웨이 룸 인덱스 + awareness 릴레이 + join 시 queryAwareness 발신 (단일 인스턴스) | backend | awareness가 같은 룸 세션에 전달 + 신규 접속자가 **즉시** 기존 커서 수신 |
| **2** | 프론트엔드 커서·선택 UI | frontend | **DoD #3 클로즈** |
| **3** | Redis pub/sub 크로스 게이트웨이 (**저장 키 0개**) | backend | 게이트웨이 2대에서 커서 상호 표시 + join 즉시 원격 peer 발견 |
| **4** | 자원 상한·백프레셔 정량화 | backend + engine | SDD §15 "세션/커넥션 캡 정량화" 클로즈 |
| **4E** | 엔진 증분 저장·GC (스냅샷 크기 절벽 해소) | engine | 대형 문서의 영속화 비활성 제거 |
| **5** | consistent-hash 라우팅 검증 (Envoy standalone) | controller + backend | SDD §15 "consistent hash 키 전달 상세" 클로즈 |
| **6** | 부하 하니스 + NFR 측정 | controller | **NFR 3행 클로즈** + 엔진 상한 5종 정량화 |
| **7** | 샤드 리밸런싱/핸드오프 설계 | controller | ADR 신설, 구현은 M5 |

Phase 1→2가 먼저인 이유: **기능을 먼저 증명하고 나중에 확장한다.** DoD #3은 단일 인스턴스로 달성 가능하므로, 스케일 작업(3~6)에 Redis·Envoy·k6를 쌓기 전에 "커서가 보인다"는 사실을 확보한다.

**4E는 presence 트랙(1~3)과 독립이다** — 엔진 영속화 트랙이라 병렬 진행 가능하다. 엔진 코드가 스스로 M3로 지정한 부채이며(`save.rs:31`), Phase 6 부하 측정 전에 끝나 있어야 대형 문서 시나리오를 측정할 수 있다.

⚠️ **단 4E는 Phase 4와는 독립이 아니다.** Phase 4의 문서 eviction은 "durable한 문서만 내린다"가 조건인데, 4E 이전에는 `MAX_SNAPSHOT_BYTES` 초과 문서가 `Persistence::Disabled`라서 **영원히 evict 불가**다. 즉 4E 없이 eviction만 넣으면 **메모리를 가장 많이 먹는 문서만 골라서 못 내린다**(§Phase 4). 순서는 `4E → 4의 eviction 활성화`가 이상적이고, 뒤집으려면 eviction의 커버리지가 부분적임을 받아들여야 한다.

---

## Phase 1 — 게이트웨이 룸 인덱스 + awareness 릴레이

### 1.1 최대 위험: WS 단일 writer 불변식 붕괴 (실측 확인 ✅)

현재 `DocWebSocketHandler`의 동시성 계약(§D-6)은 **"세션당 writer는 gRPC 응답 콜백 하나뿐"**에 의존한다. 그래서 `ConcurrentWebSocketSessionDecorator`를 쓰지 않는다 — 클래스 주석에 "위반 시 감싸야 한다"고 예고만 돼 있다.

awareness fan-out은 이 불변식을 **정면으로 깬다**: 다른 세션의 인바운드 스레드가 내 세션에 쓴다.

```
현재:  [세션 A의 gRPC 응답 콜백] ──write──▶ 세션 A          (writer 1개)
M3:    [세션 A의 gRPC 응답 콜백] ──write──▶ 세션 A
       [세션 B의 인바운드 스레드] ──write──▶ 세션 A          (writer N개 ← 동시 send)
```

처방: **핸드셰이크 시 `ConcurrentWebSocketSessionDecorator`로 감싼다.** Spring 제공 클래스로 send를 큐잉·직렬화하고 `sendBufferSizeLimit`·`sendTimeLimit` 초과 시 세션을 끊는다. 이것이 동시에 Phase 4의 송신 큐 백프레셔이기도 하다 — **Phase 1에서 도입하고 Phase 4에서 수치를 정량화**한다.

> 이 항목을 Phase 1의 첫 커밋으로 둔다. 나중에 붙이면 그 사이 모든 fan-out 코드가 미검증 동시성 위에 쌓인다.

### 1.2 룸 인덱스 — best-effort로 충분하다

> **선행 해명 — ADR-0011이 기각한 바로 그 형태다.** ADR-0011 §축1은 "게이트웨이 세션 그룹 fan-out"을
> 두 사유로 기각했다: ① 게이트웨이가 상태 보유(가드레일 5 위배) ② **멀티인스턴스서 깨짐**.
> `RoomRegistry`는 외형상 그 기각안이므로, **왜 모순이 아닌지를 여기서 못 박는다.**
>
> - **①은 발화하지 않는다.** 기각 사유의 "상태"는 *문서 sync의 권위*다. awareness는 권위가 아니라
>   **휘발 릴레이**이고, 문서 sync의 fan-out은 이 plan에서도 **엔진 broadcast가 그대로 유지**한다
>   (판단 2). 게이트웨이는 awareness 페이로드를 해석하지도 보관하지도 않는다(§1.3).
> - **②는 그대로 적용된다.** 룸 인덱스는 인스턴스 로컬이라 게이트웨이 2대에서 즉시 깨진다.
>   이 plan은 그것을 부정하지 않고 **Phase 3(Redis pub/sub)에서 해소한다** — Phase 1의 단일 인스턴스
>   제약은 알려진 한계이지 간과가 아니다.
>
> 부수 정정: ADR-0011 §범위(line 6)가 awareness를 "M1.5/M5"로 배정한 것은 **stale**이다
> — DoD #3의 소유 마일스톤은 M3다(`status/dod-tracker.md`). C2에서 정정한다.

```java
/// doc_id → 그 룸에 접속한 세션 id 집합. awareness fan-out의 대상 조회용.
/// bridges(sessionId→SessionBridge)의 역인덱스이며, 두 map의 정합성은 best-effort다.
final class RoomRegistry {
    private final Map<RoomId, Set<String>> sessionsByRoom = new ConcurrentHashMap<>();

    void join(RoomId room, String sessionId) { ... }   // bridges.put 직후
    void leave(RoomId room, String sessionId) { ... }  // bridges.remove 직후, 빈 집합은 제거
    Set<String> sessionsIn(RoomId room) { ... }        // 불변 스냅샷
}
```

`bridges`를 2단 map(`RoomId → sessionId → Bridge`)으로 바꾸지 않는 이유: `handleBinaryMessage`의 `bridges.computeIfPresent` 원자성 패턴(§D-6)이 sessionId 단일 키에 의존한다. 2단으로 만들면 그 원자성 추론을 다시 세워야 하고, 얻는 것은 정합성 강화뿐이다.

그리고 **그 정합성은 필요하지 않다.** awareness는 휘발 데이터다 — registry에는 있으나 bridges에서 사라진 세션은 lookup이 null이면 skip하면 되고, 한 프레임 유실은 다음 커서 이동이 덮는다. 강한 정합성을 위해 락을 도입하는 것은 이 데이터의 성질에 과한 값을 지불하는 것이다.

> ⚠️ 반대로 **문서 sync에는 이 논리를 적용하지 말 것.** update 유실은 수렴을 깬다. sync 경로는 지금처럼 엔진 broadcast + `Lagged`→full resync가 담당한다.

### 1.3 코덱 확장 + **join 시 게이트웨이가 queryAwareness를 발신한다**

```java
/// awareness는 페이로드를 그대로 릴레이한다. 게이트웨이는 내용을 해석하지 않는다.
Optional<byte[]> decodeAwareness(byte[] wsMessage)   // messageType 1 → 원본 페이로드 바이트
byte[] encodeAwareness(byte[] payload)               // messageType 1 + varUint8Array
byte[] encodeQueryAwareness()                        // messageType 3 — **페이로드 없음**
```

`MESSAGE_AUTH(2)`는 계속 drop한다 — 인증은 핸드셰이크에서 끝났고 in-band auth 경로를 열 이유가 없다.

#### 신규 접속자가 기존 커서를 보는 방법 — 방향을 뒤집어야 한다

**클라가 보낸 queryAwareness를 릴레이하는 설계는 작동하지 않는다.** `y-websocket@3.0.0` 소스 실측(✅ 2026-08-07, `node_modules/y-websocket/src/y-websocket.js`):

| 지점 | 실제 동작 |
|---|---|
| `messageHandlers[messageQueryAwareness]` (`:53~68`) | 받으면 **자기가 아는 전체 awareness 상태**로 응답 ✅ |
| `websocket.onopen` (`:196~220`) | 보내는 것은 **SyncStep1 + 자기 로컬 awareness 하나뿐**(`[provider.doc.clientID]`) |
| queryAwareness 발신 (`:458~465`) | **BroadcastChannel(`bc.publish`)에만** — 같은 브라우저 탭 간 전용. **WS로는 나가지 않는다** |

⇒ 아무도 WS로 queryAwareness를 보내지 않으므로 **릴레이는 dead code**다. 릴레이만 넣으면 Phase 1에서 신규 접속자는 기존 peer가 *다음에 움직일 때까지* 그를 보지 못한다. 폴백은 `y-protocols/awareness.js`의 하트비트뿐인데(`:13,59~61,77` — `outdatedTimeout=30000`, 15초 경과 시 자기 상태 갱신, 3초 주기 체크) 그래서 **최악 ~15초의 유령 부재**이고, 그 사이 가만히 있는 peer는 존재조차 드러나지 않는다.

**처방 — 게이트웨이가 발신자가 된다.** 세션이 룸에 join하면:

```
join(room, newSessionId)
  → 게이트웨이가 room의 **기존** 세션들에게 encodeQueryAwareness() 전송
  → 각 peer의 messageHandlers[3]이 전체 상태를 messageAwareness(1)로 응답
  → 게이트웨이가 그 응답을 평소 릴레이 경로로 newSession에 전달
```

핸들러가 이미 등록돼 있으므로 클라이언트 변경이 없고, 게이트웨이는 여전히 페이로드를 해석하지 않는다(§1.2 해명과 정합). 상태 보관도 없다 — **peer들에게 되묻는 것**이지 캐시가 아니다.

> 이 발신은 §1.1의 동시성 문제를 정면으로 만든다 — join한 세션의 스레드가 **다른 세션들에게 쓴다.**
> `ConcurrentWebSocketSessionDecorator`가 Phase 1의 첫 커밋이어야 하는 이유가 여기서 한 번 더 확인된다.

대안(기각): 게이트웨이가 룸별 최신 awareness를 인메모리 캐시했다가 join 시 재생. **상태 보유가 생기고 그 상태를 채우려면 페이로드를 디코딩해야 한다** — §1.2 해명의 전제가 깨진다. peer들에게 되묻는 편이 싸고, 그 되묻기는 Phase 3에서 인스턴스 경계를 넘도록 확장된다(§3.2).

⚠️ **이 발신은 인스턴스 로컬이다.** 게이트웨이 2대에서는 다른 게이트웨이의 peer에게 닿지 않으므로, 그 확장이 **Phase 3 §3.2의 `awareness:query` 채널**이다. Phase 1이 닫는 것은 *단일 인스턴스에서의* join 시 peer 발견까지다 — 이 한계를 Phase 3로 넘기는 것이 §1.2 ②(멀티인스턴스서 깨짐)를 인정한 결과와 정확히 같은 지점이다.

### 1.4 self-echo 제외 · viewer 허용

- 발신 세션에게 자기 awareness를 되돌리지 않는다(`sessionsIn(room)` - senderId).
- **viewer의 awareness는 허용한다.** `isPermitted`는 `update` 페이로드만 막는다(문서 변경). 읽는 사람의 커서가 보이는 것은 정상 동작이며 viewer를 숨기는 것이 오히려 협업 맥락을 해친다. 이 결정을 코드 주석에 근거와 함께 남긴다.

### 1.5 잔여 리스크 — awareness 신원 위조 (문서화 후 수용)

awareness 페이로드는 클라이언트가 만든 `{name, color}`를 담는다. 게이트웨이가 내용을 해석하지 않으므로 **악의적 클라이언트는 남의 이름표를 달 수 있다.**

| 대응 | 비용 | M3 판정 |
|---|---|---|
| A. 클라 신뢰 + 문서화 | 0 | **채택** |
| B. 게이트웨이가 신원 필드를 stamp | awareness 페이로드 파싱·재작성(인코딩 결합) + 핫패스 비용 | 후속 |

근거: 영향 범위가 **이미 문서 접근 권한을 가진 멤버 사이의 이름표 혼동**에 국한된다. 데이터 유출·권한 상승이 아니다. 문서 접근 자체는 JWT + `CheckPermission`이 지키고 있다. B는 위조 시도를 관측할 필요가 생기면(메트릭에 이상 징후) 그때 도입한다.

### 1.6 관측

| 시그널 | 종류 | 용도 |
|---|---|---|
| `ws.awareness.relayed{}` | counter | 릴레이 처리량 |
| `ws.awareness.dropped{reason}` | counter | `unknown_type` / `session_gone` / `rate_limited`(P4) |
| `ws.awareness.query_sent{}` | counter | join 시 peer에 보낸 queryAwareness 수(§1.3) — 0이면 발신 배선이 죽은 것 |
| `ws.room.sessions` | gauge | 룸당 세션 수 분포 → Phase 4 캡 근거 |
| `ws.send.queue.exceeded{}` | counter | decorator 버퍼 초과 = 느린 클라이언트 |

---

## Phase 2 — 프론트엔드 커서·선택 UI

### 스택 (실측 ✅ 2026-08-07, `weDocs-frontend/package.json` + `node_modules`)

| 패키지 | 버전 | 역할 |
|---|---|---|
| `@tiptap/react` · `starter-kit` | 3.27.1 | 에디터 (ProseMirror 기반) |
| `@tiptap/extension-collaboration` | 3.27.1 | Yjs 문서 바인딩 — **이미 배선됨** |
| `@tiptap/y-tiptap` | 3.0.5 | `plugins/cursor-plugin.js` **export 확인** (y-prosemirror 계열) |
| `y-websocket` | 3.0.0 | provider — `src/page/Editor.tsx:51`에서 이미 생성 중 |
| `y-protocols` | 1.0.7 | awareness 프로토콜 |
| `yjs` | 13.6.31 | — |

두 가지가 이 확인으로 바뀐다:

1. **awareness는 "활성화"할 것이 없다.** `WebsocketProvider`가 내장 `awareness`를 이미 들고 있고 `Editor.tsx:51`가 그 provider를 생성한다. Phase 2의 실제 작업은 **로컬 상태 세팅 + 렌더링 플러그인 배선**이다.
2. **커서 플러그인은 의존성 추가를 동반한다.** Tiptap 3의 공식 경로인 `@tiptap/extension-collaboration-caret`은 **미설치**다. 선택지는 둘 — ⓐ 그 확장을 추가(공식·Tiptap 통합), ⓑ 이미 있는 `@tiptap/y-tiptap`의 `cursor-plugin`을 직접 배선(의존성 0, 배선 수동). **착수 시 ⓐ부터 검토** — 이미 `extension-collaboration`을 쓰고 있어 계열이 맞다.

### 작업

- `awareness.setLocalStateField('user', { name, color })` — 이름은 인증 세션에서, 색은 userId 해시로 결정론적 배정
- 커서·선택 렌더링 플러그인 배선 (위 ⓐ/ⓑ 판정 후)
- viewer 커서도 표시 (Phase 1.4 결정과 정합)
- **E2E: 2 브라우저 → 상호 커서·선택 표시** = DoD #3 검증증거
- **회귀 확인**: `Editor.tsx`의 StrictMode provider 라이프사이클 처리(`:28~35` 주석 — `useMemo` 금지, `useEffect`에서 생성)를 깨지 말 것. awareness 배선을 `useMemo`로 되돌리면 "closed before established" 재연결 루프가 재발한다.

프론트 E2E는 여전히 CI 밖이다(4프로세스 사전조건). 증거는 로컬 실행 + 스크린샷·로그로 남긴다.

---

## Phase 3 — Redis pub/sub 크로스 게이트웨이 (상태 없음)

### 3.1 채널 설계 — pub/sub 2개, 저장 키 0개

```
awareness:{docId}       {"origin": <instanceId>, "type": 1, "payload": <base64>}   awareness 릴레이
awareness:query:{docId} {"origin": <instanceId>}                                    join 시 peer 재질의
```

`origin`(인스턴스 ID)은 **자기 발행 에코 방지**용이다. 없으면 자기가 보낸 것을 다시 받아 무한 증폭한다.

> 🔴 **저장 키가 없다. 이것이 이 Phase의 핵심 설계 결정이며, §1.2의 무해석 불변식을 Phase 3까지 관통시킨다.**
>
> 초기 설계는 `presence:{docId}` Hash(`clientId → {state, seenMs}`)에 상태를 두려 했다. **기각했다** —
> 그 Hash를 채우려면 게이트웨이가 lib0 awareness 페이로드를 **디코딩해서 clientId별로 쪼개야** 한다.
> 그 순간 §1.3의 "게이트웨이는 페이로드를 해석하지 않는다"가 깨지고, 그걸 근거로 세운 §1.2의
> ADR-0011 기각사유① 무력화 논거도 함께 무너진다. §1.5가 옵션 B를 "파싱 비용"으로 기각한 것과도
> 모순된다 — 파싱을 이미 하고 있다면 그 기각 논거가 성립하지 않는다.
>
> **그리고 그 Hash는 애초에 필요하지 않다.** 아래 두 용도가 서버 상태를 요구하는 것처럼 보였을 뿐이다:
>
> | 용도 | 서버 상태 없이 해결되는 방법 |
> |---|---|
> | join 시 기존 peer 발견 | `awareness:query` 채널로 재질의 → peer들이 응답 (§3.2) |
> | 유령 커서 청소 | **클라이언트가 이미 한다** — `y-protocols/awareness.js:70`이 30초(`outdatedTimeout`) 무소식 remote peer를 `removeAwarenessStates(..., 'timeout')`로 제거한다(실측 ✅ 2026-08-07). 살아 있는 peer는 15초 자가 갱신(`:61`)으로 타임아웃되지 않는다 |
>
> 남는 용도는 서버측 "누가 접속 중" 조회(REST)뿐이고 그건 **§범위 밖**이다. 필요해지는 시점에
> Hash를 도입하면 되며, 그때는 파싱 비용을 **의식적으로** 지불하는 결정이 된다.

### 3.2 join 시 크로스 게이트웨이 peer 재질의

**§1.3의 발신은 인스턴스 로컬이다.** gateway-2에 붙은 신규 접속자는 gateway-1의 peer에게 queryAwareness를 보낼 수 없다. 그대로 두면 §1.3이 없애려던 **~15초 유령 부재가 멀티인스턴스에서 그대로 되살아난다.**

```
join(room, newSession) on gateway-2
  ├─ 로컬: room의 기존 세션에 queryAwareness 직접 전송            (§1.3, Phase 1)
  └─ 발행: publish(awareness:query:{docId}, {origin: gw-2})       (Phase 3 신규)
        └─ gateway-1이 수신 → origin≠자기 → 자기 로컬 세션들에 queryAwareness 전송
              └─ peer 응답이 awareness:{docId}를 타고 gw-2 → newSession
```

게이트웨이는 여전히 페이로드를 만들지도 읽지도 않는다 — `encodeQueryAwareness()`는 **페이로드가 없는** 타입 3 프레임이고(§1.3), 돌아오는 응답은 불투명 바이트로 릴레이된다.

⚠️ 응답이 **룸 전원에게** 간다(peer는 질의자를 모른다). N명 룸에 1명 붙으면 N개 응답 × N명 = N² 프레임이 순간 발생한다. 홈랩 규모(N≤50)에선 무해하지만 **Phase 4의 awareness coalescing이 이 버스트에도 걸리는지** 확인 대상이다.

### 3.3 구독 범위 — 들고 있는 룸만

룸의 첫 세션 join 시 두 채널 `subscribe`, 마지막 leave 시 `unsubscribe`. 모든 채널을 구독하면 게이트웨이가 자기와 무관한 문서의 트래픽을 전부 받는다.

### 3.4 실패 정책 — fail-open

**Redis가 죽으면 awareness만 degrade하고 문서 편집은 계속된다.** awareness 발행·구독 실패는 로그·메트릭만 남기고 세션을 끊지 않는다.

근거: 문서 sync 경로는 Redis를 경유하지 않는다(판단 2). awareness는 부가 기능이므로 그 장애가 핵심 기능을 끌어내리면 가용성 설계가 거꾸로 된 것이다. 이는 인증·인가의 fail-closed와 **의도적으로 반대**이며, 그 비대칭의 근거를 코드 주석에 남긴다.

**상태가 없으니 복구도 없다** — §3.1의 저장 키 0개 결정이 여기서 배당을 준다. Redis가 돌아오면 다음 커서 이동이 곧 복구다(재동기화 로직·stale 정리 불요). 그 사이 크로스 게이트웨이 커서는 최대 ~15초 뒤 상대의 자가 갱신으로 저절로 다시 보인다.

### 3.5 검증

게이트웨이 **2 인스턴스** + 엔진 1 + doc-service 1 + Redis 1. 클라이언트 A는 gateway-1, B는 gateway-2에 붙여 커서 상호 표시 확인. 이때 **문서 sync가 Redis 없이 이미 전파되는 것**도 같은 시나리오에서 확인된다(판단 2의 실증).

---

## Phase 4 — 자원 상한·백프레셔 정량화

`secure-coding.md` P2("무상한 자원 금지")의 미결 부채를 청산하는 Phase다.

### 게이트웨이

| 상한 | 현재 | M3 |
|---|---|---|
| 전역 동시 세션 | 없음 | Semaphore, 초과 시 핸드셰이크 **503** (VT 풀링 금지 가드레일과 정합 — 스레드가 아니라 세션을 센다) |
| per-doc 세션 | 없음 | 캡 + 초과 시 4429 close |
| per-user 세션 | 없음 | 캡 (탭 폭주 방지) |
| 송신 큐 | 없음 | `ConcurrentWebSocketSessionDecorator` 버퍼·시간 수치 확정 (Phase 1 도입분) |
| awareness 인바운드 | 없음 | **coalescing** — 토큰 버킷보다 우아하다. awareness는 최신 상태만 의미 있으므로 N ms 윈도우의 마지막 상태만 발행 |
| idle timeout | 10분 (주석: "M3서 정량 재조정") | Phase 6 측정 기반 재조정 |

> ⚠️ **세션 카운터의 acquire/release 짝을 어디에 두는지가 이 Phase의 진짜 난점이다.**
> 핸드셰이크(인터셉터)에서 획득하면 해제 지점은 `afterConnectionClosed`인데, 그 둘 사이에
> **`afterConnectionEstablished`가 조기 return하는 경로**가 있다(`DocWebSocketHandler:88~96` —
> `openSync` 실패 시 `closeQuietly` 후 return, `bridges`에 등록조차 안 됨). 획득과 해제를
> 서로 다른 콜백에 두면 그 경로가 곧 누수 경로다.
>
> 판정 기준: **획득 지점은 "해제가 반드시 도달하는 지점"에서 역산한다.** 핸드셰이크 거절로 503을
> 주려면 인터셉터에서 세야 하므로, 인터셉터 획득 + `afterConnectionClosed` 해제를 택하되
> **핸드셰이크 성공 후 세션이 열리지 않는 모든 경로**에서 해제가 도달하는지를 테스트로 고정한다
> (`afterConnectionEstablished` 조기 return · `openSync` 예외 · 업그레이드 실패).
> 도달을 증명 못 하면 획득을 `afterConnectionEstablished` 성공 직후로 내리고 503을 포기한다 —
> **누수보다 덜 우아한 거절 코드가 낫다.**

### 엔진

| 항목 | 현재 | M3 | 근거 |
|---|---|---|---|
| per-doc 세션 캡 | **없음** | 신설 | `main.rs:75~76` — "문서 수 상한은 **서로 다른 문서 수**만 막는다. 한 문서로의 세션 fan-out은 상한 밖" |
| 연결당 스트림 하드캡 | 없음 | Phase 6 측정 후 판정 | `main.rs:74~75` — 단일 채널 게이트웨이가 전 세션을 다중화하므로 정적 상한이 정상 부하를 조를 위험 |
| **문서 eviction (LRU)** | 상한만(`MAX_DOCUMENTS=10_000`), eviction 없음 | **신설 — 선행조건 해소됨** | `doc.rs:86~93` — "eviction은 ADR-0013 영속화 선행이라 현재는 상한만". 그 영속화가 **M2 Phase 3+에서 완료**됐다 |

#### 문서 eviction — SDD가 이미 등록해 둔 M2 미결이다

이건 새 항목이 아니다. **SDD §15 미해결에 `[ ] 엔진 문서 eviction/idle unload → M2 Phase 3+`로 등록돼 있고 아직 체크되지 않았다.** M2는 완료 선언됐는데 이 항목은 남았다 — C11의 역방향 점검 대상이다(아래 §M2 이월 참조).

차단 사유(영속화 부재)는 M2에서 사라졌다. 이것이 없으면 `MAX_DOCUMENTS`에 도달한 인스턴스는 **새 문서를 영구히 거부**한다 — 상한은 DoS를 막지만 그 자체가 가용성 절벽이다.

> 🔴 **evict 조건은 "유휴"가 아니다. 세 조건의 논리곱이다.**
>
> | 조건 | 왜 |
> |---|---|
> | **살아 있는 세션이 없다** | `DocEntry`가 broadcast sender를 쥔다(`doc.rs:177`). 구독자가 붙은 채 evict하면 그 세션들의 fan-out이 **조용히** 끊긴다 — 에러도 안 나고 편집만 전파되지 않는다. 이건 튜닝 값이 아니라 **불변식**이다 |
> | **pending save가 없다** | `save_in_flight`/미반영 update가 남은 채 내리면 **유실**. 스위퍼의 settle을 기다려야 한다 |
> | **durable하다** | 마지막 스냅샷이 현재 상태를 덮는다. `Persistence::Disabled`(4MiB 초과, §Phase 4E) 문서는 **evict 대상이 아니다** — 내리면 되돌릴 수 없다 |
>
> 세 번째가 **4E와의 결합점**이다: 증분 저장이 없으면 큰 문서일수록 evict 불가이고, 정작 메모리를
> 가장 많이 먹는 게 그 문서들이다. 4E 없이 eviction만 넣으면 **evict가 필요한 문서만 골라서 못 내린다.**

> 모든 수치는 **Phase 6 측정 전에는 임시값**이다. Phase 4에서 메커니즘을 넣고, Phase 6에서 근거를 붙인다. 이 순서를 뒤집으면 상한 없이 부하를 걸어 무엇이 먼저 무너지는지만 보게 된다.

---

## Phase 4E — 엔진 증분 저장·GC (독립 트랙)

### 문제

현재 스냅샷 저장은 **전체 상태 직렬화**(`encode_state_as_update`)다. 문서가 커져 blob이 `MAX_SNAPSHOT_BYTES`(≈4MiB−1KiB)를 넘으면 그 문서의 **영속화가 비활성된다**(`Persistence::Disabled` + ERROR).

```
문서 성장 → blob > 4MiB → 저장 포기 → 그 문서는 이후 재시작 시 마지막 성공 시점으로 되돌아간다
```

M2가 만든 안전장치는 "**조용히** 실패하지 않게" 하는 것까지였다(`save.rs:31` 주석이 스스로 "근본 해소는 M3"라고 남겼다). 즉 지금은 **시끄럽게 포기**하는 상태다.

### 방향 (착수 시 상세화)

1. **yrs GC/컴팩션** — tombstone·delete-set 누적 축소. **미도입 확정 ✅**(실측 2026-08-07: `doc.rs:179`가 `Doc::new()` 기본 옵션이고 레포 전체에 `Options`/`gc`/`skip_gc` 코드가 0건). 배정처는 **SDD §15**(`sdd/5-project-milestones-guardrails.md:107`)와 `design/crdt-engine.md` §6·§9이며 **둘 다 "M2 Phase 3"으로 적혀 있으나 수행되지 않았다** — ADR-0013 본문에는 gc/컴팩션 언급이 없다(인용 주의)
2. **증분 저장** — 전체 상태 대신 마지막 저장 이후 delta만. `page_snapshots`가 최신 1행 UPSERT 모델(ADR-0013)이라 **스키마·계약 변경을 동반**한다 → doc-service·proto 영향 재판정 필요
3. **청크 분할** — blob을 N개로 쪼개 저장. 스키마 변경 최소, 복원 시 순서 조립 필요

⚠️ 2·3은 **ADR-0013 개정**과 **proto 변경 가능성**을 부른다. M3의 "proto 무변경" 전제(판단 1)를 깨는 유일한 후보이므로, 착수 전에 세 방향의 비용을 비교하고 ADR로 결정해야 한다. 1번만으로 상한 아래로 내려온다면 그것이 가장 싸다 — **먼저 측정할 것**(현실적 최대 문서가 몇 MiB인지).

> **1번은 M2 이월이지 신규가 아니다.** SDD §15가 M2 Phase 3에 배정한 채 `[ ]`로 남아 있으므로
> 소유 마일스톤을 M3로 재배정한다(C2). 그리고 GC 도입은 **wire 호환·수렴에 영향을 줄 수 있으므로**
> 가드레일 6(proptest 수렴)과 가드레일 5(criterion 회귀) 양쪽을 통과해야 한다 —
> "옵션 하나 켜기"로 취급하지 말 것.

### 왜 M3인가

Phase 6 부하 측정이 대형 문서 시나리오를 포함해야 의미가 있는데, 그 시나리오에서 영속화가 꺼지면 측정 대상 자체가 달라진다. 그리고 이 절벽은 **문서가 자라기만 하면 시간이 지나며 반드시 도달한다** — 부하와 무관한 필연이다.

---

## Phase 5 — consistent-hash 라우팅 검증 (Envoy standalone)

### 구성

```
gateway (단일 ManagedChannel)
   │  HTTP/2, 스트림마다 doc-id 헤더
   ▼
Envoy standalone   ← ring_hash LB + hash policy: header "doc-id"
   ├──▶ engine-A (:50051)
   └──▶ engine-B (:50052)
```

### 검증 항목

1. **같은 doc-id → 항상 같은 인스턴스** (스트림 여러 개, 게이트웨이 재시작 후에도)
2. **다른 doc-id → 분산** (ring 분포 확인)
3. **단일 채널이 스트림 단위로 갈라지는가** ← 판단 3의 핵심 가정 실측
4. **인스턴스 1대 제거 → 해당 doc만 재배치** (consistent hash의 성질; 전체 재해싱이면 링 설정 오류)

### 산출

- M5에서 쓸 `DestinationRule`(consistentHash by header `doc-id`) YAML
- **ADR-0023** — consistent-hash 키 전달 상세 (SDD §15 미해결 클로즈)
- 3번이 깨질 경우의 대응안 (게이트웨이 doc별 채널 분리 등)

---

## Phase 6 — 부하 하니스 + NFR 측정

DoD 트래커의 NFR 3행을 닫는다.

| NFR | 측정 | 판정 기준 |
|---|---|---|
| 동시 편집자 ~50명 | k6 WS, 1 doc 50 clients | **p95 수렴 < 100ms** |
| 동시 WS ~수천 | k6 ramp-up | VT saturation 미발생 |
| 편집 반영 지연 | OTel histogram (서버 수신→broadcast) | p95 < 100ms |
| VT pinning 부재 | JFR / async-profiler | pinning 이벤트 0 |

⚠️ `design/benchmark-methodology.md`의 경고가 여기에도 적용된다: criterion이 재는 것(머지 처리량)과 NFR이 요구하는 것(e2e 수렴 지연)은 **다른 지표**다. 이 Phase가 그 간극을 메우는 유일한 측정이다.

⚠️ 벤치 측정 위생(`current.md` 실측): 로드가 걸린 맥에서 A/B가 ±7% 흔들리고 손대지 않은 그룹도 +33%가 나온다. 부하 테스트는 측정 머신을 격리하고 신뢰구간을 함께 기록한다.

⚠️ 엔진 벤치는 `--bench convergence`가 필수다(실측 2026-07-30). 인자 없는 `cargo bench`는 libtest 하네스까지 벤치 타깃으로 잡는다.

### 엔진 상한 5종 — 코드가 이 Phase를 지목하고 있다

엔진 소스가 **"M3 부하 검증서 정량 재조정"**이라고 직접 적어둔 값들이다. 이 Phase의 산출물에 이 표를 채우는 것이 포함된다.

| 상수 | 현재값 | 위치 | 코드 주석의 요구 |
|---|---|---|---|
| `MAX_DOCUMENTS` | 10_000 | `doc.rs:93` | "인스턴스 **메모리 대비** 정량 재조정" + env 주입으로 확장 |
| `RESTORE_BUDGET` | 5s | `doc.rs:100` | single-flight 대기 누적 실측 후 재조정 |
| `MAX_DOC_ID_LEN` | 128 | `doc.rs:28` | 정량 재조정 (M2에서 room=UUID로 좁아졌으므로 축소 후보) |
| `FANOUT_CAPACITY` | 256 | `doc.rs:84` | per-session 버퍼가 먼저 백프레셔를 받는 의도가 실제로 성립하는지 검증 |
| `OUTBOUND_BUFFER` | 64 | `sync/mod.rs:38` | 위와 동일 (쌍으로만 의미가 있다) |

마지막 두 개는 **쌍으로 튜닝해야 한다.** 설계 의도는 "느린 소비자가 broadcast `Lagged`(→full resync) 전에 아웃바운드 mpsc에서 먼저 자연 백프레셔를 받는다"인데, 50 clients 부하에서 이 순서가 실제로 지켜지는지는 측정된 적이 없다. 뒤집혀 있으면 느린 클라이언트 한 명이 full resync 폭주를 유발한다(설계서 §부록A-3의 미해결 질문).

### 이 Phase가 표면화시킬 이월 2건 (측정 결과에 따라 우선순위 결정)

둘 다 **이미 등록됐으나 미구현**이고, 50 clients 시나리오에서 처음으로 수치가 붙는다:

| 항목 | 현재 | 등록처 | Phase 6에서 보이는 모습 |
|---|---|---|---|
| **self-echo 미필터** | 송신자도 자기 update를 되받는다 — 정확성 무해(클라 멱등), 순수 트래픽 낭비 | ADR-0011 §트레이드오프 + 설계서 §9 → **M1.5**(미수행) | fan-out N벌 중 **1벌**이 낭비 = `1/N`. N=50이면 2%라 아마 잡음 이하 |
| **fan-out 제로카피** | `update.to_vec()` — 구독자마다 `Vec<u8>` clone | SDD §15 → **M2/M3**(미수행) | N=50이면 페이로드 **50벌 복제**. NFR 미달 시 첫 번째 용의자 |

⇒ **측정 전에 어느 쪽도 착수하지 않는다.** 다만 산술만으로도 우선순위는 거의 정해진다 — 같은 분모(fan-out N벌)로 맞추면 self-echo가 없애는 낭비는 `1/N`, 제로카피가 없애는 복제 낭비는 `(N−1)/N`이다. **N=50에서 2% 대 98% ≈ 49배.** 둘 다 가드레일 5(criterion 근거 동반)에 걸리므로 Phase 6의 산출에 "이 둘의 우선순위 판정"을 포함한다.

**부산물**: Phase 4의 게이트웨이 상한 수치에 근거가 붙는다 → SDD §15 "레이트리밋·세션/커넥션 캡 정량화" 클로즈.

---

## Phase 7 — 샤드 리밸런싱/핸드오프 설계

SDD §6.3은 **장애** 케이스만 정의한다(인스턴스 down → 재라우팅 → 스냅샷 복원). **계획된 증설·축소**는 미정의다.

설계할 시퀀스:

```
1. drain 신호 → 엔진이 새 Sync 스트림 거부 (기존은 유지)
2. 보유 문서 전부 SaveSnapshot push (M2 경로 재사용)
3. 기존 스트림 graceful close → 게이트웨이가 재연결
4. 재연결이 새 링에서 다른 인스턴스로 라우팅 → LoadSnapshot 복원
```

미결 질문:
- drain 신호 채널 — SIGTERM만으로 충분한가, 아니면 proto에 신호가 필요한가(→ 필요하면 M3의 proto 무변경 원칙 재판정)
- 3→4 사이 in-flight update의 운명 (엔진 `ALREADY_EXISTS` 재시도 미구현 이월건과 접점 — engine issue #18)
- 게이트웨이 재연결 로직이 실제로 있는가 (SDD §3.1이 요구하지만 구현 확인 필요)

**산출은 설계 + ADR까지. 구현은 M5**(K8s rolling update 맥락에서 실제로 필요해지는 시점).

---

## M2 이월 — "완료 선언"과 "완료" 사이의 3건

착수 전 확인에서 나왔다. **M2는 완료 선언됐으나 SDD §15에 M2로 배정된 미해결 3건이 `[ ]`로 남아 있다.**
`plan-logging.md` §완료 시 역방향 점검이 잡았어야 할 건이고, 셋 다 이 plan이 흡수한다.

| SDD §15 항목 | 배정 | 실측 상태 | M3에서 |
|---|---|---|---|
| yrs 히스토리 GC/컴팩션 | M2 Phase 3 | **미도입**(`doc.rs:179` `Doc::new()`) | Phase 4E 방향 1 |
| 엔진 문서 eviction/idle unload | M2 Phase 3+ | **미도입** | Phase 4 |
| fan-out 제로카피(`Bytes`) | M2/M3 | **미도입**(`update.to_vec()`) | Phase 6 측정 → 우선순위 판정, 구현은 범위 밖 |

⇒ **C2에서 SDD §15의 소유 마일스톤을 M3로 재배정**한다. 체크박스를 옮기지 않으면 다음 마일스톤에서
같은 발견을 반복한다 — 그게 이 표가 존재하는 이유다.

---

## Blast Radius

3개 레포·인프라를 건드리므로 `workflow.md` §Blast Radius 선언에 따라 명시한다.

| 축 | 내용 |
|---|---|
| **직접 변경** | backend `ws-gateway`(핸들러·코덱·룸 인덱스·설정·계측) · frontend `src/page/Editor.tsx` + 커서 확장 · engine `doc.rs`·`sync/mod.rs`·`snapshot/` · controller `docs/`(SDD·설계서·ADR·current.md) + Envoy 설정 + 부하 하니스 |
| **간접 영향** | ① **문서 sync 경로** — Phase 1이 WS writer 계약(§D-6)을 바꾼다. decorator가 모든 아웃바운드를 경유하므로 sync 프레임 지연 특성이 달라질 수 있다 ② **엔진 메모리·복원** — Phase 4 eviction이 `registry.open()` 경로의 복원 빈도를 올린다(`RESTORE_BUDGET` 압박) ③ **doc-service** — 4E가 증분/청크로 가면 `SaveSnapshot` 계약·스키마 변경 ④ **proto** — 판단 1대로 Phase 1~3은 무변경, 4E·7만 후보 |
| **롤백** | Phase별 독립 PR이라 `git revert` 단위가 곧 Phase다. Phase 3은 **저장 키가 없어 revert가 곧 완전 롤백**이다(정리할 Redis 상태 없음, §3.1). **되돌리기 어려운 것 2개**: ⓐ 4E가 스키마를 바꾸면 마이그레이션 역방향 필요 → **ADR 확정 전 착수 금지** ⓑ eviction은 되돌려도 이미 내려간 문서는 복원 경로를 타므로, 켜기 전에 §Phase 4의 세 조건을 테스트로 고정 |
| **검증** | 아래 §검증 표. Phase 1~4는 자동 테스트, 2는 로컬 E2E + 스크린샷, 5~6은 실측 기록 |
| **다운타임** | 없음(M3는 미배포 — 로컬·CI 한정). K8s 배포는 M5 |

---

## 실행 체크리스트

> 서비스 레포(backend/frontend/engine)는 **branch + PR + 건별 승인**. controller만 main 직접.

- [x] **C1** `docs(plan):` 이 파일 신설 — controller main 직접 (`0e758f9`)
- [x] **C2** `docs(sdd):` 문서 정정 **7건**(착수 시 2건 추가 발견) — ① SDD §6.3 Redis 범위를 awareness 한정으로 명시(무손실 버퍼=M5는 유지) ② SDD §6.2 시퀀스의 "+ Redis fan-out" 삭제 ③ `design/crdt-engine.md` §6 "Redis + consistent-hash" 모순 정정 ④ **SDD §15 미해결 3건(yrs GC·eviction·제로카피)의 소유 마일스톤 M2→M3 재배정** ⑤ ADR-0011 §범위의 awareness "M1.5/M5" → M3 정정 ⑥ **SDD §5 Redis 키 설계** — `pub/sub doc:{docId}`가 "update·awareness fan-out"이라 적혀 있어 판단 2와 정면 충돌(→ awareness 전용 채널로 교체) ⑦ **SDD §5 `presence:{docId}`** — M3 미사용을 명시(§3.1 저장 키 0개 결정)
- [x] **C3** `docs(adr):` `adr/README.md` 표 갱신 — 0021·0022 등재 누락 + **0004·0005·0007이 2026-08-03 정식 승격됐는데 표는 여전히 "분리 예정"**(착수 시 발견). 후자는 이 plan 판단 3이 ADR-0007을 권위로 인용하는 근거라 그냥 둘 수 없었다
- [ ] **C4** backend PR — Phase 1. **커밋 순서 고정**: decorator → 룸 인덱스 → 코덱(awareness/queryAwareness) → 릴레이 + **join 시 queryAwareness 발신**(§1.3) → 계측
- [ ] **C5** frontend PR — Phase 2, **DoD #3 증거 확보**. 선행 = 커서 플러그인 ⓐ/ⓑ 판정
- [ ] **C6** backend PR — Phase 3 (Redis pub/sub 2채널). **저장 키를 만들지 않는다** — Hash를 도입하면 §1.2 무해석 불변식이 깨진다(§3.1)
- [ ] **C7** backend PR + engine PR — Phase 4 (게이트웨이 상한 + 엔진 per-doc 캡 + 문서 eviction). **eviction은 §Phase 4의 세 조건을 테스트로 고정한 뒤에만 활성화**
- [ ] **C7E** engine PR — Phase 4E (증분 저장·GC). **선행 = 현실적 최대 문서 크기 측정** → 방향 3택 ADR
- [ ] **C8** controller + backend — Phase 5 (Envoy 검증 + ADR-0023)
- [ ] **C9** controller — Phase 6 (부하 하니스 + NFR 측정 기록 + self-echo/제로카피 우선순위 판정)
- [ ] **C10** controller — Phase 7 (핸드오프 설계 + ADR)
- [ ] **C11** `docs:` `current.md`·`dod-tracker.md` 갱신 + `current.md` §다음 액션 6의 "Redis 버퍼 복원 설계"를 M5로 정정(SDD §6.3과 정합) + M5 stub 선결조건에 "Phase 5가 hash 계약을 선확정" 반영

### 크래프트 게이트 (가드레일 7)

Phase 1·3·4는 동시성·자원 상한·실패 정책이 핵심이라 `concurrency.md`·`secure-coding.md` 렌즈가 특히 걸린다.
⚠️ 룰은 레포 경계를 넘지 않는다(실측 2026-07-28) — `java-expert`·`rust-expert` **에이전트로** 실행할 것.

---

## 검증

| Phase | 검증 |
|---|---|
| 1 | 같은 룸 2세션 awareness 상호 수신 · self-echo 없음 · viewer awareness 통과 · viewer update 여전히 drop(회귀) · 세션 종료 후 릴레이 미발생 · **join 시 기존 peer에 queryAwareness가 실제로 나가고, 그 응답이 신규 세션에 도달**(§1.3 — 이게 없으면 신규 접속자가 ~15초간 기존 커서를 못 본다) |
| 2 | 2 브라우저 커서·선택 표시 (**DoD #3**) · 한쪽이 **가만히 있어도** 다른 쪽 접속 즉시 커서가 보인다(Phase 1 발신의 e2e 확인) |
| 3 | 게이트웨이 2대 크로스 표시 · **gw-2 join 시 gw-1의 가만히 있는 peer가 즉시 보인다**(§3.2 재질의) · Redis 중단 시 편집 계속(fail-open) · Redis 복구 후 재동기화 코드 없이 회복 · **Redis에 키가 생기지 않음**(`--scan` 0건 — 무해석 불변식의 회귀 가드) |
| 4 | 각 캡 초과 시 지정 close code · **세션 카운터 누수 없음**(핸드셰이크 성공 후 세션 미개설 경로 3종에서 해제 도달) · 느린 클라이언트가 룸 전체를 지연시키지 않음 · 엔진 per-doc 캡 · **evict 3조건**(세션 0 · pending save 0 · durable) 각각의 반례에서 evict 미발생 · eviction 후 재접속이 스냅샷으로 복원 |
| 4E | 상한 초과 크기 문서가 영속화를 유지 · 재시작 후 복원 정합 · criterion 회귀 없음(가드레일 5) |
| 5 | 같은 doc-id 고정 라우팅 · 인스턴스 제거 시 부분 재배치 |
| 6 | p95 < 100ms @ 50 clients · 수천 커넥션 · VT pinning 0 · 엔진 상한 5종 근거 기록 |

기존 회귀 보호: gateway 테스트 전체 + `YProtocolCodecTest`(awareness drop 테스트는 **의도적으로 변경**되며, 그 변경이 곧 Phase 1의 계약 전환 지점이다).

---

## 범위 밖

- **Istio waypoint·DestinationRule 실배포** → M5 (Phase 5가 계약만 확정)
- **핸드오프 구현** → M5 (Phase 7이 설계만)
- **무손실 Redis 버퍼**(인스턴스 전환 중 in-flight update 보존) → **M5**. SDD §6.3이 배정한 별개 트랙이며 핸드오프 구현과 한 몸이다(판단 2 주석). Phase 7이 미결 질문으로만 든다
- **엔진 fan-out 제로카피**(`Vec<u8>` clone → `Bytes`) → 독립 트랙. Tier2 벤치 근거 동반 필수(가드레일 5). **Phase 6 부하 결과가 이 최적화의 우선순위를 결정한다** — 편집자 50명이면 페이로드 50벌이 복제되므로 NFR 미달 시 첫 번째 용의자다
- **엔진 self-echo 필터** → 독립 트랙. ADR-0011이 M1.5로 잡았으나 미구현(`doc.rs:503`). 정확성 무해(클라 멱등)라 순수 트래픽 최적화이고, 낭비가 `1/N`(N=50에서 2%)이라 제로카피(`(N−1)/N`)보다 **약 49배 작다** → **Phase 6 측정 후 판정**
- **Tier2 샤딩 "N배" baseline**(per-doc 샤딩 before/after) → 벤치 트랙. M2/M3로 걸쳐 등록돼 있으나 DoD·NFR과 직결되지 않는다
- **awareness 신원 서버 stamp** → 후속 (Phase 1.5 판정)
- **presence REST 조회 API**("누가 접속 중") → 후속. **서버 상태를 요구하는 유일한 용도**이며, 도입 시 awareness 페이로드 디코딩 비용을 의식적으로 지불하는 결정이 된다(§3.1). M3는 저장 키 0개를 유지한다
- **엔진 운영 기능 3건**(`tonic-health`·metrics·reflection) → M5 (ADR-0022 §범위 밖)
- **트리 CRDT · 버전 히스토리 · 검색** → PRD 확장(2차)

---

## 열린 질문 (착수 전 판정 필요)

> 착수 전 확인에서 2건이 닫혔다. **"5분이면 확인되는 것"을 열린 질문으로 두지 않는다**
> (`workflow.md` §검증 없이 쓰지 않는다 — caveat는 검증 불가 영역의 사후 보강이지 대체가 아니다).

1. ~~**Phase 2 프론트 스택**~~ → **닫힘 ✅**(2026-08-07): Tiptap 3.27.1 + `@tiptap/y-tiptap` 3.0.5 + y-websocket 3.0.0. 상세·잔여 판정(커서 확장 ⓐ/ⓑ) = §Phase 2
2. **게이트웨이 재연결 로직 존재 여부** — SDD §3.1이 heartbeat + backoff + state reconciliation을 요구하나 구현 미확인. Phase 7의 전제이므로 늦어도 그 전에 확인. (참고: **클라이언트** 측 재연결은 y-websocket이 상한 2500ms backoff로 수행함이 확인됨 — 미확인인 것은 **게이트웨이↔엔진** 스트림 재연결이다)
3. **Phase 4 캡의 초기값** — Phase 6 측정 전 임시값을 무엇으로 둘지 (보수적으로 낮게 시작 vs 관측만)
4. **Redis 배포 형태** — 로컬 docker-compose로 M3를 넘기고 K8s 배치는 M5로 미룰지
5. ~~**yrs GC 옵션이 실제로 도입됐는가**~~ → **닫힘 ✅**(2026-08-07): **미도입**. `doc.rs:179` `Doc::new()` 기본 옵션, 레포 전체 `Options`/`gc` 코드 0건. 배정처도 ADR-0013이 아니라 SDD §15·설계서 §6/§9였다 → §Phase 4E 방향 1 · §M2 이월
6. **M3 범위가 과한가** — DoD #3(Phase 1~2)만으로 마일스톤을 닫고 4·4E·5·6·7을 M3.5/M5로 미루는 선택지가 있다. 판단 기준은 "M4(AI)가 이 중 무엇에 막히는가"이며, 답은 **아무것도 막히지 않는다** — 따라서 순수하게 완성도 대 속도의 문제다. 단 §M2 이월 3건은 어디로 미루든 **누군가는 체크박스를 옮겨야 한다**(C2)

---

## 재개 지점 (Resume)

```
마지막 완료 = 2026-08-07 C1~C3. 계획 커밋(`0e758f9`) + 문서 드리프트 정정 8건
              (C2 7건: SDD §5·§6.2·§6.3·§15×3 · 설계서 §6·§9 · ADR-0011 / C3 1건: adr/README).
다음        = Phase 1(backend PR) 착수 — 브랜치 + PR + 건별 승인.

주의 (다음 세션이 밟을 지뢰):
1. Phase 1의 **첫 커밋은 ConcurrentWebSocketSessionDecorator**여야 한다(§1.1). 나중에 붙이면
   그 사이 모든 fan-out 코드가 미검증 동시성 위에 쌓인다. §1.3의 join-시 발신이 이 필요를 키웠다.
2. **queryAwareness는 "릴레이"가 아니라 "게이트웨이 발신"이다**(§1.3). y-websocket은 WS로
   queryAwareness를 보내지 않는다(BroadcastChannel 전용) — 릴레이만 넣으면 dead code이고
   신규 접속자가 최대 ~15초간 기존 커서를 못 본다. 이 방향을 되돌리지 말 것.
3. **Phase 3에 Redis 저장 키를 만들지 말 것**(§3.1). Hash를 두면 게이트웨이가 awareness 페이로드를
   디코딩해야 하고, 그 순간 §1.2가 ADR-0011 기각사유①을 무력화한 논거와 §1.5의 옵션 B 기각 논거가
   동시에 무너진다. 유령 커서는 **클라이언트가 30초 타임아웃으로 스스로 지운다**(실측 확인).
   join 시 원격 peer 발견은 `awareness:query` 채널 재질의로 해결한다(§3.2).
4. **eviction은 "유휴"가 조건이 아니다** — 세션 0 · pending save 0 · durable의 논리곱(§Phase 4).
   구독자가 붙은 문서를 evict하면 fan-out이 에러 없이 조용히 끊긴다.
5. 라인 번호는 2026-08-07 실측이다. 서비스 레포가 앞서면 어긋나므로 `rg`로 심볼을 다시 잡을 것.
6. C2는 문서 5건 정정이 한 덩어리다 — SDD §15 재배정(M2 이월 3건)을 빠뜨리면 이 발견이 증발한다.
```
