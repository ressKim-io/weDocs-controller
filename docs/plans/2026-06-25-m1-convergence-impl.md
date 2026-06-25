---
date: 2026-06-25
slug: m1-convergence-impl
status: planned
related:
  - plans/2026-06-25-m1-repo-scaffold.md
  - adr/0010-proto-distribution-buf-git-input.md
  - dev-logs/2026-06-25-m1-repo-scaffold.md
---

# weDocs — M1 본 구현: "두 탭 동시 편집 수렴" 증명

스캐폴드(`2026-06-25-m1-repo-scaffold.md`, done)의 빈 스텁을 채워 **두 브라우저가 같은 문서를
동시 편집하면 동일 상태로 수렴**함을 증명한다. 엔진(Rust yrs) 우선.

## Context

### 검증된 와이어 포맷 (공식 출처, 2026-06-25 ✅ verified)

게이트웨이 코덱의 린치핀 — 추측 금지(deep-thinking.md). 출처:
yjs/y-protocols `master` (`src/sync.js`, `PROTOCOL.md`) · yjs/y-websocket `master` (`src/y-websocket.js`).

| 레이어 | 상수 | 프레이밍 |
|---|---|---|
| y-websocket top-level | `messageSync=0` · `messageAwareness=1` · `messageAuth=2` · `messageQueryAwareness=3` | `varUint(type) • payload` |
| y-protocols sync 서브 | `SyncStep1=0`(state vector) · `SyncStep2=1`(diff update) · `Update=2`(update) | `varUint(subtype) • varBuffer(payload)` |
| 클라 접속 시 | y-websocket client는 즉시 `messageSync → SyncStep1(SV)` 송신 | — |

- `varBuffer` = `varUint(len) • bytes` (lib0 `writeVarUint8Array`). 작은 값(0/1/2)은 1바이트 varUint.
- `writeSyncStep1` → `Y.encodeStateVector`, `writeSyncStep2` → `Y.encodeStateAsUpdate(doc, sv)`, `writeUpdate` → update 그대로.
  `readSyncMessage`: type0→readSyncStep1(→step2로 응답), type1·2→`Y.applyUpdate`.

### 핵심 설계 결정

**게이트웨이 = 프로토콜 번역기, 엔진 = sync 권위(authority).**
게이트웨이는 Java라 `Y.Doc`이 없어 SyncStep1에 답할 수 없음 → 엔진이 sync 주도.
게이트웨이는 `y-websocket 와이어 ↔ gRPC 프레임` 1:1 번역만. **fan-out은 엔진의 per-doc broadcast 채널**
(가드레일 5 "엔진이 엔진이다"에 부합 — 게이트웨이는 per-doc 세션 그룹핑 불필요).

```
세션당 1 gRPC Sync 스트림
─ 스트림 open            → 엔진: ServerFrame{state_vector}        (= 클라에 SyncStep1)
─ ClientFrame{state_vector} → 엔진: ServerFrame{update}           (= SyncStep2 diff)
─ ClientFrame{update}       → 엔진: apply_update + broadcast.send
─ broadcast 수신(타 세션)   → 엔진: ServerFrame{update}            (= Update fan-out)
```

매핑(게이트웨이): WS `SyncStep1` → `ClientFrame{state_vector}`; WS `SyncStep2|Update` → `ClientFrame{update}`.
역방향: `ServerFrame{state_vector}` → WS `SyncStep1`; `ServerFrame{update}` → WS `SyncStep2|Update`.

- **proto 변경 불필요** ✅ — 현 `ClientFrame{update,state_vector}` / `ServerFrame{update,state_vector}`로
  SyncStep1/2/Update 전부 표현. controller proto bump·새 태그 없음.
- **doc_id** = M1은 `ClientFrame.doc_id`(URL room)로 라우팅. gRPC 메타데이터 consistent-hash는 infra 마일스톤 연기.
- **awareness(커서)** = M1 범위 밖(연기). proto에 새 채널 필요 → M1.5. 수렴 증명엔 불필요.
- **OTel 폴리글랏 trace** = M1 포함(Phase 4, 가드레일 4 + showcase).

### 워크플로 제약 (중요)

- **controller**: main 직접 commit·push 허용 (CLAUDE.md). Phase 0/5는 직접.
- **서비스 레포**(crdt-engine/backend/frontend): 일반 룰 = **branch + PR + 건별 승인**. Phase 1~4 각 PR push/create는 사용자 건별 승인 필요(user-approval.md). 에이전트가 직접 push·PR 생성 금지.

---

## 실행 체크리스트

### Phase 0 — plan 기록 (controller, main 직접)
- [ ] 이 파일 작성 + commit `docs(plans): M1 convergence impl plan` ← **이 커밋 후 코드 작업 시작**

### Phase 1 — crdt-engine 머지 + fan-out (Rust) ★ 가드레일 게이트
- [ ] `engine.rs`: `DocRegistry` per-doc `{Doc + tokio::sync::broadcast::Sender<Vec<u8>>}`.
      `apply_update(doc_id, &[u8])` / `encode_state_as_update(doc_id, sv)` / `encode_state_vector(doc_id)` / `subscribe(doc_id)`
