---
date: 2026-07-29
category: decision
tier: 2
importance: major
status: resolved
tags: [m2, crdt-engine, snapshot, restore, oncecell, fail-closed, craft-gate]
related:
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0022-module-structure-rust.md
  - plans/2026-07-29-m2-phase34-engine-persistence.md
  - dev-logs/2026-07-29-rust-module-structure-and-standards-gap.md
---

# M2 Phase 3+4 — 엔진 스냅샷 복원 (C3·C3.5)

> 저장(Phase 3)보다 복원(Phase 4)을 **먼저** 넣었다. 그 순서가 데이터 유실 구간 하나를
> 통째로 없앤다. 크래프트 게이트는 그와 **같은 종류의 유실 경로를 하나 더** 잡아냈다.

## 착수 시 실측 — 상태 문서 3건이 틀렸다

재개 SSOT(`current.md`)와 부모 plan이 "`build_client` flip은 끝났으니 `SaveSnapshot` 호출
배선부터"라고 지시했는데, 셋 다 사실과 달랐다.

| 문서의 기술 | 실측 |
|---|---|
| flip 완료 → 호출 배선부터 | flip은 됐으나 `build.rs`의 `compile_protos`에 **`doc.proto`가 없어** `DocServiceClient`가 생성조차 안 된다 |
| Phase 3에서 proto 태그 bump 필요 (engine `ci.yml:16`) | **불요.** `proto-v0.2.0`에 `SaveSnapshot`·`LoadSnapshot`이 이미 있고 `git diff proto-v0.2.0 -- proto/`가 비어 있다 |
| 2b가 doc-service를 호출한다는 인상 | **아웃바운드 클라이언트가 하나도 없다.** 2b는 게이트웨이가 넘긴 `role` 메타 강제였을 뿐 |

**교훈**: "선반영 완료"라고 적힌 항목일수록 실측이 필요하다. 세 건 모두 *부분적으로만* 참이라
문서만 읽으면 틀렸다는 걸 알 수 없었다 — flip은 진짜로 됐고, 태그도 진짜로 있었고, 2b도 진짜로
role을 강제한다. 틀린 건 그로부터 **도출한 결론**이었다.

## 결정 — 복원을 저장보다 먼저

plan 번호는 Phase 3(저장) → 4(복원)이지만 실행 순서를 뒤집었다.

**저장을 먼저 넣으면 생기는 구간**: 엔진 재시작 → Doc는 빈 상태 → stale 로컬 상태를 가진 클라가
먼저 접속 → 그 상태가 권위가 됨 → 스위퍼가 **정상 DB 스냅샷을 열화된 상태로 덮어쓴다.**
version 카운터도 0으로 리셋돼 단조성이 성립하지 않는다(backend에 단조성 가드를 넣으면 재시작 후
모든 저장이 거부된다).

**복원이 먼저면 그 구간이 존재하지 않는다.** 산출물은 같고 순서만 다르다.

> 일반화: **"쓰기"와 "읽기"를 나눠 낼 때는 읽기를 먼저 낸다.** 읽기 없는 쓰기는 잘못된 상태를
> 영속화하지만, 쓰기 없는 읽기는 무해하다. 비대칭이 명확한데 번호 순서를 따를 이유가 없다.

## 핵심 구현 — `OnceCell` single-flight가 막는 것

첫 open이 `LoadSnapshot`을 await하는 동안 두 번째 세션이 구독하면, 그 세션은 **빈 문서의
state vector**를 SyncStep1로 받는다. 복원 update는 broadcast가 아니라 `Doc`에 직접 apply되므로
그 세션은 복원분을 영영 못 받고 자기 로컬 상태를 권위로 착각해 되민다 = **문서 fork**.

`DashMap<DocId, Arc<Mutex<DocEntry>>>` → `Arc<DocSlot>{ OnceCell<Mutex<DocEntry>> }`로 바꿔
`get_or_try_init`이 ① 동시 opener를 첫 initializer 뒤에 줄세우고 ② 실패를 캐시하지 않게 했다.

부수 효과 두 가지가 설계상 중요하다:
- **엔진 재시작 = 한 페이지의 모든 클라가 동시 재접속하는 순간.** single-flight가 없으면 그
  시점에 `LoadSnapshot`이 N배 증폭돼 막 살아난 doc-service를 다시 밀어버린다.
