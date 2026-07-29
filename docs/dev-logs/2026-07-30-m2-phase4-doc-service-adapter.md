---
date: 2026-07-30
category: decision
tier: 2
importance: major
status: resolved
tags: [m2, crdt-engine, snapshot, doc-service, tonic, keepalive, traceparent, craft-gate, mutation-test]
related:
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0022-module-structure-rust.md
  - plans/2026-07-29-m2-phase34-engine-persistence.md
  - dev-logs/2026-07-29-m2-phase34-engine-restore.md
---

# M2 Phase 4 — doc-service 복원 어댑터 (C4)

> 엔진이 처음으로 **나가는 gRPC 호출자**가 됐다. 그 과정에서 세 부류의 교훈이 나왔다:
> ① 리팩토링이 **뒤 단계의 지시문**을 stale하게 만든다 ② 설정한 줄 알았던 보호가 **꺼져 있었다**
> ③ 초록인 테스트가 **아무것도 증명하지 않고 있었다**.

머지 = engine `1a14f13` ([PR #15](https://github.com/ressKim-io/weDocs-crdt-engine/pull/15), +1,112/-7).

---

## 1. 리팩토링은 코드만 stale하게 만들지 않는다 — 다음 단계의 지시문도 그렇다

C4 절은 C3.5(ADR-0022 모듈 재편) **이전**에 쓰였다. C3.5를 끝내며 그 절의 **경로**는 고쳤지만
(`persistence.rs`·`service.rs` → `snapshot/`·`sync/`) **코드 스니펫은 그대로 뒀다.** 착수해서
그대로 따라가니 셋이 깨졌다:

| # | 원문 지시 | 왜 깨지나 |
|---|---|---|
| m1 | `pub mod doc { include_proto!("doc"); }` | `src/doc.rs`(도메인)와 **이름 충돌**. proto 패키지명과 관심사명이 같은 단어를 쓴다 → `doc_proto` |
| m2 | 어댑터를 `mod doc_service;`(비공개) | `main.rs`는 **별도 바이너리 크레이트**라 `pub(crate)`조차 닿지 않는다 → `pub mod` + "포트가 어댑터를 `use`하지 않는다"로 원 목적 유지 |
| m3 | "`doc_service_addr` 필드" (타입 미지정) | gRPC 엔드포인트는 `SocketAddr`가 **아니다**(스킴 필요) → `Option<Endpoint>` |

**교훈**: 다음 단계 지시문을 재검할 때 경로만 보면 안 된다. **이름·가시성·타입**이 같이 움직인다.
이번엔 "착수 실측" 표를 plan에 먼저 커밋하고 시작해서 비용이 정정 1커밋으로 끝났다 —
그대로 코딩부터 했으면 컴파일 에러 3개를 디버깅으로 만났을 것이다.

## 2. 켠 줄 알았던 보호가 꺼져 있었다 — hyper keepalive 기본값

```rust
// 내가 쓴 주석
/// HTTP/2 keepalive — 유휴 연결이 조용히 죽은 것(NAT·LB 타임아웃)을 다음 RPC가 아니라 PING이 찾는다.
const KEEPALIVE_INTERVAL: Duration = Duration::from_secs(30);
```

`http2_keep_alive_interval` + `keep_alive_timeout`만 설정했다. 그런데 실측(hyper 1.x
`client/conn/http2.rs`):

> "If disabled, keep-alive pings are only sent while there are open request/responses streams.
> **Default is `false`.**" — `keep_alive_while_idle`

**이 채널은 문서 open 순간 수십 ms만 스트림이 열리고 나머지는 완전 유휴다.** 즉 PING이 한 번도
나가지 않는다. 주석이 주장하는 보호가 **정확히 그 반대**로 동작하고 있었다.

**교훈**: 주석이 "이 설정은 X를 막는다"고 주장하면, 그 X가 실제로 막히는 **조건**까지 확인해야
한다. 기본값이 additive하지 않은 플래그(`while_idle` 같은 활성 조건)는 특히 그렇다.
`version-compatibility.md`가 말하는 "런타임 기본값 암묵 의존"의 전형이다.

## 3. 초록인데 아무것도 증명하지 않는 테스트 — mutation으로 판별한다

traceparent 주입 테스트를 이렇게 썼다: 어댑터를 직접 만들고, `.instrument(span)`으로 감싸
`store.load()`를 부르고, 페이크가 `traceparent`를 받았는지 단언. **초록.**

게이트 지적: 이건 "현재 span에 OTel 컨텍스트가 있으면 어댑터가 주입한다"까지만 증명한다.
실제 3-hop 전파는 `sync/mod.rs`의 `.instrument(span.clone())`에 걸려 있는데, **그 줄을 지워도
이 테스트는 초록**이고 trace만 조용히 끊긴다.

실 스트림 테스트로 교체한 뒤 **직접 확인**했다 — `.instrument(span.clone())`를 지우고 돌리니:

```
left:  "2285e3f093158759b686b85f27c61e1b"   ← 새 root trace가 생겼다
right: "4bf92f3577b34da6a3ce929d0e0e4736"   ← 인바운드 trace-id
```

주목할 점: 배선이 끊겨도 traceparent는 **여전히 실린다.** 없어지는 게 아니라 **다른 trace가
된다.** 그래서 "traceparent가 있는가"를 묻는 단언은 이 회귀를 영원히 못 잡는다. 물어야 할 것은
**"인바운드와 같은 trace인가"**다.

**교훈**: 관측성 테스트는 "신호가 있는가"가 아니라 **"신호가 올바른 것에 연결됐는가"**를 물어야
한다. 그리고 새 테스트가 뭔가를 증명한다고 믿기 전에 **의도적으로 깨뜨려 실패를 확인**한다.
(음성 대조군도 함께 뒀다 — OTel 레이어가 없으면 주입 자체가 없다는 것. 전역 subscriber가
대조군을 오염시켜 테스트 바이너리를 분리해야 했다.)

## 4. 무상한이 살아나는 시점은 "평상시"가 아니라 "복구 중"이다

`OnceCell` single-flight(C3)가 복원 RPC 중복을 막는다 — 단 **같은 doc에 대해서만.**
서로 다른 doc 사이에는 상한이 없었다.

**엔진 재시작 = 접속 중이던 모든 클라이언트가 동시 재접속 = 서로 다른 수백 개 doc의
`LoadSnapshot`이 1초 안에 몰린다.** doc-service Hikari 기본 풀은 10이다. 게다가
`grpc-timeout` 헤더를 보내도 **블로킹 JDBC 호출은 gRPC 취소로 중단되지 않는다** — 스레드가
쿼리에서 돌아올 때까지 커넥션을 쥐고 있다. 엔진은 3초에 포기하고 fail-closed → 클라 재연결 →
다시 폭주하는 metastable 루프.

plan §C6은 **저장** 경로에 `MAX_INFLIGHT_SAVES = 8`을 이미 두고 있었다. 정작 stampede를
일으키는 **복원** 경로엔 없었다 — 정상 운영에서 복원은 doc당 1회라 "핫패스가 아니다"라고
판단했기 때문이다. 그 판단은 맞지만, **상한이 필요한 이유는 평균 부하가 아니라 복구 시
동시성**이다. → `Endpoint::concurrency_limit(8)`.

## 5. "빈 값 = 미설정"의 저울은 기능이 자라면 뒤집힌다

`DOC_SERVICE_ADDR=""`를 미설정과 동일 취급했다. 근거는 "K8s `value: \"\"`나 미해결 치환으로
**켜지도 않은 기능 때문에 파드가 죽는 건** 과한 대가"였다.

게이트 지적: 그 저울은 **복원만 있는 지금**에서만 맞는다. C6(저장)이 붙고 Phase 6에서 켜는
순간 반대편 대가가 바뀐다 — "크래시루프"가 아니라 **"모든 편집이 저장되지 않고 재시작 시
전량 유실"**이고, 파드는 Ready인 채 WARN 한 줄만 남기므로 **아무 알람도 울리지 않는다.**

→ **변수 부재**(의도적 off)와 **설정했는데 빈 값**(작성 오류)을 가른다. 단일 스위치 설계는
그대로다(불린 추가 없음).

**교훈**: "실패 시 무엇을 잃는가"의 저울은 **기능이 완성되는 시점 기준**으로 달아야 한다.
지금 잃을 게 없다고 조용한 기본값을 두면, 잃을 게 생기는 시점에 아무도 그 결정을 다시 찾아오지
않는다.

## 6. 게이트 자신이 만든 위반 — 분류와 로깅을 나눈다는 규약

`classify`(tonic Code → 포트 3분류) 문서에 "분류(순수)와 로깅(부수효과)을 섞지 않는다"고
써놓고, 정작 함수 끝에서 `.tap_logged(doc_id)`를 부르고 있었다. 결과:

- 복원 실패 1건 → **로그 2줄**(어댑터 + 경계 `open_rejection`) = observability P5 위반
- 게다가 `EngineError::RestoreStore`의 Display에 `{0}`이 없어, **사유는 1번 줄에만 · 판정은
  2번 줄에만** 있었다. 운영자가 두 줄을 붙여 읽어야 한다

→ `classify`에서 로깅 제거(선언대로 순수 복원), `TapLogged`는 **삭제**(C6에서 저장 경로가
필요해지면 그쪽에서 만든다 — 지금 남기면 dead code), 에러 체인이 사유를 싣게 `{0}` 추가.

---

## 결과

크래프트 게이트(rust-expert): **Blocker 0 · Major 6 · Minor 9** → 15건 반영, 1건 이월.
`[B]` 6종 중 observability 1종 미통과 → 해소 후 통과.

**이월 → C5**: `StoredSnapshot::Present`의 필드가 enum variant라 `from_wire` 없이 직접 조립이
가능하다. C4는 지켰지만 **컴파일러가 막지 못하고**, C6가 저장 경로에서 두 번째 조립 지점을
만든다. 그 전에 newtype으로 닫는다.

최종: 64 테스트 · `clippy -D warnings` · `fmt` · CI 3종(build-test·cargo-audit·gitleaks) 초록.
