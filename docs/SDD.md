# SDD — Synapse 시스템 설계 문서 (v2)

문서 버전: **v2** (언어 전략 B 확정 반영)
선행 문서: `PRD.md`
v1 → v2 변경 요약:
- 게이트웨이를 **Java Virtual Thread**로 확정 (Go 제거 — JEP 491로 동시성 격차 해소)
- AI Service를 **Python(FastAPI + LlamaIndex)** 으로 전환 (Spring AI → Python; "모델 통합"이 아니라 "AI 생태계 깊이"가 목적)
- Rust를 단순 래퍼가 아니라 **독립 CRDT 엔진**으로 (yrs 위 최적화, bidi streaming, criterion 벤치마크)
- 레포를 **5개 폴리레포**로 (frontend / backend[Java] / ai-service[Python] / crdt-engine[Rust] / controller)
- proto는 **buf CLI + controller SSOT + git submodule**
- Istio **Ambient** 상세화 (ztunnel L4 / 엔진만 waypoint L7 + consistent hash)

---

## 구성 (분할 문서)
- [설계 원칙 & 아키텍처 개요](sdd/1-architecture.md) — §0–1
- [서비스 · 언어 배정 · proto 계약](sdd/2-services-and-contracts.md) — §2–4
- [데이터 · 실시간 동기화 · AI · 인증](sdd/3-data-sync-ai-auth.md) — §5–8
- [인프라 · 관측 · 테스트](sdd/4-infra-observability-testing.md) — §9–11
- [레포 구조 · 마일스톤 · 가드레일 · 결정로그](sdd/5-project-milestones-guardrails.md) — §12–15

- [결정 로그 (ADR)](adr/) — §15는 ADR로 분리
