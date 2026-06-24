---
name: crdt-yrs
description: "yrs(y-crdt) 기반 협업 CRDT 엔진 패턴 — Doc/Transaction, state vector diff, 스냅샷/GC, Yjs binary wire 상호운용, tonic bidi sync I/F, 문서별 actor 격리. Use when Rust로 Yjs 호환 CRDT 서버/엔진을 설계하거나 sync 프로토콜·스냅샷·머지·`!Send` 동시성을 다룰 때."
effort: max
---

# CRDT Engine with yrs (y-crdt)

`yrs`는 Yjs의 Rust 포트로 **binary wire/프로토콜이 Yjs와 호환**된다 — 클라이언트 Yjs와 서버 yrs가
동일 update 포맷으로 상호운용된다(Synapse M1의 핵심 전제). 이 스킬은 "단순 래퍼가 아닌 엔진"을
만들기 위한 패턴이다(SDD §3.2).

> ⚠️ API는 **yrs 0.27** 기준. 마이너 버전에서 시그니처가 바뀌므로 `docs.rs/yrs`로 확인할 것.

## Quick Reference (결정 트리)

```
새 클라이언트 접속?
  └─ 클라가 state vector 전송 → 서버: encode_diff_v1(sv) → 최소 diff만 회신 (전체 X)
편집 update 도착?
  └─ txn_mut.apply_update(Update::decode_v1(&bytes)?)  → observe_update_v1로 타 피어에 fan-out
커서/선택(presence)?
  └─ ❌ CRDT(Doc)에 넣지 마라 → Awareness 또는 별도 Redis 채널 (tombstone 오염 방지)
영속화?
  └─ 주기/임계마다 encode_state_as_update_v1() → bytea 스냅샷. 복원 = 새 Doc에 apply_update
동시성?
  └─ Doc은 await 너머 공유 금지 → 문서별 task(actor)가 Doc 소유, mpsc 명령 채널
전송?
  └─ 매 update마다 unary RPC ❌ → tonic bidi 스트림 1개 유지
```

## 1. 핵심 API (yrs 0.27)

```rust
use yrs::{Doc, Text, Transact, Update, StateVector};
use yrs::updates::decoder::Decode;
use yrs::updates::encoder::Encode;

let doc = Doc::new();
let text = doc.get_or_insert_text("content");   // 공유 타입(문서 루트)

// 원격 update 적용 (Yjs 클라가 보낸 바이트)
{
    let mut txn = doc.transact_mut();            // 쓰기 트랜잭션 (문서당 1개 배타)
    txn.apply_update(Update::decode_v1(&bytes)?)?;
}                                                // txn drop 시 커밋

// 신규 접속: 클라 state vector 기준 최소 diff
let remote_sv = StateVector::decode_v1(&client_sv_bytes)?;
let diff = doc.transact().encode_diff_v1(&remote_sv);   // 이 diff만 전송

// 스냅샷(영속화용 전체 상태)
let snapshot = doc.transact().encode_state_as_update_v1();
let my_sv    = doc.transact().state_vector().encode_v1();
```

**v1 vs v2**: 클라 Yjs와 **인코딩 버전을 일치**시켜라(`y-protocols` 기본 v1). 혼용하면 디코드 실패.

## 2. 변경 전파 (observe → fan-out)

```rust
// Doc 변경 시 인코딩된 update를 구독자(타 게이트웨이 커넥션)에게 broadcast
let _sub = doc.observe_update_v1(move |_txn, e| {
    let update: &[u8] = &e.update;               // 이미 인코딩됨 — 재인코딩 불필요
    let _ = tx.send(update.to_vec());            // tokio broadcast/mpsc 로 fan-out
})?;   // _sub(Subscription) 살아있는 동안만 콜백 유효 — drop 주의
```
> 시그니처(`Fn(&TransactionMut, &UpdateEvent)`)는 버전 민감 — docs.rs 확인.

## 3. 문서별 Actor (!Send 안전 + consistent hash 정합)

`Doc`/`Transaction`을 `await` 경계 너머로 들고 가지 마라(`!Send`/데드락). 문서당 **하나의 task가
Doc을 소유**하고 명령을 mpsc로 받는 actor 패턴 → "같은 문서 = 같은 인스턴스/스레드"(SDD consistent hash)와 자연 정합.

```rust
enum Cmd {
    Apply { update: Vec<u8> },
    Sync  { client_sv: Vec<u8>, reply: oneshot::Sender<Vec<u8>> },
    Subscribe { peer: broadcast::Sender<Vec<u8>> },
}

// 문서당 1 task: Doc을 소유하고 직렬 처리 (락 경합 없음)
tokio::task::spawn_local(async move {     // 또는 전용 std 스레드 + LocalSet
    let doc = Doc::new();
    while let Some(cmd) = rx.recv().await { /* match cmd → Doc 조작 (await 없이) */ }
});
```
- 트랜잭션 블록 안에서 `.await` 호출 금지 — I/O는 트랜잭션 밖에서.
- 여러 문서 = 여러 actor(문서별 격리, SDD §3.2 "동시 다문서 처리").

