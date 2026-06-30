# 엔진 기술 설계서 — CRDT Engine (Rust) 심화

> **이 문서의 위상**: 흩어져 있던 엔진 설계를 하나로 통합한 **단일 기술 설계서(deep-dive)**.
> 출처 통합: [SDD §3.2](../sdd/2-services-and-contracts.md)(책임·인터페이스) · [ADR-0011](../adr/0011-engine-sync-fanout-bridge.md)(브리지 결정) · `weDocs-crdt-engine/src/*`(코드 주석 §D-1~6) · [수렴 구현 plan](../plans/2026-06-25-m1-convergence-impl.md).
> **독자**: 본인(학습), 면접관(심층 방어), 신규 협업자. 이론 → 우리 설계 → 산업 대비 → 최적화 순.
> 작성: 2026-06-30 (M1 종료 시점 기준)

---

## 0. 한눈에

```
[브라우저 Tiptap+Yjs] ──WS(y-websocket 와이어)──▶ [ws-gateway: Java VT]
                                                       │ 번역만(lib0 코덱)
                                                       ▼ gRPC bidi (traceparent 주입)
                                              [CRDT Engine: Rust + yrs]  ★이 문서
                                                       │ per-doc broadcast fan-out
                                                       ▼
                                              같은 doc의 다른 모든 세션
```

엔진의 한 줄 정의: **"yrs(Yjs의 Rust 포트)를 권위 머지 코어로 삼아, 한 문서의 동시 편집을 gRPC bidi 스트림 위에서 머지·fan-out하는 서버 권위(server-authoritative) 동기화 엔진."**

---

## 1. 먼저 — 실시간 협업은 업계에서 어떻게 푸나 (지형도)

실시간 공동 편집의 "충돌 해결"은 크게 세 갈래다. 우리가 왜 CRDT를 골랐는지는 이 지형 위에서만 정당화된다.

### 1.1 세 가지 접근

| 접근 | 핵심 아이디어 | 대표 | 강점 | 약점 |
|---|---|---|---|---|
| **OT** (Operational Transformation) | 편집을 "연산"으로 보고, 중앙 서버가 연산을 **변환**해 순서를 맞춤 | **Google Docs**, Confluence(Synchrony) | 문서가 가벼움(문자당 메타데이터 X), 즉시 강한 일관성 | 변환 함수가 악명 높게 복잡(수백 엣지케이스), 서버 중앙 권위 필수 |
| **CRDT** (Conflict-free Replicated Data Type) | 편집을 **교환법칙이 성립하는 연산**으로 설계 → 어떤 순서로 적용해도 같은 결과(수학적 수렴 보장) | **Zed**, Yjs 생태계, Automerge | 중앙 변환 불필요, 오프라인·P2P 자연스러움 | 문자/요소당 메타데이터(tombstone) → 무거움, GC 필요 |
| **도메인 특화 LWW** | 충돌 입도를 도메인에 맞춤(객체의 속성 단위 last-writer-wins) | **Figma** | 가장 단순·빠름 | 일반 텍스트엔 부적합(도메인이 트리/속성일 때만) |

### 1.2 대기업이 실제로 고른 것 (왜 다른가)

- **Google Docs = OT.** 서버가 어차피 모든 연산을 봐야 한다(권한·렌더·저장). 중앙 변환 비용이 \<5ms라 데이터 모델 단순화 이득이 더 큼. 오프라인은 "1급 기능"이 아니라 "우아한 degradation". [systemdr]
- **Figma = OT도 순수 CRDT도 거부.** 디자인 문서는 "텍스트 시퀀스"가 아니라 "속성 수백 개를 가진 객체 트리"라 OT의 문자 단위 변환이 안 맞음. 대신 **속성 단위 LWW + fractional indexing**으로 200명 동시 편집. 도메인 입도가 자연스러우면 범용 CRDT/OT보다 단순한 시스템이 가능하다는 교훈. (코드 레이어엔 Eg-walker 별도 도입.) [sujeet.pro, figma blog]
- **Zed = 순수 CRDT(Rust, 직접 구현).** Atom·Tree-sitter 제작자들이 GPU UI부터 CRDT 협업 엔진까지 from scratch. 핵심 = "편집을 절대 offset이 아니라 **논리적 위치(logical location)** 로 표현" → 연산이 본질적으로 교환 가능. 차세대 동기화 엔진 DeltaDB는 문자 단위 추적으로 사람+AI 에이전트가 같은 뷰 공유 목표. [zed.dev/blog/crdts]
- **Yjs 생태계 = 가장 널리 쓰는 CRDT.** 주 900k+ 다운로드. AFFiNE(y-octo), JupyterCad/GIS, Sana, Skiff 등이 프로덕션 사용. **yrs = Yjs의 Rust 포트로 wire 호환** — 우리 엔진의 머지 코어. [yjs github, crdt.tech]

