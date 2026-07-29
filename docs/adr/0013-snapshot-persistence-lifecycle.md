# ADR-0013 — 스냅샷 영속화 라이프사이클 (엔진 push + 복원)

- 상태: **Accepted**
- 날짜: 2026-06-30 (**개정 2026-07-29** — §개정 3건)
- 관련: [ADR-0011](0011-engine-sync-fanout-bridge.md) (트레이드오프 "Doc 미evict") · SDD §3.2·§6.3 · [plan-audit M2F-02](../plans/2026-06-30-plan-audit-improvements.md) (T3-1 blocker) · [M2 plan](../plans/2026-06-30-m2-persistence-session.md) · [Phase 3+4 실행 계획](../plans/2026-07-29-m2-phase34-engine-persistence.md) · 가드레일 5
- 범위: M2 스냅샷 저장/복원. 멀티인스턴스 중복저장 방지(consistent-hash)·Redis 버퍼 복원 = M3/M5(범위 밖).

## 맥락

ADR-0011 트레이드오프: 엔진은 Doc를 evict하지 않으나 **프로세스 재시작 = 전 데이터 유실**(in-memory only). M2 = 영속화 + 재접속/장애 복원.

핵심 blocker(**M2F-02**): `crdt-engine/build.rs`가 `.build_client(false)` → 엔진에 **아웃바운드 gRPC 클라이언트 stub이 없다** → 엔진이 doc-service를 호출할 방법이 물리적으로 없다. SDD §3.2는 "엔진이 Postgres에 스냅샷 저장"이라 적었으나 트리거 메커니즘이 미정이었다. **이 방향이 안 정해지면 엔진 스레드 모델·트랜잭션 경계·proto가 전부 미정 → M2 첫 줄 불가.**

제약: 가드레일 5(엔진=권위), 가드레일 3(JNI 금지 — gRPC는 허용), 가드레일 4(gRPC+OTel).

## 결정

**엔진 push** — 엔진이 스냅샷 저장의 권위·트리거 주체.

1. **`build.rs` `build_client(true)` flip** — 엔진에 doc-service gRPC 클라이언트 stub 생성.
2. **저장 트리거** = debounce + 상한: **마지막 update 후 `T`초 유휴** OR **누적 `N` updates** 중 먼저 도달 시 `encode_state_as_update_v1(default)` → `DocService.SaveSnapshot(page_id, blob, version)`. 제안 초기값 **T=10초, N=100 updates**(아래 정량 근거).
3. **복원** = doc ensure(첫 구독) 시: 엔진 → `DocService.LoadSnapshot(doc_id)`(proto 필드 `doc_id`=`page_id`, ADR-0012) → 응답 분기:
   ```
   if version == 0 && snapshot.is_empty():   # 신규 페이지(저장 이력 없음)
       빈 Doc 그대로 사용 (apply 없음)
   else:
       apply_update_v1(&snapshot)             # lib0 v1 디코드+적용 단일 호출
   이후 → SyncStep2로 신규 클라에 전달
   ```
   (기존 `CrdtEngine.GetSnapshot`은 엔진 in-memory 읽기라 재시작 후엔 빈 상태 → 복원에 재사용 불가, `LoadSnapshot` 신설.)
4. **보장 경계** = 최종 스냅샷. 스냅샷 사이 in-flight update 유실 허용. Redis 버퍼로 무손실 복원 = **M5**.
5. **버전 체계** = **엔진이 권위**. 엔진이 doc당 단조 증가 카운터를 유지(재시작 시 `LoadSnapshotResponse.version`으로 초기화) → `SaveSnapshotRequest.version`에 현재 값 전달. doc-service는 `page_snapshots`를 `UPSERT ON CONFLICT(page_id) DO UPDATE`로 **최신 1행만 유지**, 받은 버전을 그대로 저장 후 `SaveSnapshotResponse.version`으로 echo(재할당 안 함). 신규 페이지 = `LoadSnapshot`이 `version=0`·빈 blob 반환.

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

- **build_client(true) = 엔진에 outbound 의존 추가** — 엔진이 doc-service에 의존하게 됨(단방향). gRPC라 가드레일 3(JNI) 무관. doc-service 다운 시 저장 실패 → 재시도 정책은 **아래 §개정 2026-07-29 (1)** 참조(원안 "3회 후 드롭"에서 변경).
- **멀티인스턴스 중복저장** — 단일인스턴스 가정. M3 consistent-hash(doc당 1엔진) 전까지 같은 doc을 두 엔진이 들면 중복 저장 가능. M3에서 해소.
- **in-flight 유실 허용** — 스냅샷 사이 update는 재시작 시 유실. MLP 수용(무손실=Redis 버퍼 M5).

