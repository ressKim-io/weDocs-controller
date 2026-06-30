# ADR-0011 — 엔진 sync/fan-out 브리지 (게이트웨이=번역기, 엔진=권위)

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: SDD §3.1·§3.2·§6 · [m1-convergence-impl plan §C·§D](../plans/2026-06-25-m1-convergence-impl.md) · [Phase 1~3 dev-log](../dev-logs/2026-06-28-m1-convergence-phase1-3.md) · 가드레일 5
- 범위: M1 수렴 본체. awareness/self-echo 필터/per-edit span = M1.5/M5(범위 밖).

## 맥락

M1 = "두 브라우저 동시 편집 수렴". 클라는 Yjs + `y-websocket`(표준 와이어: `messageSync` → `SyncStep1/2/Update`).
게이트웨이는 **Java라 `Y.Doc`이 없다** → 클라의 `SyncStep1`(state vector)에 직접 답할 수 없다(diff 계산 불가).
누가 sync를 주도하고, 동시 편집을 어떻게 fan-out하며, 어떤 인코딩으로 상호운용하는가를 정해야 했다.

제약: 가드레일 5("엔진은 엔진이다 — 최적화+벤치") · 가드레일 4(gRPC+OTel) · **proto 무변경 목표**(다운스트림 재생성 연쇄 회피).

## 결정

**게이트웨이 = 프로토콜 번역기, 엔진 = sync 권위 + fan-out 허브.**

1. **엔진이 sync 주도** — 게이트웨이는 `y-websocket 와이어 ↔ gRPC 프레임` 1:1 번역만. 엔진이 `Y.Doc`을 쥐고 SyncStep2(diff)·스냅샷을 생성.
2. **fan-out = 엔진의 per-doc `tokio::broadcast` 채널**(cap 256) — 게이트웨이는 세션 그룹핑 불필요(가드레일 5 부합). 한 세션의 update를 엔진이 같은 doc의 모든 스트림에 broadcast.
3. **모든 인코딩 lib0 v1 고정**(`encode_v1`/`decode_v1`) — Yjs 클라와 wire 호환의 전제.
4. **doc_id = gRPC 메타데이터**(`"doc-id"`) — 스트림 open 시점에 엔진이 doc를 알아야 하는 chicken-egg를 해소(첫 ClientFrame 전엔 doc 모름). `ClientFrame.doc_id`는 첫 프레임 검증용(불일치→reject).
5. **구독-후-스냅샷을 락 안에서** — 신규 스트림: 락 획득 → broadcast 구독 → 현재 상태 스냅샷 → 락 해제. lost-update 윈도 차단(락 보유 중 `.await` 금지).
6. **Lagged → 전체 상태 재전송** — 느린 수신자가 `RecvError::Lagged`로 update 유실 시 `encode_state_as_update_v1(default)`로 재수렴.

매핑: WS `SyncStep1`→`ClientFrame{state_vector}` · WS `SyncStep2|Update`→`ClientFrame{update}` · `ServerFrame{update}`→WS `Update(2)`.

## 대안 비교 (3축)

### 축 1 — fan-out 위치/방식

| 방안 | 게이트웨이 복잡도 | 가드레일 5 | self-echo | 판정 |
|---|---|---|---|---|
| **엔진 per-doc `broadcast`** (채택) | 낮음(번역만) | ✅ 엔진이 상태/fan-out 권위 | 송신자도 수신(멱등 no-op, 무해) | ✅ |
| 게이트웨이 세션 그룹 fan-out | 높음(doc별 세션 레지스트리·동기화) | ❌ 게이트웨이가 상태 보유 | 게이트웨이서 필터 | ❌ 게이트웨이 비대, 멀티인스턴스서 깨짐 |
| per-stream 채널 + sender 레지스트리 | 중간 | △ | 정확 필터 가능 | ❌ M1 과설계(self-echo 무해라 불요), M1.5 |

### 축 2 — 인코딩 버전

| 방안 | Yjs 상호운용 | 판정 |
|---|---|---|
| **lib0 v1 고정** (채택) | ✅ Yjs 클라가 디코드 가능 | ✅ |
| v2 (`encode_v2`) | ❌ Yjs 클라 디코드 불가 | ❌ 상호운용 전제 붕괴 |

### 축 3 — doc_id 전달

| 방안 | open 시 doc 식별 | proto 변경 | 판정 |
|---|---|---|---|
| **gRPC 메타데이터** (채택) | ✅ 즉시 | 없음 | ✅ |
| 첫 ClientFrame의 `doc_id` 필드 | ❌ 첫 프레임 전엔 모름(구독 못 함) | 없음 | ❌ chicken-egg (단, 검증용 보조로 병용) |

## 결과

- **proto 무변경으로 M1 완수** — 기존 `ClientFrame{doc_id,update,state_vector}`/`ServerFrame{update,state_vector}`로 SyncStep1/2/Update 전부 표현. controller proto bump·태그·다운스트림 재생성 0.
- 2클라 동시 편집 수렴 E2E green + proptest 수렴(가드레일 6) + criterion 벤치(256 concurrent ≈ 1.166ms, 가드레일 5).
- 게이트웨이 = lib0 코덱 + WS↔gRPC 번역만(JNI 없음, 가드레일 3). 엔진 = sync/fan-out/벤치(가드레일 5).
- 코드리뷰 8건 반영(doc_id 검증·full_state 부작용·핸들러 분리·손상프레임 대칭 등, [engine code-review dev-log](../dev-logs/2026-06-25-m1-engine-code-review.md)).

## 트레이드오프 (인정)

- **self-echo 미필터**(M1) → 송신자도 자기 update 수신, 트래픽 2배. 클라 applyUpdate 멱등이라 정확성 무해. 최적화 = M1.5.
- **`ServerFrame{update}`를 전부 `Update(2)`로 프레이밍** → proto가 SyncStep2 vs Update 미구분 → y-websocket `provider.synced` 미발火. M1 E2E는 'synced' 비의존 텍스트 폴링으로 우회. synced 라이프사이클 = proto 판별자 필요(M1.5).
- **Doc 미evict**(M1) → 전 세션 disconnect돼도 registry 유지(프로세스 내 재접속 복원). 프로세스 재시작=유실 → 영속화는 M2(스냅샷, [M2F-02](../plans/2026-06-30-plan-audit-improvements.md)).
- **단일 인스턴스 가정** → 멀티인스턴스 fan-out(Redis pub/sub)·consistent-hash 라우팅 = M3.
