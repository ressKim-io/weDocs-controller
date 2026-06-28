---
date: 2026-06-28
category: decision
tier: 2
importance: critical
status: resolved
tags: [m1, convergence, crdt, yjs, yrs, ws-gateway, e2e, frontend, polyglot]
related:
  - plans/2026-06-25-m1-convergence-impl.md
  - dev-logs/2026-06-25-m1-engine-code-review.md
  - dev-logs/2026-06-25-m1-repo-scaffold.md
  - adr/0010-proto-distribution-buf-git-input.md
---

# M1 수직 슬라이스 수렴 증명 — Phase 1~3 (engine·gateway·frontend 머지)

프로젝트 최우선 리스크였던 **"두 브라우저가 같은 문서를 동시 편집하면 동일 상태로 수렴"**을
3개 서비스 레포(Rust 엔진 · Java 게이트웨이 · React 프론트)에 걸쳐 **end-to-end 실측 증명**했다.
Phase 1~3 전부 PR 머지 완료. proto 변경 없이(`ClientFrame`/`ServerFrame`로 SyncStep1/2/Update 표현) 완수.

> 전향(다음 할 일)·전체 체크리스트는 [plan](../plans/2026-06-25-m1-convergence-impl.md) §재개 지점. 본 dev-log는 후향(한 일·검증·교훈).

## Context

- M0(기획·proto·스캐폴딩) → M1 골격(3레포 PUBLIC) 이후, **M1 본 구현**이 본 작업.
- 핵심 가설: **Yjs(브라우저) ↔ yrs(Rust) 와이어 호환**이 깨지면 전 제품 전제가 무너진다(SDD §13, 가드레일 6).
- 설계 SSOT = [plan §A~§D](../plans/2026-06-25-m1-convergence-impl.md): 검증된 y-protocols/y-websocket 와이어 포맷,
  yrs 0.27 API, 게이트웨이=번역기·엔진=sync 권위 설계, 정합성 8결정.

## 무엇을 증명했나 (Before / After)

| | Before (M1 골격) | After (Phase 1~3 머지) |
|---|---|---|
| 수렴 | 코드 없음 — 가설만 | **2 클라이언트 동시 편집 → 동일 텍스트 수렴 실측 green** |
| 경로 | 미연결 | `브라우저 y-websocket → ws-gateway(8080) → crdt-engine(50051) → fan-out` 동작 |
| 가드레일 6 | 미충족 | **proptest 수렴(commutative/associative/idempotent) green** (Phase 1) |
| 상호운용 | 미검증 | 모든 인코딩 **lib0 v1 고정** → Yjs 클라가 디코드 가능 확인 |

## Phase별 산출물 (3 PR 머지)

| Phase | 레포 / PR | 핵심 |
|---|---|---|
| **1** crdt-engine (Rust) | weDocs-crdt-engine#1, merge `fbd25fe` | per-doc `{Doc + tokio::broadcast(cap 256)}`, gRPC bidi `Sync` 브리지, `apply_v1`/`diff_v1`/`full_state_v1`. proptest 3 + fanout 3 green, criterion 벤치(~1.17ms/256 update). rust-expert+code-reviewer 8건 반영([code-review dev-log](2026-06-25-m1-engine-code-review.md)). |
| **2** ws-gateway (Java) | weDocs-backend#1, merge `e0e8277` | `Lib0`(varUint/varBuffer) TDD, `YProtocolCodec`, `EngineClient.openSync`(메타데이터 `doc-id`), `DocWebSocketHandler`(세션당 Sync 스트림, 단일 writer, `computeIfPresent` 원자화). 22 test pass, java-expert+code-reviewer 2-lens 반영. |
| **3** frontend (React) | weDocs-frontend#1, merge `e8f0c83` | `Editor.tsx` room=`?room=` 다중문서, `test/e2e/convergence.e2e.test.ts`(vitest, 2클라 y-websocket+ws). `npm run test:e2e` + `npm run build` green. |

## 핵심 설계 결정 (plan §D 요약 — ADR 후보)