- [ ] `service.rs`: `Sync` bidi 실구현 — open 시 SyncStep1 송신, `ClientFrame{state_vector}`→SyncStep2,
      `ClientFrame{update}`→apply+broadcast, broadcast→`ServerFrame{update}` fan-out. `GetSnapshot` = encode_state_as_update 전체
- [ ] `tests/convergence_proptest.rs`: 본문 — 교환(순서 무관)·멱등·수렴(두 doc 상호 교환→동일). yrs 상태 비교 (가드레일 6)
- [ ] tonic in-process 통합테스트: 2 클라 스트림 concurrent updates → 수렴 검증
- [ ] `benches/convergence.rs`: 머지 핫패스 criterion 벤치 (가드레일 5)
- [ ] VERIFY: `cargo test` (proptest green) + `cargo bench --no-run` 컴파일 → rust-expert cross-check
- [ ] branch `feature/m1-merge-fanout` + PR (승인 후 push/create)

### Phase 2 — ws-gateway 브리지 (Java) — 최고위험 TDD
- [ ] lib0 코덱(`varUint`/`varBuffer` 인코드·디코드) — **테스트 먼저**(Red→Green). y-websocket/sync 프레임 파싱·생성
- [ ] `DocWebSocketHandler`: WS 세션당 `EngineClient.Sync` 스트림 open(StreamObserver). doc_id=URL room.
      inbound WS→ClientFrame, inbound ServerFrame→WS 프레임. 세션 close 시 스트림 정리
- [ ] `EngineClient`: `asyncStub.sync(responseObserver)` bidi 연결 진입점 구현. VT 유지·JNI 미사용(가드레일 3)
- [ ] 테스트: 코덱 단위테스트 + (raw WS 클라 ↔ gateway ↔ 실제 engine) 통합테스트
- [ ] VERIFY: `./gradlew test` → java-expert cross-check
- [ ] branch + PR (승인 후)

### Phase 3 — frontend 검증 + E2E 수렴 (React) — 헤드라인 산출물
- [ ] `Editor.tsx` 표준 provider 유지. (선택) room=docId 다중 문서
- [ ] **E2E 수렴 테스트**: 2 클라이언트(2 Y.Doc + provider, 또는 Playwright 두 탭) concurrent edit → 동일 텍스트 assert
- [ ] VERIFY: `npm run build` + 로컬 engine+gateway 기동 후 E2E green
- [ ] branch + PR (승인 후)

### Phase 4 — OTel 폴리글랏 trace 전파 (3 repos) 가드레일 4 + showcase
- [ ] gateway→engine gRPC에 W3C `traceparent` 전파 (Java OTel auto-instr + Rust tonic OTel layer)
- [ ] 한 편집 요청이 React→Java→Rust **단일 trace**로 보이는지 확인(스크린샷/로그)
- [ ] VERIFY: trace에 3개 span(브라우저 origin·gateway·engine) 연결 확인 → otel-expert cross-check
- [ ] branch + PR (승인 후)

### Phase 5 — 마감 (controller, main 직접)
- [ ] dev-log: 수렴 증명 결과(Before/After·검증 방법·교훈)
- [ ] ADR: 엔진 sync/fan-out 브리지 설계(게이트웨이=번역기, 엔진=권위, broadcast fan-out) — 대안 비교표
- [ ] 이 plan `status: done` + dev-log 링크 + commit

---

## 검증

| 대상 | 명령 | 게이트 |
|---|---|---|
| engine | `cargo test`(proptest 수렴 green) · `cargo bench --no-run` | 가드레일 5·6 |
| gateway | `./gradlew test`(코덱 단위 + 통합) | TDD(testing.md) |
| frontend | `npm run build` + E2E(2클라 수렴) green | 헤드라인 |
| 전체 | 로컬 engine(50051)+gateway(8080) 기동 → 두 탭에서 `ws://localhost:8080/ws/doc/demo` 동시 편집 → 동일 텍스트 | M1 정의 |
| OTel | React→Java→Rust 단일 trace 연결 | 가드레일 4 |

- 로컬 환경(buf 1.71·cargo 1.96·java 25.0.3·node 26·gh 2.95) 설치 확인 → 모든 검증 실행 가능.
- 못 돌린 검증은 "추정 통과" 금지, "미실행" 명시(deep-thinking.md).

## 범위 밖

doc-service·ai-service / 스냅샷 DB 영속화 / Istio 메타데이터 consistent-hash 라우팅 / 멀티-인스턴스 엔진 /
**awareness(커서) — M1.5 연기**(proto bump 필요) / 인증·인가.

---

## 재개 지점 (Resume)

> **마지막 완료**: plan 작성(Phase 0 진행 중). 스코프 확정 = awareness 연기 / OTel M1 포함.
> **다음 작업**: Phase 0 커밋 → Phase 1 crdt-engine(rust-expert) — `engine.rs` per-doc broadcast + `service.rs` Sync bidi 실구현 + proptest 수렴 본문(가드레일 게이트).
> **주의**: 서비스 레포 3개는 branch+PR+건별 승인. proto 불변(현 계약 충분) → controller proto bump 없음.
> **주의**: 와이어 상수는 Context 표 참조(검증 완료). 게이트웨이 코덱은 TDD 최고위험.
> **환경**: buf 1.71 · cargo 1.96 · java 25.0.3 · node 26 · gh 2.95.