## 4. tonic bidi `Sync` I/F (gRPC, WS 아님)

게이트웨이(Java)↔엔진(Rust)은 **bidi 스트림 1개 유지**(매 update마다 새 호출 X). gRPC 일반은
[[grpc]] 참조 — 여기선 엔진 특화만.

```rust
async fn sync(&self, req: Request<Streaming<ClientFrame>>)
    -> Result<Response<Self::SyncStream>, Status>
{
    let doc_id = req.metadata().get("x-doc-id")    // consistent-hash 키 = 스트림 메타데이터
        .and_then(|v| v.to_str().ok()).ok_or_else(|| Status::invalid_argument("doc_id"))?;
    let mut inbound = req.into_inner();
    let (out_tx, out_rx) = mpsc::channel(256);     // 송신 큐 = 백프레셔 경계
    // inbound 읽어 doc actor에 Apply, actor broadcast를 out_tx로 → out_rx 스트림 반환
    Ok(Response::new(ReceiverStream::new(out_rx)))
}
```
- **백프레셔**: 채널 bounded. 느린 피어로 가득 차면 드롭/종료 정책(SDD §3.1).
- **OTel**: tonic 인터셉터로 `traceparent` 전파 → [[observability-otel]].

## 5. 스냅샷 & GC

- **스냅샷**: update N개 또는 T초마다 `encode_state_as_update_v1()` → PostgreSQL `bytea`. 복원은 새 `Doc`에 `apply_update`. → 스키마/sqlx는 [[database]].
- **GC**: yrs가 인접 struct 병합·삭제 콘텐츠 비움으로 tombstone 메타 축소(완전 삭제는 불가 — 완화만). 큰 문서는 주기적 스냅샷으로 복원 비용 상한.

## Anti-Patterns

1. **presence/커서를 Doc에 넣기** → tombstone 오염, 무한 성장. Awareness/Redis로 분리(SDD §6.1).
2. **매 접속에 전체 상태 전송**(`encode_state_as_update`) — `encode_diff_v1(state_vector)`로 최소 diff만.
3. **Transaction을 `.await` 너머로 보유** — `!Send` 컴파일 에러 또는 배타락 데드락. 트랜잭션은 짧게, I/O는 밖.
4. **update마다 unary RPC** — 홉·핸드셰이크 폭증. bidi 스트림 1개 유지.
5. **v1/v2 인코딩 혼용** — 클라 Yjs와 불일치로 디코드 실패. 한쪽으로 통일.
6. **스냅샷·GC 없이 update 무한 누적** — 복원 O(전체 히스토리), 메모리 증가.
7. **"래퍼"** — yrs 호출만 감싸고 최적화/벤치 없음 → 가드레일 반려. criterion 수치 동반.

## Verification Criteria

이 스킬을 적용한 엔진이 다음을 만족해야 한다:
1. **Yjs↔yrs round-trip** — 클라 Yjs가 만든 update를 서버 yrs가 적용·복원하고, 서버 diff를 클라가 적용해 동일 문서(M1 DoD).
2. **최소 diff** — 신규 접속이 `encode_diff_v1`로 자기 state vector 이후분만 수신(전체 X).
3. **수렴** — 동시 N replica에 랜덤 순서·중복 적용 → byte 동일 상태(`proptest`, [[crdt-convergence-testing]]).
4. **스냅샷 동등성** — `encode_state_as_update_v1` 복원본 == 원본 Doc 상태.
5. **presence 분리** — 커서/선택이 Doc 상태에 섞이지 않음(스냅샷에 presence 부재).
6. **`!Send` 준수** — `cargo build` 통과(Doc/Txn await 공유 없음), 트랜잭션 내 `.await` 0건.

## 참조 스킬
- `[[crdt-convergence-testing]]` — proptest 수렴 + criterion 벤치(이 엔진의 검증)
- `[[grpc]]` — gRPC/proto 일반(여기선 엔진 bidi 특화만)
- `[[msa-event-driven]]` — 스냅샷 후 doc.updated 이벤트 → 인덱싱
- `[[observability-otel]]` — Rust `tracing`+OTel, 머지 지연 메트릭
- `[[database]]` — 스냅샷 `bytea` 영속화(sqlx)

## Sources / Verified (2026-06-25)
- [yrs — docs.rs](https://docs.rs/yrs/latest/yrs/) — core API (encode_diff_v1, encode_state_as_update_v1, apply_update)
- [yrs — crates.io](https://crates.io/crates/yrs) — 0.27.2 (Yjs wire 호환)
- [y-crdt/y-crdt (GitHub)](https://github.com/y-crdt/y-crdt) — Rust 포트, 프로토콜 호환 목표
- [yrs-warp](https://github.com/y-crdt/yrs-warp) — sync 프로토콜/awareness 레퍼런스(WS; 본 엔진은 gRPC)
