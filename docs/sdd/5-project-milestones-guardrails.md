# SDD — 레포 구조 · 마일스톤 · 가드레일 · 결정로그
> [← 인덱스](../SDD.md)

## 12. 레포 구조 (5-repo 폴리레포)

```
① weDocs-frontend/    React + Tiptap + Yjs + y-websocket provider (gRPC 비소비자)

② weDocs-backend/     Java만 (gradle 멀티모듈)
   ├── ws-gateway/   (Spring Boot 4 / Virtual Thread)
   ├── doc-service/  (Spring Boot, Security/JPA — M2+)
   └── buf.gen.yaml  → buf 원격 git input (controller proto, ADR-0010)

③ weDocs-ai-service/ Python (uv/poetry)
   ├── app/          (FastAPI + LlamaIndex)
   ├── indexer/      (Kafka consumer)
   └── buf.gen.yaml  → buf 원격 git input

④ weDocs-crdt-engine/ Rust (cargo)
   ├── src/          (yrs 엔진 + tonic gRPC)
   ├── benches/      (criterion)
   └── build.rs      → buf export + tonic-prost-build (proto vendored, gitignored)

⑤ weDocs-controller/  컨트롤 플레인
   ├── proto/        ★proto SSOT (common/ crdt/ doc/ ai/)
   ├── infra/
   │   ├── k8s/      (kustomize base+overlays)
   │   ├── istio/    (ambient, waypoint=엔진, DestinationRule consistentHash)
   │   ├── argocd/   (app-of-apps)
   │   └── terraform/ (옵션)
   ├── .claude/      (에이전트/스킬)
   ├── ci/           (buf breaking 게이트 + 다운스트림 트리거)
   └── docs/         (PRD.md, SDD.md, adr/)
```
- proto SSOT는 controller. gRPC 소비자(②③④)가 **buf 원격 git input**으로 참조해 stub 생성(submodule 아님 — ADR-0010). ①(frontend)은 gRPC 비소비자(y-websocket).
- infra는 controller에 흡수(별도 레포 X).
- 폴리레포 비용(proto 동기화, CI 5벌)은 controller의 멀티레포 오케스트레이션 + buf 게이트로 관리 → 그 자체가 DevOps showcase.

---

## 13. 마일스톤 (리스크 우선)

| 단계 | 목표 | 검증 기준 | 주 언어 |
|---|---|---|---|
| **M0** | 기획·설계·proto·스캐폴딩 | PRD+SDD+proto(buf)+5repo 골격 | — |
| **M1** | CRDT 코어 | **두 브라우저 동시 편집 수렴** | Rust+Java+JS |
| **M2** | 영속화·세션 | 재접속 복원, 권한 | Java |
| **M3** | Presence | 커서·선택 fan-out(멀티 인스턴스) | Java |
| **M4** | AI co-pilot | RAG 스트리밍, GPU 폴백 | Python |
| **M5** | 인프라·관측 | GitOps 배포, 폴리글랏 단일 trace | (DevOps) |
| **M6** | 마감 | 문서·데모·벤치마크·README | — |

**M1 최우선**: Yjs↔yrs 상호운용 + bidi 스트림이 깨지면 전제가 무너짐. 최소 구성(Rust 엔진 + 얇은 Java 게이트웨이 + 최소 React)으로 "동시 편집 수렴"을 먼저 증명.

---

## 14. Claude Code 작업 가이드

- **진입점**: `controller/docs/PRD.md` → `SDD.md`
- **워크플로우**: PRD → SDD → (서비스별) 구현 → 리뷰
- **작업 단위**: 마일스톤 단위. M1은 crdt-engine + ws-gateway(최소) + frontend(최소)를 하나의 수직 슬라이스로.
- **불변 규칙 (에이전트 가드레일)**:
  - proto 변경은 `controller/proto`에서 시작 → `buf breaking` 통과 → submodule 업데이트 → 3언어 재생성
  - AI Service는 CRDT 의존성을 가질 수 없다(설계 위반)
  - 게이트웨이는 native call(JNI)을 도입하지 않는다(VT pinning 방지)
  - 서비스 간 호출은 gRPC + OTel propagator를 통과한다
  - CRDT Engine은 "엔진"이다 — 단순 래퍼 PR은 반려, 최적화·벤치마크 동반
  - M1 머지 전 proptest 수렴 테스트 통과 필수

---

## 15. 결정 로그 (ADR — `docs/adr/`로 분리 예정)

1. **언어 전략 B** — I/O=Java VT, AI=Python, CPU=Rust. Go 제외(VT가 동시성 우위 상쇄).
2. **게이트웨이 Java Virtual Thread** — JEP 491(JDK24/25)로 synchronized pinning 해소. 풀링 금지, Semaphore 백프레셔.
3. **AI Python/LlamaIndex** — "모델 통합"이 아니라 "AI 생태계 깊이"가 목적. RAG 품질 차별화.
4. **Rust 독립 엔진 + bidi streaming** — 단순 래퍼 아님. consistent hashing으로 stateful 확장. (사이드카·FFI 기각: stateful 충돌 / VT pinning)
5. **CRDT 라이브러리 yrs** — 클라 Yjs와 wire 호환. 직접 구현은 학습용 1모듈로 INTERNALS 문서화.
6. **5-repo 폴리레포 + buf** — proto 배포 = buf 원격 git input(submodule 아님 — ADR-0010). infra는 controller 흡수. proto SSOT=controller.
7. **Istio Ambient** — ztunnel L4 mTLS 전부, waypoint L7은 엔진만(consistent hash).
8. **vector store=pgvector** — 별도 DB 미도입.
9. **배포 메인=홈랩 KinD + 로컬 GPU**. 멀티클라우드 생략.

### 미해결 (M1~M2에서 확정)
- [ ] CRDT Engine 장애 시 복원 절차 상세
- [ ] AI Service SLO 정량 정의(큐 대기 + 추론)
- [ ] outbox 구현(Debezium vs 애플리케이션 레벨)
- [ ] 인증 서비스 분리 시점
- [ ] consistent hash 키 전달 상세(gRPC 메타데이터 ↔ waypoint 설정)
