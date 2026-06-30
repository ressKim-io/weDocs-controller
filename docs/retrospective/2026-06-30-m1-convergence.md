# M1 회고 — "두 탭 동시 편집 수렴" + 폴리글랏 단일 trace

> 마일스톤: **M1 (CRDT 코어)** — 리스크 우선 마일스톤. 기간: 2026-06-25 ~ 06-30.
> 검증 기준(SDD §13): "두 브라우저 동시 편집 수렴". 확장: thin 2-hop OTel trace.
> 상태: **달성** (Phase 1~5 완료). 관련 plan: [m1-convergence-impl](../plans/2026-06-25-m1-convergence-impl.md).

## 1. 무엇을 증명했나

이 프로젝트 최대 리스크(PRD §8: "Rust/CRDT 학습 곡선 — M1에 집중 배치")를 **수직 슬라이스로 먼저 증명**:

1. **Yjs(클라) ↔ yrs(Rust 서버) wire 호환** — 동일 binary format(lib0 v1)으로 상호운용. PRD §8 핵심 가정 검증 완료.
2. **두 브라우저 동시 편집 → 충돌 없이 동일 텍스트로 수렴** — E2E 실측(2클라 y-websocket, 게이트웨이 경로).
3. **수렴 정확성** — `proptest`로 교환·멱등·수렴 property 검증(가드레일 6).
4. **폴리글랏 단일 trace** — Java(gateway) span → Rust(engine) span, 같은 traceID(가드레일 4, 2-hop).

## 2. Before / After

| 항목 | Before (M0 스캐폴드) | After (M1) |
|---|---|---|
| 수렴 | 빈 스텁(엔진 `unimplemented!`) | 2클라 동시 편집 → 동일 텍스트 수렴 실측 green |
| 엔진 | yrs 래퍼 골격 | per-doc `{Doc + broadcast(256)}` fan-out + gRPC bidi `Sync` + criterion 벤치(머지 256 concurrent ≈ 1.166ms) |
| 게이트웨이 | gRPC 클라 스켈레톤 | lib0 코덱(TDD) + WS↔gRPC 번역 + 세션당 Sync 스트림 |
| trace | 없음 | Java→Rust 단일 trace 실측(traceID `eb852a8d…`) |
| proto | 정의만 | **무변경으로 완수**(기존 ClientFrame/ServerFrame로 SyncStep1/2/Update 표현) |
| CI 환경 | Mac | Linux(docker+Jaeger) 이관 → live 검증 가능 |

## 3. 잘된 것 (Keep)

- **리스크 우선 + 수직 슬라이스** — 가장 불확실한 것(Yjs↔yrs)을 가장 먼저, 최소 구성으로 증명. PRD/SDD 설계 원칙 6이 실전에서 유효.
- **write-time spec 검증** — 각 Phase 0에서 yrs 0.27 API·y-protocols 와이어 포맷·OTel 버전을 docs로 선검증("추측 코드 금지"). 와이어 1바이트 오차가 치명적인 영역에서 회귀를 사전 차단.
- **proto 무변경 달성** — 기존 계약으로 SyncStep1/2/Update를 표현 → 다운스트림 재생성·태그 bump 연쇄 회피. M1 속도의 핵심.
- **plan-logging 규율** — 재개 지점(Resume)을 단계마다 갱신 → 세션·환경(Mac→Linux) 전환에도 재도출 없이 이어감.
- **adversarial 검증이 회귀를 막음** — 감사에서 나온 "endpoint 버그 → `.with_endpoint()` 추가" 권장을 spec 검증으로 기각(넣었으면 회귀).

## 4. 어려웠던 것 / 교훈 (Improve)

- **게이트웨이는 Y.Doc이 없다** → 엔진이 sync 권위를 가져야 함(SyncStep1 응답 불가). 설계를 "게이트웨이=번역기, 엔진=권위"로 정리 → [ADR 0011](../adr/0011-engine-sync-fanout-bridge.md).
- **OTLP 기본값 함정** — javaagent 2.x 기본 프로토콜이 `http/protobuf`로 바뀌어 gRPC 포트서 export 실패. **컴파일·부팅으로는 안 잡히고 live에서만** 드러남 → live 검증의 가치. (`config-contract-audit`)
- **bidi 스트림 span 수명** — gRPC 스트리밍 client span은 스트림 종료 시 export → trace가 늦게 합류. 관측 설계 시 스트림 수명 고려.
- **문서 부채 누적** — ADR-0010이 폐기한 "submodule"이 가드레일·SDD·PRD 6곳에 잔존(매 세션 주입되는 가드레일 자기모순). M1 막바지 [감사](../dev-logs/2026-06-30-m1-plan-audit.md)로 일괄 해소. 교훈: **결정(ADR) 후 파급 표현을 즉시 전수 갱신**.
- **fresh 머신 재현성** — `make proto-sync` 선행·`cargo`/`buf` PATH 등 암묵 전제가 Linux 이관서 드러남. onboarding에 반영 필요.

## 5. 정량 지표

- 머지 처리량(criterion): 256 concurrent updates ≈ **1.166ms**(~4.5µs/update). ⚠️ 이는 엔진 핫패스 처리량이며 NFR `sync p95<100ms`(end-to-end 왕복)와는 **다른 지표**(M3 부하서 별도 측정).
- 단일 trace: 2 span(ws-gateway→wedocs-crdt-engine), 1 traceID.
- 머지된 PR: engine #1·#2, gateway #1·#2, frontend #1 (5건).
- 코드리뷰 반영: 엔진 8건, 게이트웨이 3건(2-lens).

## 6. DoD 진척 (PRD §7)

| DoD | 상태 |
|---|---|
| 두 브라우저 동시 편집 수렴 | ✅ M1 |
| CRDT 수렴 property 검증 | ✅ M1 (proptest) |
| Java→Rust→Python 단일 trace | 🔶 M1=2-hop(Java→Rust) ✅ / 3-hop(+Python)=M4 |
| 재접속 복원 / 커서 / AI / 폴백 / GitOps / README | M2~M6 (PRD §7 마일스톤 태그 참조) |

## 7. M2로 넘기는 것 (Action)

- **M2F-02 (blocker)**: 스냅샷 영속화 트리거 방향 — 엔진 `build_client(false)`라 doc-service 호출 불가 → ADR 먼저([T3](../plans/2026-06-30-plan-audit-improvements.md)).
- 인증/인가 경계(JWT·CheckPermission), outbox 방식, 복원 시퀀스 — M2 착수 전 확정.
- 횡단(M1 막바지 감사 도출): NFR 측정 매핑·DoD 트래커·서비스 CI·관측 콜사이트([T4](../plans/2026-06-30-plan-audit-improvements.md)).
