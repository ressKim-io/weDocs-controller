# ADR-0004 — Rust 독립 CRDT 엔진 + bidi streaming

- 상태: **Accepted**
- 날짜: 2026-06-24 (SDD v2 확정 시 결정, 2026-08-03 정식 ADR 승격)
- 관련: ADR-0001 · ADR-0005 · ADR-0011 · SDD §2·§15.4

## 맥락

CRDT 머지는 CPU 바운드 + 정확성이 생명이다. 클라이언트(Yjs, JavaScript)와 서버 사이에
"중앙 권위 없는 수렴"을 보장하려면 서버측도 동일한 CRDT 구현체를 써야 한다.
Yjs의 Rust 포트인 **yrs**(ADR-0005)를 선택하면 서버 언어는 자연스럽게 Rust가 된다.

문제: Rust 엔진을 **어떤 형태로** 시스템에 배치할 것인가?

## 결정

Rust를 **독립 gRPC 서비스**(bidi streaming)로 배치한다.

- 게이트웨이(Java) ↔ 엔진(Rust): `CrdtEngine.Sync` bidirectional streaming RPC
- 엔진은 문서별 상태를 메모리에 유지하고 fan-out(ADR-0011)
- consistent hashing(Istio waypoint L7, ADR-0007)으로 같은 문서 = 같은 인스턴스 (stateful 확장)
- 엔진은 단순 래퍼가 아니라 **최적화·벤치마크 동반 의무** (가드레일 5)

## 대안 비교

| 대안 | 장점 | 단점 (기각 사유) |
|---|---|---|
| **A. Rust 독립 서비스 (채택)** | 독립 스케일링, 언어 최적 활용, VT pinning 0 | 네트워크 hop 추가, 배포 복잡도 |
| **B. Rust FFI/JNI 사이드카** | 네트워크 hop 제거 | VT pinning(JNI = native call), 디버깅 지옥, crash가 JVM 전체를 죽임 |
| **C. Java 내 yrs 래퍼 (JNI)** | 단일 프로세스 | B와 동일한 문제 + CRDT 최적화를 Java 쪽에서 할 수 없음 |
| **D. WebAssembly 임베딩** | 언어 중립 | WASM GC 없이 Yrs의 Vec/HashMap 비용 큼, bidi stream 매핑 복잡 |

## 결과

- 엔진은 `tonic` gRPC 서버로 기동 (proto = `crdt/crdt.proto`)
- 게이트웨이는 gRPC 클라이언트만 가짐 — native call 금지 (VT 가드레일)
- 엔진 PR에는 criterion 벤치마크 동반 필수 (단순 래퍼 PR 반려)
- stateful이므로 멀티인스턴스 시 consistent hash 라우팅 필요 → M3
- 장애 복원 = 스냅샷 영속화(ADR-0013) + doc-service LoadSnapshot
