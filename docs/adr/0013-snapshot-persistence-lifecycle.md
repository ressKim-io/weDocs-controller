# ADR-0013 — 스냅샷 영속화 라이프사이클 (엔진 push + 복원)

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: [ADR-0011](0011-engine-sync-fanout-bridge.md) (트레이드오프 "Doc 미evict") · SDD §3.2·§6.3 · [plan-audit M2F-02](../plans/2026-06-30-plan-audit-improvements.md) (T3-1 blocker) · [M2 plan](../plans/2026-06-30-m2-persistence-session.md) · 가드레일 5
- 범위: M2 스냅샷 저장/복원. 멀티인스턴스 중복저장 방지(consistent-hash)·Redis 버퍼 복원 = M3/M5(범위 밖).

## 맥락

ADR-0011 트레이드오프: 엔진은 Doc를 evict하지 않으나 **프로세스 재시작 = 전 데이터 유실**(in-memory only). M2 = 영속화 + 재접속/장애 복원.

핵심 blocker(**M2F-02**): `crdt-engine/build.rs`가 `.build_client(false)` → 엔진에 **아웃바운드 gRPC 클라이언트 stub이 없다** → 엔진이 doc-service를 호출할 방법이 물리적으로 없다. SDD §3.2는 "엔진이 Postgres에 스냅샷 저장"이라 적었으나 트리거 메커니즘이 미정이었다. **이 방향이 안 정해지면 엔진 스레드 모델·트랜잭션 경계·proto가 전부 미정 → M2 첫 줄 불가.**

제약: 가드레일 5(엔진=권위), 가드레일 3(JNI 금지 — gRPC는 허용), 가드레일 4(gRPC+OTel).

## 결정

**엔진 push** — 엔진이 스냅샷 저장의 권위·트리거 주체.

1. **`build.rs` `build_client(true)` flip** — 엔진에 doc-service gRPC 클라이언트 stub 생성.
2. **저장 트리거** = debounce + 상한: **마지막 update 후 `T`초 유휴** OR **누적 `N` updates** 중 먼저 도달 시 `encode_state_as_update_v1(default)` → `DocService.SaveSnapshot(page_id, blob, version)`. 제안 초기값 **T=10초, N=100 updates**(아래 정량 근거).
3. **복원** = doc ensure(첫 구독) 시: 엔진 → `DocService.LoadSnapshot(page_id)` → `decode_v1` → `apply_update` → 이후 SyncStep2로 신규 클라에 전달. (기존 `CrdtEngine.GetSnapshot`은 엔진 in-memory 읽기라 재시작 후엔 빈 상태 → 복원에 재사용 불가, `LoadSnapshot` 신설.)
4. **보장 경계** = 최종 스냅샷. 스냅샷 사이 in-flight update 유실 허용. Redis 버퍼로 무손실 복원 = **M5**.

## 대안 비교 (트리거 방향, 3축)

| 방안 | 가드레일 5 정합 | 멀티인스턴스 중복저장 | 트랜잭션 경계 | who-is-dirty 인지 | 판정 |
|---|---|---|---|---|---|
| **A. 엔진 push** (`build_client(true)`) (채택) | ✅ 엔진=상태 권위가 저장도 주도 | 단일인스턴스 가정(M3 consistent-hash가 doc당 1엔진 보장) | 엔진이 dirty 시점 정확히 앎 | ✅ 엔진이 dirty 추적 | ✅ |
| B. doc-service pull (`GetSnapshot` 폴링) | △ 저장 권위가 엔진 밖 | 폴링 주체 1개라 중복 없음 | doc-service가 "언제 dirty인지" 모름 | ❌ 전수 폴링 낭비 또는 별도 신호 필요 | ❌ who-is-dirty 모호, 폴링 낭비 |
| C. 게이트웨이 중개 | ❌ 번역기가 상태/저장 보유 | — | 게이트웨이가 상태 추적해야 | ❌ | ❌ ADR-0011 "게이트웨이=무상태 번역기" 위반 |

→ **A 채택**: 엔진이 이미 Doc 상태·update 카운트를 쥐고 있어 dirty 시점을 정확히 안다. 저장 권위를 상태 권위(엔진)와 일치시키는 것이 단일 책임.

## 정량 근거 (트리거 임계 T=10초 / N=100)

- **너무 잦은 저장**(매 update) = write amplification: `encode_state_as_update_v1`는 전체 상태 직렬화라 doc 크기에 비례. 초당 수십 update × 전체 직렬화 = Postgres I/O 폭증.
- **너무 드문 저장** = 유실 윈도 확대: 재시작 시 마지막 스냅샷 이후 전부 유실.
- debounce(유휴 10초)는 "타이핑 멈춤" 자연 경계에 저장 → 대부분의 편집 세션을 1~2회 저장으로 커버. 상한 N=100은 끊임없는 편집 시 유실 윈도를 bound. 실측 후 M2 구현에서 조정(엔진 PR 벤치).

## 결과

- **M2F-02 blocker 해소** → M2 엔진 작업(Phase 3 저장 / Phase 4 복원) 착수 가능.
- proto-v0.2.0: `DocService.LoadSnapshot` 신설(additive). `SaveSnapshot`은 기존 계약 사용.
- 엔진 스레드 모델: 저장은 broadcast 핸들러 밖 별도 태스크(`spawn`)로 — 머지 핫패스(가드레일 5) 비차단. 락 보유 중 `.await` 금지(ADR-0011 원칙 계승).
- M2 DoD "재접속 복원" 검증 경로 확정.

## 트레이드오프 (인정)

- **build_client(true) = 엔진에 outbound 의존 추가** — 엔진이 doc-service에 의존하게 됨(단방향). gRPC라 가드레일 3(JNI) 무관. doc-service 다운 시 저장 실패 → 재시도/백오프 필요(엔진 PR에서 처리).
- **멀티인스턴스 중복저장** — 단일인스턴스 가정. M3 consistent-hash(doc당 1엔진) 전까지 같은 doc을 두 엔진이 들면 중복 저장 가능. M3에서 해소.
- **in-flight 유실 허용** — 스냅샷 사이 update는 재시작 시 유실. MLP 수용(무손실=Redis 버퍼 M5).