> **요지**: "정답"은 없다. **제약이 알고리즘을 고른다.** Google은 중앙 서버 전제 → OT. Figma는 도메인이 트리 → 속성 LWW. Zed/Yjs는 오프라인·확장·wire호환 → CRDT. 면접에서 "왜 CRDT?"에 이 지형으로 답하면 "유행 따라"가 아니라 "제약 분석"이 된다.

### 1.3 우리의 선택과 근거

**CRDT(yrs).** 지배 제약 3개:
1. **클라가 이미 Yjs** — Tiptap 블록 에디터가 Yjs 위. 서버가 wire 호환(yrs)이면 클라 변경 0, 상호운용은 lib0 v1 바이너리로 자동.
2. **오프라인·재접속이 위키의 자연 요구** — 새로고침·네트워크 끊김 후 재수렴이 CRDT에선 공짜(state vector diff). OT라면 서버 중앙 변환에 묶임.
3. **언어 전략** — 머지는 CPU·정확성 critical → Rust. yrs가 그 자리에 정확히 들어맞음(가드레일: "엔진은 엔진이다").

→ **결정: Google Docs(OT)가 아니라 Zed/Yjs 계열(CRDT). 단, Zed처럼 from-scratch가 아니라 yrs를 코어로 채택**(직접 CRDT 구현은 학습용 1모듈로 분리, [SDD ADR-5]).

---

## 2. 우리 엔진의 정체 — "Rust로 재구현한 서버 권위 Yjs relay"

정직하게 분류하자. 우리가 만드는 것은 **새로운 CRDT 알고리즘이 아니다.** 업계에 이미 같은 계열의 제품이 있다:

| 제품 | 정체 | 우리와의 관계 |
|---|---|---|
| **Hocuspocus** (Tiptap) | Yjs CRDT WebSocket 백엔드. 문서를 **바이너리 Y.Doc으로 저장**, auth·persistence·webhook | 우리가 하려는 일의 Node.js 판 |
| **y-sweet** (Jamsocket) | Rust + yrs 기반 Yjs 서버, S3 영속 | **우리와 가장 가까움(Rust+yrs)** |
| **Liveblocks Yjs** | 완전 관리형 Yjs 인프라(WS·저장·REST·DevTools) | 우리의 SaaS 버전 |
| **y-redis / yrs-warp** | Redis fan-out / Rust warp 기반 relay | 멀티인스턴스 fan-out 참조(M3) |

> **그래서 "단순 yrs 래퍼가 아님"의 진짜 의미는 무엇인가?**
> CRDT 수학을 재구현하는 게 아니다(그건 yrs가 한다). **엔진의 깊이 = 분산 협업 서버 인프라**다 — Hocuspocus/y-sweet가 "그냥 Yjs"가 아니라 제품인 이유와 같다:
>
> ```
> 래퍼(얕음)              엔진(깊음, = 우리 목표)
> ─────────────────────────────────────────────────
> apply_update 호출       + per-doc fan-out 허브(broadcast)
>                         + 동시성/백프레셔 모델(락·버퍼 계층)
>                         + 신규접속 sync 프로토콜(state vector diff)
>                         + 영속화·스냅샷·복원(M2)
>                         + 수평 확장(consistent-hash 샤딩, 멀티인스턴스 fan-out)
>                         + 관측(OTel trace·메트릭)·벤치(criterion 정량)
> ```
>
> 즉 가드레일 5("단순 래퍼 PR 반려")는 **"CRDT를 직접 짜라"가 아니라 "서버 인프라를 엔진 수준으로 만들라"** 로 읽어야 한다. (이 재해석은 §6 최적화 로드맵으로 이어짐.)