- **복원 `.await`가 `parking_lot::Mutex` 생성 *이전*에 일어난다** → "동기 락 안에서 await 금지"가
  구조적으로 지켜진다. 리뷰어가 `MutexGuard: !Send` + `Send` 요구 조합으로 **컴파일러가 이를
  증명한다**고 확인했다.

**복원 실패 슬롯을 map에서 지우지 않는다.** 지우면 `Arc<DocSlot>` 클론을 쥔 동시 opener가 고아
슬롯을 초기화하는 사이 다른 opener가 새 슬롯을 꽂아 **한 docId에 `Doc` 2개**가 생긴다 —
막으려던 fork 그 자체다. 더 교활한 건 피해 양상이다: 고아 쪽 세션의 `receiver`는 죽은 채널에
묶이는데 `apply_v1`은 map을 다시 조회해 새 슬롯에 쓰므로, 그 클라는 **영영 fan-out을 못 받는
편도 세션**이 되면서 자기 상태를 권위로 믿는다.

## 크래프트 게이트가 잡은 것 — 같은 종류의 유실 경로

`rust-expert` 게이트에서 Major 3건이 나왔고, **M1이 데이터 유실 경로**였다.

`StoredSnapshot { blob, version }` 구조체는 `(version = 5, blob = [])`라는 모순 쌍을 표현할 수
있었고, `restore`가 `blob`만 보고 분기해서 그 쌍이 조용히 **"신규 페이지"로 해석**됐다.
결과는 빈 Doc가 권위가 되고 다음 저장이 살아있는 행을 덮는 것 — **fail-closed가 막으려던 바로
그 경로인데 가드가 발화하지 않았다.** proto3가 미설정 `bytes`를 빈 값으로 주므로 C4 어댑터가
실제로 만들어낼 수 있는 쌍이다.

→ 열거형 `Absent | Present`로 바꿔 불법 상태를 표현 불가로 만들고, `from_wire`를 경계 관문으로.

**교훈**: ADR-0013 §결정 3은 분기 조건을 `version == 0 && snapshot.is_empty()`라고 **두 필드의
연언으로** 적어뒀는데 구현이 한쪽만 봤다. ADR 문언을 그대로 옮기지 않고 "같은 뜻이겠지"로
줄인 것이 원인이다. **ADR의 조건식은 축약하지 않는다.**

나머지 2건: `From<SnapshotStoreError>`가 `.to_string()`으로 원인 체인을 버린 것(error-handling
P4 Rust 금지 목록 명시), 벤치가 teardown을 측정 안에서 잰 것(criterion `iter_batched`는 입력
drop이 routine 안 — 실측 오염 `large_paste_10k` 15.5%).

## 회귀 방지

1. **`from_wire` 경계 관문** — C4 어댑터가 반드시 통과해야 하는 지점. plan §재개 지점 ⑥에 명시.
2. **fork 불변식을 성질로 고정** — `second_opener_never_sees_pre_restore_state`는 구현이 아니라
   성질을 단언해서, 나중에 구조를 바꿔도 회귀가 잡힌다.
3. **`restore_failure_is_not_cached`(`calls == 2`)** — `OnceCell` 의미론이 깨지면 저장소 일시
   장애가 그 문서를 프로세스 수명 내내 못 열게 만든다.
4. **`registry_apply` 벤치 그룹 신설** — 기존 벤치는 raw `yrs`만 돌려 `DocRegistry` 회귀를 **볼
   수 없었다**. 가드레일 5가 이 트랙에 대해 공회전 중이었다는 뜻이고, C5의 핫패스 변경 전에
   baseline을 main에 심었다.

## 산출

| | |
|---|---|
| C3 [PR #13](https://github.com/ressKim-io/weDocs-crdt-engine/pull/13) | `2ab925e` — 복원-우선 open · `SnapshotStore` 포트 · 벤치 baseline |
| C3.5 [PR #14](https://github.com/ressKim-io/weDocs-crdt-engine/pull/14) | `28e1b9c` — 모듈 구조·에러 카탈로그·설정 (상세 = [meta dev-log](2026-07-29-rust-module-structure-and-standards-gap.md)) |
| ADR | [0013 §개정](../adr/0013-snapshot-persistence-lifecycle.md) 3건 · [0022](../adr/0022-module-structure-rust.md) 신설 |

`DOC_SERVICE_ADDR` 기본 미설정이라 **동작은 아직 변하지 않았다** — 실제 배선은 C4, 실기동
검증(M2 DoD)은 C6 이후.
