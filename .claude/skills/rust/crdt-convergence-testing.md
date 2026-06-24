---
name: crdt-convergence-testing
description: "Rust CRDT 엔진의 수렴 정확성·성능 검증 — proptest로 commutative/associative/idempotent(랜덤 op 순열·중복 → 동일 상태), criterion으로 머지/diff/스냅샷 벤치, Yjs↔yrs 상호운용 테스트. Use when CRDT 머지 수렴을 property로 증명하거나 '래퍼 대비 N배' 성능을 정량화할 때."
effort: max
---

# CRDT Convergence & Benchmark Testing

CRDT의 생명은 **수렴**(어떤 머지 순서·중복에도 모든 replica가 동일 상태)이다. 이는 예제 몇 개로
보장되지 않으므로 **property-based testing**으로 수천 케이스를 돌린다. Synapse 가드레일:
**M1 머지 전 proptest 수렴 통과 필수**(SDD §11/§14).

> CRDT 머지는 수학적으로 **commutative · associative · idempotent**여야 한다 → 이 세 성질을 property로 검증.

## Quick Reference (결정 트리)

```
무엇을 검증?
├─ 수렴(정확성) ─ proptest: 랜덤 op 시퀀스를 여러 순서로 적용 → 모든 replica 동일?
│   ├─ commutative : 같은 op 집합, 순서만 셔플 → 동일 상태
│   ├─ associative : 부분 머지 그룹핑 달라도 → 동일 상태
│   └─ idempotent  : 같은 update 2번 적용 → 상태 불변
├─ 상호운용 ─ Yjs(JS) update ↔ yrs(Rust): round-trip 동일 (M1 필수)
└─ 성능 ─ criterion: 머지/diff/스냅샷 throughput, "naive 래퍼 대비" 비교
```

## 1. proptest 수렴 (commutativity)

```rust
use proptest::prelude::*;
use yrs::{Doc, Text, Transact};

// 1) op 모델: 위치+텍스트 삽입/삭제 등 도메인 연산
#[derive(Clone, Debug)]
enum Op { Insert { idx: u32, s: String }, Delete { idx: u32, len: u32 } }

fn ops_strategy() -> impl Strategy<Vec<Op>> { /* prop::collection::vec(...) */ }

proptest! {
    #[test]
    fn converges_under_any_order(ops in ops_strategy(), seed in any::<u64>()) {
        // 2) replica A: ops 순서대로 적용 → 각 단계 update 수집
        let updates = apply_and_capture(&ops);

        // 3) replica B: 같은 update들을 셔플 순서로 적용
        let mut shuffled = updates.clone();
        shuffle_with_seed(&mut shuffled, seed);

        let a = build_doc(&updates);
        let b = build_doc(&shuffled);

        // 4) 수렴: 두 Doc의 정규화된 상태가 동일해야 함
        prop_assert_eq!(state_bytes(&a), state_bytes(&b));
    }
}

fn state_bytes(doc: &Doc) -> Vec<u8> { doc.transact().encode_state_as_update_v1() }
```
- **셔플 순서**가 핵심(commutativity). seed로 재현 가능. 실패 시 proptest가 **최소 케이스로 자동 축소**.
- **비교는 정규화 상태로**: 두 replica가 동일 update 집합을 모두 받았을 때 `encode_state_as_update_v1` 결과(또는 텍스트 평탄화)가 같아야 한다.

## 2. idempotence & associativity

```rust
proptest! {
    #[test]
    fn idempotent(ops in ops_strategy()) {
        let updates = apply_and_capture(&ops);
        let once  = build_doc(&updates);
        let twice = build_doc(&[updates.clone(), updates].concat()); // 중복 적용
        prop_assert_eq!(state_bytes(&once), state_bytes(&twice));    // 상태 불변
    }
}
```
associativity: update를 그룹별로 먼저 머지(부분 합) 후 합치기 vs 순차 적용 → 동일.

## 3. Yjs ↔ yrs 상호운용 (M1 필수)