## 개정 2026-07-29 — 구현 착수 시 확정한 3건

> 상태 **Accepted 유지**. 결정(§결정 1~5)은 그대로이고, 구현이 닿아서야 드러난 공백 3건을 채운다.
> 실행 계획 = [plans/2026-07-29-m2-phase34-engine-persistence](../plans/2026-07-29-m2-phase34-engine-persistence.md).

### (1) 재시도 정책 — "3회 후 드롭" → 분류별 처리

**원안**: 3회 지수 백오프 재시도, 소진 시 경고 로그 + 드롭.
**개정**: 실패를 3분류하고 분류별로 다르게 처리한다.

| 분류 | gRPC code | 처리 |
|---|---|---|
| Transient | `Unavailable`·`DeadlineExceeded`·`Cancelled`·`ResourceExhausted`·`Aborted`·`Internal`·`Unknown`·`DataLoss` | **상한 백오프(최대 ~1분)로 무기한 재시도** |
| NotPersistable | `NotFound`(page 행 부재) · `InvalidArgument`(doc_id 비UUID) | 그 문서의 영속화 **즉시 영구 비활성** + WARN |
| Permanent | `Unimplemented`·`PermissionDenied`·`Unauthenticated`·`FailedPrecondition` | 영구 비활성 + **ERROR**(설정 오류·proto 스큐 신호) |

**왜 바꿨나**: 원안은 "재시도 단위 = 보관 중인 페이로드"를 암묵 전제했다. 실제 설계에서 스위퍼는
**매 시도마다 살아있는 Doc에서 블롭을 재인코딩**하므로 드롭할 페이로드가 존재하지 않는다.
그래서 재시도 비용이 "백오프 창당 RPC 1회"로 고정되고, 3회에서 멈출 이유가 사라진다 — 멈추면
doc-service 재시작이 백오프 창보다 오래 걸렸을 때 유실만 커진다. 반대로 원안은 영구 실패
(비UUID doc_id 등)를 3회씩 두드리는데, 이건 결과가 바뀌지 않는 낭비다. **재시도할 가치가
있는 것은 무기한, 없는 것은 0회**가 정확한 배분이다.

### (2) 복원 실패 시 동작 = fail-closed (§결정 3의 공백)

§결정 3은 `LoadSnapshot` **성공** 시 분기만 규정했고 실패 시를 정하지 않았다.
→ **복원 실패 시 sync 스트림을 열지 않는다**(`Status::unavailable`). 손상된 블롭의 디코드 실패도 동일.

**왜**: 빈 Doc로 열면 클라가 자기 로컬 상태를 권위로 착각해 되밀고, 그 상태를 다음 저장이 DB에
확정시킨다 = **영구 유실**. 관측 가능한 거부(재연결 루프)가 관측 불가능한 조용한 덮어쓰기보다 낫다.
**대가**: doc-service 다운 = 편집 전면 불가(엔진이 doc-service에 하드 의존). 가용성보다 문서
무결성을 택한다 — 협업 문서에서 fork는 사후 복구가 사실상 불가능하기 때문이다.

### (3) 저장 트리거 T의 표현 = 시각 델타가 아니라 유휴 tick 수

§결정 2의 "마지막 update 후 T초 유휴"를 **`SWEEP_INTERVAL(1초) × SAVE_IDLE_TICKS(10)`**로 구현한다
(T=10초는 불변). 전역 스위퍼가 1초마다 문서별 `try_lock`으로 훑고, 머지 카운터가 직전 tick과
같으면 유휴 tick을 올린다.

**왜**: ① 머지 핫패스에서 `Instant::now()`가 사라져 정수 증가 1회만 남고 ② `try_lock`이라
스위퍼가 머지를 **한 번도 막지 않으며**(가드레일 5) ③ 디바운스 테스트가 `sweep_once()`를 10번
호출하는 것으로 끝나 시계 주입·`tokio::time::pause`·sleep이 전부 불필요해진다.
**대가**: 저장 시점에 최대 1 tick(1초)의 지연이 더해진다 — T=10초 대비 무시 가능.
