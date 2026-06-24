# istio — Ambient 메시

ztunnel(L4)이 전 서비스에 자동 mTLS. waypoint(L7)는 **CRDT Engine에만**.

```
ambient/namespace.yaml                      네임스페이스 dataplane=ambient (ztunnel L4 전부)
waypoint/crdt-engine-waypoint.yaml          엔진 전용 L7 waypoint (Gateway API)
waypoint/destinationrule-consistenthash.yaml  docId consistent hash (x-doc-id 헤더)
```

## 왜 엔진만 waypoint?
- 엔진은 **stateful** — 같은 문서가 같은 인스턴스로 가야 인메모리 yrs 상태가 일관됨 → L7 consistent hash 필요.
- 나머지(게이트웨이·doc·ai)는 L4 mTLS면 충분 → waypoint 불필요(리소스 절약).

## 미해결 (SDD §15)
- consistent hash 키 전달 상세: gRPC 메타데이터(`x-doc-id`) ↔ waypoint 설정 정합 (M2 확정).