순수 Rust 수렴만으론 부족 — **클라 Yjs(JS)와의 wire 호환**을 별도 검증.
```
[JS] Yjs Doc 편집 → encodeStateAsUpdate → bytes ─┐
                                                  ├─ [Rust] apply_update → 동일 텍스트?
[Rust] yrs 편집 → encode_state_as_update_v1 ──────┘ → [JS] applyUpdate → 동일 텍스트?
```
- 고정 코퍼스 바이트를 양 언어에 넣고 양방향 round-trip. CI에서 JS↔Rust 교차 실행(Node + cargo).
- v1 인코딩 통일 확인([[crdt-yrs]]).

## 4. criterion 벤치 ("엔진 vs 래퍼")

```rust
use criterion::{criterion_group, criterion_main, Criterion, BatchSize};

fn bench_merge(c: &mut Criterion) {
    c.bench_function("merge_1k_updates", |b| {
        b.iter_batched(|| prepared_updates(1000),
                       |ups| apply_all(ups),        // 측정 대상: 배치 머지 핫패스
                       BatchSize::SmallInput);
    });
}
criterion_group!(benches, bench_merge);
criterion_main!(benches);
```
- 측정: **머지 throughput / `encode_diff_v1` 지연 / 스냅샷 인코딩**. `cargo bench`.
- "래퍼 대비 N배"는 **naive 베이스라인**(순차·재인코딩)과 **최적화본**(배치·제로카피)을 같은 벤치로 비교해 수치 제시. 추측 금지(`deep-thinking.md`).
- 회귀 방지: criterion baseline 저장 → CI에서 임계 회귀 경고.

## Anti-Patterns

1. **예제 기반 테스트만**(`insert "ab" → "ab"`) — 수렴은 순서·동시성에서 깨짐. property 필수.
2. **고정 시드/적은 케이스** — `PROPTEST_CASES` 충분히(수천). 셔플 다양성 확보.
3. **타이밍/sleep로 "동시성" 흉내** — 결정적 op 순열로 모델링(`testing.md`: sleep 금지).
4. **벤치를 디버그 빌드로** — `--release` 아니면 무의미. criterion은 release.
5. **수렴 비교를 텍스트 only로** — 포맷/속성까지 포함된 상태(update bytes)로 비교해야 누락 안 잡힘.
6. **상호운용 생략** — Rust 내부만 통과해도 클라 Yjs와 깨지면 전제 붕괴(M1 리스크 1순위).

## Verification Criteria

1. **수렴 통과** — commutativity/associativity/idempotence property가 수천 케이스(`PROPTEST_CASES≥1000`) 통과.
2. **축소 동작** — 일부러 버그 주입 시 proptest가 최소 반례를 출력(테스트가 실제로 검증함).
3. **상호운용** — 고정 코퍼스 Yjs↔yrs 양방향 round-trip 동일.
4. **벤치 수치** — `cargo bench`가 머지/diff/스냅샷 처리량을 내고, naive 대비 개선 배수가 문서화됨.
5. **CI 게이트** — proptest + 상호운용 테스트가 M1 머지 전 CI에서 green.

## 참조 스킬
- `[[crdt-yrs]]` — 엔진 API/패턴(이 테스트의 대상)
- `[[negative-path-coverage]]` — edge/error 케이스 보강
- `[[grpc]]` — 통합 테스트에서 bidi 스트림 계약 검증

## Sources / Verified (2026-06-25)
- [proptest — docs](https://altsysrq.github.io/rustdoc/proptest/latest/proptest/) — property testing, 자동 shrinking
- [Property-based testing in Rust with Proptest — LogRocket](https://blog.logrocket.com/property-based-testing-in-rust-with-proptest/) — commutativity/associativity/idempotence
- [Conflict-free replicated data type — Wikipedia](https://en.wikipedia.org/wiki/Conflict-free_replicated_data_type) — 머지 대수 성질
- [criterion.rs](https://github.com/bheisler/criterion.rs) — 통계적 벤치, baseline 회귀