---

## 3. 핵심 개념 — yrs/Yjs는 왜 수렴하나 (INTERNALS)

엔진을 이해하려면 yrs가 다루는 4개 객체를 알아야 한다.

### 3.1 모델 (YATA 계열)

Yjs는 **YATA**(Yet Another Transformation Approach) 알고리즘 기반. 핵심은 §1.2 Zed와 동일 — **절대 위치가 아니라 논리적 ID로 편집을 표현**한다.

```
문서 = struct들의 순서 집합. 각 struct(Item)는:
  id        = (client_id, clock)   ← 누가, 몇 번째로 만든 연산인가 (Lamport 시계 유사)
  origin    = 왼쪽 이웃의 id        ← "어디 뒤에 삽입" (offset 아님!)
  content   = 실제 문자/요소
  deleted   = tombstone 플래그       ← 삭제는 지우지 않고 표시만(수렴 위해)
```

같은 위치에 두 명이 동시 삽입하면? `(client_id, clock)`로 **결정론적 정렬** → 모든 복제본이 같은 순서 도출. 중앙 변환(OT) 불필요 = CRDT의 본질.

### 3.2 동기화에 쓰는 두 객체

| 객체 | 의미 | 비유 |
|---|---|---|
| **State Vector** | `client_id → 최신 clock` 맵. "내가 가진 것의 압축 요약" | 각 작성자별 "여기까지 읽음" 북마크 |
| **Update** | struct/삭제의 인코딩된 집합. "이만큼의 변경" | diff/패치 |

동기화 = **"네 state vector 줘 → 네가 없는 부분만 update로 보내줄게."**
```
encode_state_as_update_v1(client_sv)  →  클라가 누락한 diff만 계산 (최소 전송)
```
이게 §4의 SyncStep1/2의 정체다.

### 3.3 왜 수렴이 "보장"되나 (proptest가 검증하는 것)

CRDT 연산은 세 성질을 만족하도록 설계됨 → **Strong Eventual Consistency**:
```
교환법칙(commutative): apply(A,B) == apply(B,A)   ← 순서 무관
결합법칙(associative): 묶는 방식 무관
멱등성(idempotent):    같은 update 두 번 적용 = 한 번  ← self-echo가 무해한 이유
```
우리 `tests/convergence_proptest.rs`가 **무작위 연산 순열에도 모든 복제본이 동일 상태**임을 property-based로 검증(가드레일 6). 이게 "두 브라우저 수렴"의 수학적 근거.

### 3.4 인코딩 — lib0 v1 고정 (상호운용의 생명줄)

```
✅ encode_v1 / decode_v1  ← Yjs 클라가 디코드 가능 (호환)
❌ encode_v2              ← 더 작지만 Yjs 클라 디코드 불가 → 상호운용 붕괴
```
**모든 인코딩 v1 고정**은 협상 불가 제약. ([ADR-0011] 축 2)

### 3.5 tombstone과 GC (CRDT의 세금)

삭제를 즉시 지우면 동시성 충돌 시 수렴이 깨짐 → **tombstone으로 표시만** 함. 누적되면 메모리 부담 → yrs가 인접 struct 병합·삭제 콘텐츠 비움으로 **완화**(완전 제거는 불가). 이게 OT 대비 CRDT의 본질적 비용([§1.1]).

---

## 4. 동기화 프로토콜 — 데이터 흐름

### 4.1 와이어 매핑 (게이트웨이 = 번역기)

게이트웨이는 Java라 `Y.Doc`이 없다 → diff 계산 불가 → **엔진이 sync 권위.** 게이트웨이는 1:1 번역만:

```
y-websocket 와이어            gRPC 프레임 (proto 무변경!)
──────────────────────────────────────────────────────
SyncStep1(state vector)  ⇄   ClientFrame{ state_vector }
SyncStep2 | Update       ⇄   ClientFrame{ update }
Update(2)                ⇄   ServerFrame{ update }
```
> proto 무변경으로 M1 완수 — 기존 `ClientFrame{doc_id,update,state_vector}`로 SyncStep1/2/Update 전부 표현. ([ADR-0011] 결과)

