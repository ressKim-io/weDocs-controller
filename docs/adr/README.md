# ADR — 아키텍처 결정 기록

SDD §15 결정 로그를 개별 ADR로 분리한다. 형식: **1 결정 = 1 파일**.

| # | 결정 | 상태 |
|---|---|---|
| [0001](0001-language-strategy-b.md) | 언어 전략 B (I/O=Java VT · AI=Python · CPU=Rust, Go 제외) | Accepted |
| 0002 | 게이트웨이 Java Virtual Thread (JEP 491 pinning 해소) | SDD §15.2 — 분리 예정 |
| 0003 | AI = Python / LlamaIndex (생태계 깊이) | SDD §15.3 — 분리 예정 |
| 0004 | Rust 독립 CRDT 엔진 + bidi streaming | SDD §15.4 — 분리 예정 |
| 0005 | CRDT 라이브러리 = yrs (Yjs wire 호환) | SDD §15.5 — 분리 예정 |
| 0006 | 5-repo 폴리레포 + buf (proto 배포는 ADR-0010이 확정) | SDD §15.6 — 분리 예정 |
| 0007 | Istio Ambient (ztunnel L4 / waypoint=엔진) | SDD §15.7 — 분리 예정 |
| 0008 | vector store = pgvector | SDD §15.8 — 분리 예정 |
| 0009 | 배포 = 홈랩 KinD + 로컬 GPU | SDD §15.9 — 분리 예정 |
| [0010](0010-proto-distribution-buf-git-input.md) | proto 배포 = buf 원격 git input (submodule 불가 → `subdir` input) | **Accepted** |
| [0011](0011-engine-sync-fanout-bridge.md) | 엔진 sync/fan-out 브리지 (게이트웨이=번역기·엔진=권위·broadcast fan-out·v1 고정) | **Accepted** |

> **번호 공백(0002~0009)**: 0010(proto 배포 블로커)을 먼저 확정해 점프. 0002~0009 정식 분리는 **M6 일괄**(또는 해당 마일스톤 착수 시) — 그 전까지 **권위 = SDD §15 본문**. 0011 = M1 마감 산출물.

## 미해결 (소유 마일스톤 — 권위=SDD §15, 여기는 링크만)
> SDD §15와 중복 관리 금지. 상세·갱신은 [SDD §15](../sdd/5-project-milestones-guardrails.md).
- CRDT Engine 장애 복원 절차 → **M2**
- outbox 구현 (Debezium vs 앱레벨) → **M2**
- 인증 서비스 분리 시점 → **M2**
- consistent hash 키 전달 상세 (gRPC 메타데이터 ↔ waypoint) → **M3**
- AI Service SLO 정량 정의 (큐 대기 + 추론) → **M4**