1. **게이트웨이 = 프로토콜 번역기, 엔진 = sync 권위.** Java엔 `Y.Doc`이 없어 SyncStep1에 답할 수 없으므로
   엔진이 sync를 주도. 게이트웨이는 `y-websocket 와이어 ↔ gRPC 프레임` 1:1 번역만(가드레일 5 "엔진이 엔진이다" 부합).
2. **fan-out = 엔진의 per-doc `tokio::broadcast`.** 게이트웨이는 세션 그룹핑 불필요. 송신자 self-echo는
   클라 `applyUpdate` 멱등이라 무해(M1은 미필터, 트래픽 2배는 M1.5 최적화).
3. **doc_id = gRPC 메타데이터(`"doc-id"`).** open 시점엔 ClientFrame이 없어 엔진이 doc를 모르는 chicken-egg →
   메타데이터로 open 즉시 해결. `ClientFrame.doc_id`는 첫 프레임 검증용(불일치=세션 종료).
4. **모든 인코딩 v1 고정.** v2 메서드는 Yjs 클라가 디코드 불가 → 상호운용의 전제.
5. **ServerFrame{update} = 전부 WS `Update(2)`로 프레이밍.** proto가 SyncStep2 vs Update를 구분 안 함.
   클라에선 둘 다 `applyUpdate`로 동일. 단 `provider.synced`는 set 안 됨 → **E2E는 'synced' 비의존 텍스트 폴링**.
6. **구독-후-스냅샷을 락 안에서**(lost-update 윈도 차단) · **broadcast Lagged → 전체 상태 재전송**으로 재수렴.

## 검증 방법 (실측 — "추정 통과" 금지, deep-thinking.md)

- **로컬 풀스택 실기동**: engine `cargo run`(:50051) + gateway bootJar(:8080) → `npm run test:e2e` **2회 green**(168ms / 978ms).
- **false-positive 회피 2중 확인**:
  - E2E에서 `disableBc: true` — 같은 프로세스 두 클라가 **BroadcastChannel로 게이트웨이를 우회하면 거짓 green**.
    꺼서 반드시 `ws-gateway↔engine` 경로만 통과시킴.
  - gateway 로그가 **테스트 시각(17:17:48)에 WS 핸들러 + gRPC `TcpMetrics` 초기화** → gRPC 스트림이 실제로 열렸음 확인.
- **실행마다 고유 room** — 엔진이 M1에서 Doc을 evict하지 않으므로(plan §D-8) 'demo' 재사용 시 이전 실행 상태가 누적 → 오염 차단.
- `npm run build`(tsc --noEmit + vite) green.

## 교훈

- **검증 경로를 의심하라.** 단일 프로세스 멀티 클라 테스트는 사이드 채널(BroadcastChannel)로 거짓 green이 나기 쉽다.
  "무엇을 통과시키지 않아야 하는가"(`disableBc`)를 먼저 못 박고, 로그로 실경로를 교차 확인해야 진짜 증명.
- **proto를 안 바꾸고도 수직 슬라이스가 가능**했다 — 기존 `ClientFrame`/`ServerFrame` 3필드로 SyncStep1/2/Update를
  전부 표현. 'synced' 라이프사이클·awareness는 proto bump가 필요해 M1.5로 분리(스코프 규율).
- **신규 도구는 write-time spec 검증**(workflow.md): y-websocket 3.0 `WebsocketProvider` opts(`WebSocketPolyfill`/`disableBc`),
  이벤트 emit 형태(`status`→`{status:'connected'}`)를 node_modules 소스로 직접 확인 후 작성 — 추측 코드 0.

## 다음 (M1 잔여)

- **Phase 4** — OTel 폴리글랏 trace: gateway(Java)→engine(Rust) gRPC 메타데이터 `traceparent` 2-hop 전파(가드레일 4 + showcase).
- **Phase 5** — 마감: 본 수렴 증명을 ADR(엔진 sync/fan-out 브리지 설계, 대안 비교표)로 승격 + plan `done`.
- M1.5 백로그: awareness(커서) · 'synced' 라이프사이클 · self-echo 필터 · 브라우저-origin trace span (전부 proto/최적화 의존).