### 4.2 신규 접속 시퀀스 (late-join)

```
client → gateway: connect(docId, JWT)
gateway → doc-service: CheckPermission ⇒ role(editor/viewer)
gateway ↔ engine: Sync 스트림 open (doc-id = gRPC 메타데이터)   ← §4.4
engine → client: SyncStep1 (엔진의 state_vector) ───┐ 클라의 오프라인분 pull 유도
client → engine: ClientFrame{state_vector}          │
engine → client: ServerFrame{diff update}  ◀────────┘ encode_state_as_update_v1
client: 로컬 Yjs 적용 → 즉시 편집 가능
이후: update가 bidi로 양방향 + 같은 doc 모든 세션에 fan-out
```

### 4.3 fan-out — per-doc broadcast 허브

```
                       ┌─ session A (out mpsc, buf 64) ─▶ 클라 A
doc "room-1"           │
  DocEntry             ├─ session B ─────────────────────▶ 클라 B
   doc: yrs.Doc        │
   tx: broadcast(256) ─┤  apply_v1(update) → 머지 후
                       └─ 원본 바이트 그대로 broadcast.send()
```
한 세션의 update를 엔진이 같은 doc의 **모든 구독 스트림에 broadcast**. 게이트웨이는 세션 그룹핑 불필요(가드레일 5 부합). 송신자도 자기 update 수신하지만 **멱등이라 no-op**([§3.3], self-echo 무해 — 필터는 M1.5 최적화).

### 4.4 chicken-egg 해소 — doc_id를 메타데이터로

스트림 open 시점엔 아직 첫 ClientFrame이 없음 → 그래도 엔진이 어느 doc인지 알아야 구독 가능. → **doc_id를 gRPC 메타데이터(`doc-id`)로 전달**. `ClientFrame.doc_id`는 첫 프레임 검증용(불일치 → 세션 종료, 교차오염 방지). ([ADR-0011] 축 3, `service.rs` §D-1)

---

## 5. 동시성 모델 — 엔진의 진짜 엔지니어링

여기가 "Rust로 실시간성 높이는" 부분의 실체. 정확성과 백프레셔가 코드에 박혀 있다.

### 5.1 레지스트리 락과 lost-update 윈도 차단

```rust
// DocRegistry = Arc<Mutex<HashMap<String, DocEntry>>>
open(doc_id):
  락 획득 → 구독(subscribe) → 그 다음 스냅샷(state_vector) → 락 해제
  // 구독-후-스냅샷을 같은 락 안에서 → 구독 전 update 유실 윈도 제거 (§D-2)
  // ⚠️ 락 보유 중 .await 금지 — transact()는 동기
```
**lost-update 윈도**: 만약 "구독" 전에 다른 세션 update가 지나가면 신규 클라가 그걸 놓침. 구독을 스냅샷보다 먼저, 둘을 같은 임계영역에 두어 차단.

### 5.2 2단 백프레셔 (slow consumer 대응)

```
broadcast 채널(FANOUT_CAPACITY = 256)   ← 문서당 fan-out 버퍼
        │
per-session 아웃바운드 mpsc(OUTBOUND_BUFFER = 64)  ← 세션당, 더 작게
```
**의도**: 느린 클라이언트가 broadcast `Lagged`(유실 → 전체 재동기화)를 트리거하기 *전에*, 더 작은 per-session mpsc에서 **먼저 자연 백프레셔**가 걸리게 함(`service.rs` §D-6). 버퍼 크기 대소관계가 곧 설계 의도.

### 5.3 Lagged → 전체 재전송

느린 수신자가 `RecvError::Lagged(skipped)` → 유실분 복구 불가 → `encode_state_as_update_v1(default)`로 **전체 상태 재전송**해 재수렴(`service.rs` §D-5). TODO(M1.5): lagged 빈발 = cap 부족 신호 → `lagged_total` 메트릭.

### 5.4 bidi 스트림 + cancel-safety

