# ADR-0005 — CRDT 라이브러리 yrs 채택

- 상태: **Accepted**
- 날짜: 2026-06-24 (SDD v2 확정 시 결정, 2026-08-03 정식 ADR 승격)
- 관련: ADR-0001 · ADR-0004 · SDD §2·§15.5

## 맥락

실시간 협업 편집의 핵심은 CRDT(Conflict-free Replicated Data Type)다.
클라이언트는 Yjs(JavaScript)를 사용하고, 서버는 Rust로 결정됐다(ADR-0004).
서버측 CRDT 구현체를 선택해야 한다.

핵심 요구:
- Yjs 클라이언트와 **binary wire format 호환** (lib0 v1 encoding)
- Rust에서 native 성능
- 문서 상태의 encode/decode (스냅샷 영속화에 필수)

## 결정

**yrs** (Yjs Rust port, y-crdt/y-crdt 프로젝트)를 채택한다.

- yrs 0.27+: Yjs와 동일한 lib0 v1 wire format
- `encode_state_as_update` / `decode_v1` / `encode_state_vector` API로 스냅샷·diff 연산
- Rust native — zero-copy 머지, 벤치마크로 회귀 감시 가능

## 대안 비교

| 대안 | 장점 | 단점 (기각 사유) |
|---|---|---|
| **A. yrs (채택)** | Yjs wire 호환, Rust native, 활발한 유지보수 | 문서가 빈약, 내부 구조 학습 곡선 |
| **B. Automerge (Rust)** | 범용 CRDT, 좋은 문서 | Yjs와 **wire 비호환** — 클라도 Automerge로 바꿔야 함, 생태계 작음 |
| **C. 자체 CRDT 구현** | 완전한 제어 | 정확성 증명 비용 막대, Yjs 호환 보장 불가, 시간 소모 |
| **D. Yjs WASM (서버측)** | 100% 호환 보장 | WASM 오버헤드, Rust 최적화 불가, 메모리 관리 복잡 |

## 결과

- 클라이언트 Yjs ↔ 서버 yrs가 같은 binary encoding을 공유 → 프로토콜 변환 불필요
- M1에서 proptest로 **어떤 머지 순서에도 수렴** property를 검증 (DoD #8 ✅)
- 리스크: Yjs↔yrs 상호운용이 깨지면 전제 무너짐 → M1에 최우선 검증 배치 (완료)
- 학습 곡선 완화: `INTERNALS.md`에 yrs 내부 구조 문서화 (M6)
- 버전 핀: yrs 0.27.x — minor bump 시 proptest 재실행 필수