per-session tokio task가 `select!`로 인바운드(클라 프레임)와 fan-out(broadcast)을 동시 대기. `inbound.message()`의 디코드 상태는 `Streaming`에 보존, broadcast `recv()`는 cancel-safe → **어느 브랜치가 취소돼도 프레임 무손실**. (config-contract-audit: tonic 마이너 업그레이드 시 재확인 대상.)

### 5.5 관측 (가드레일 4)

게이트웨이(Java javaagent)가 주입한 W3C `traceparent`를 `MetadataExtractor`로 추출 → `span.set_parent` → `.instrument(span)`으로 세션 태스크 전체를 trace에 연결. **한 WS 세션 = Java span의 자식 Rust span**. (per-edit span은 M1.5/M5.)

---

## 6. "래퍼 → 엔진" 최적화 로드맵 (가드레일 5의 실현)

§2에서 재정의했듯, 엔진 깊이는 서버 인프라에서 나온다. 현재 vs 목표를 정직하게:

| 영역 | 현재(M1) | 한계 | 최적화 방향 | 비교 대상 |
|---|---|---|---|---|
| **레지스트리 락** | `Arc<Mutex<HashMap>>` 전역 락 1개 | doc A 머지가 doc B를 막음(한 인스턴스 수천 doc 시 병목) | **per-doc 샤딩**(DashMap/락 분할) → 문서 격리 | y-sweet의 doc별 격리 |
| **fan-out 바이트** | `update.to_vec()` 복사 | 제로카피 아님 | `Bytes`/`Arc<[u8]>` 공유로 복사 제거 | — |
| **영속화** | 없음(인메모리, 프로세스 재시작=유실) | 복원 불가 | 스냅샷(update N개/T초) → Postgres bytea, 복원 적용 | Hocuspocus 바이너리 저장 |
| **멀티인스턴스 fan-out** | 단일 인스턴스 가정 | 수평 확장 불가 | **Redis pub/sub** 크로스 인스턴스 + docId consistent-hash 라우팅(Istio waypoint) | y-redis |
| **벤치 방법론** | criterion + **M1.5 Tier1 위생/회귀 가드 ✅**(PR#3: merge/build_doc 분리·워크로드 4종·`--save-baseline`) | "N배" 헤드라인은 아직(Tier2 샤딩 before/after 필요) | Tier2 샤딩 baseline → M2/M3 | §7 |

> 이 표가 **M2~M3·M5 작업의 기술 백로그**이자, 면접에서 "엔진을 어떻게 더 깊게?"에 대한 답.

---

## 7. 벤치마크 — "N배 빠르다"를 정직하게 만드는 법

> 📖 상세: [벤치마크 방법론](benchmark-methodology.md) — 3계층 측정·baseline 정의·워크로드 모델·하니스 설계.

현재 가장 약한 고리. SDD §3.2가 "Java 단순 래퍼 대비 N배 criterion 증명"이라 했지만 **baseline이 없으면 N은 공허**하다.

**측정 대상부터 정직하게:**
```
criterion이 재는 것     = 머지 처리량(throughput), CPU 핫패스   ← 현재
NFR이 요구하는 것       = end-to-end 수렴 지연 p95 < 100ms       ← 진짜 목표
                          (네트워크+게이트웨이 번역+gRPC+머지+fan-out)
이 간극을 메우는 별도 측정(부하 테스트)이 필요.
```

**공정한 baseline 후보 (택1, 명시):**
1. 순진한 구현(전체 문서 직렬화 후 전송) 대비 → "diff 동기화가 N배 적은 바이트"
2. 단일 전역 락 대비 per-doc 샤딩 → "동시 다문서 처리량 N배"(§6)
3. (반칙 주의) "Java가 못 하는 걸 한다"는 N배가 아니다 — 비교 불가는 비교가 아님.

→ **권장**: criterion에 baseline 케이스를 같이 넣어 `git` 회귀로 추적(`benches/`). 부하 테스트(동시 N세션 수렴 지연)는 별도 하니스.

---

## 8. 산업 대비 우리 포지션 (면접 방어 한 페이지)

| 축 | Google Docs | Figma | Zed | y-sweet/Hocuspocus | **weDocs 엔진** |
|---|---|---|---|---|---|
| 알고리즘 | OT | 속성 LWW | 순수 CRDT(직접) | Yjs CRDT | **Yjs CRDT(yrs)** |
| 서버 권위 | 중앙 변환 | 서버 권위 | relay | 서버 권위 relay | **서버 권위 relay** |
| 머지 코어 | 자체 | 자체 | 자체(Rust) | yrs/Yjs | **yrs(Rust)** |
| 언어 | — | Rust(서버) | Rust | Rust/Node | **Rust 엔진 + Java 게이트웨이 분리** |
| 차별점 | — | 도메인 입도 | from-scratch 통합 | 관리형/영속 | **폴리글랏 분리 + 단일 trace + consistent-hash 샤딩** |

**우리만의 한 줄**: "Yjs 생태계의 검증된 머지(yrs)를 코어로, **게이트웨이(I/O, Java VT)와 엔진(CPU, Rust)을 언어 제약에 따라 분리**하고, 그 폴리글랏 호출을 **단일 OTel trace로 관측**하며, docId consistent-hash로 stateful 수평 확장하는 서버 권위 동기화 엔진." → 알고리즘 발명이 아니라 **분산 시스템 설계·언어 판단·관측성**이 증명 포인트.

---

## 9. 미해결 / 다음 (소유 마일스톤)

- 영속화·스냅샷·복원 → **M2** ([M2F-02])
- per-doc 샤딩(전역 락 제거) + 제로카피 → **M2/M3** (§6)
- 멀티인스턴스 fan-out(Redis) + consistent-hash 라우팅 상세 → **M3**
- self-echo 필터 · synced 라이프사이클(proto 판별자) · per-edit span → **M1.5**
- 벤치 Tier1 위생·그룹화·회귀 가드 → **M1.5 ✅**(engine PR#3, [dev-log](../dev-logs/2026-06-30-m1.5-bench-hygiene.md)) / Tier2 샤딩 "N배" baseline → M2/M3 / 부하 하니스(Tier3) → **M5** (§7)
- CRDT 직접 구현 학습 모듈(INTERNALS 심화) → 선택 ([SDD ADR-5])

---

## 부록 A — DevOps/엔지니어링 관점 자문 (발전용)

1. **전역 락 → per-doc 샤딩**을 하면, 한 인스턴스가 수천 doc를 들 때 처리량이 어떻게 변할까? 이걸 criterion으로 "before/after N배"를 보여주면 §7의 정직한 baseline이 생긴다 — 어떤 워크로드(문서 수 × 세션 수)로 측정해야 대표성이 있을까?
2. **consistent-hash로 "같은 doc=같은 인스턴스"** 인데, 그 인스턴스가 죽으면? 리밸런싱 중 그 doc의 in-flight update는 어디로 가나(스냅샷 복원 + Redis 버퍼)? 이게 M2 영속화와 M3 라우팅의 접점.
3. **Lagged 재전송(§5.3)은 전체 상태를 보냄** — 큰 문서에서 한 명이 느리면 전체 재전송 폭주가 날 수 있다. 어느 지점에서 "이 클라를 끊는 게 낫다"고 판단할 백프레셔 정책을 둘까?
4. **trace는 현재 스트림당 1 span**(per-edit 아님). 편집 1건의 지연을 추적하려면 per-edit span이 필요한데, 그 카디널리티 폭발(초당 수백 span)을 어떻게 샘플링할까?

---

## 참고 (산업 사례)

- Figma 멀티플레이어: <https://sujeet.pro/articles/figma-multiplayer-infrastructure> · <https://www.figma.com/blog/building-figmas-code-layers/>
- Zed CRDT: <https://zed.dev/blog/crdts>
- Google Docs OT vs CRDT: <https://systemdr.systemdrd.com/p/crdts-vs-operational-transformation>
- Yjs: <https://github.com/yjs/yjs> · <https://yjs.dev/> · 구현 목록 <https://crdt.tech/implementations>
- 서버 백엔드(우리 계열): Hocuspocus <https://github.com/ueberdosis/hocuspocus> · y-sweet/Liveblocks(관리형)
- 로컬-퍼스트 sync engine 흐름(Linear/Figma LiveGraph/Asana LunaDB): <https://stack.convex.dev/object-sync-engine>
