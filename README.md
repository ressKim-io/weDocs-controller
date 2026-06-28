# Synapse — Controller (control plane)

> 실시간 협업 텍스트 에디터(CRDT) + 문서 맥락 AI co-pilot. Polyglot MSA.
> 이 레포(`controller`)는 5-repo 폴리레포의 **컨트롤 플레인**이다 — proto SSOT · infra(GitOps) · CI 게이트 · 문서.

**코드네임 `Synapse`** (변경 가능 — 작업 디렉터리는 `weDocs`).

## 무엇을 / 왜
- **무엇**: 여러 사용자가 같은 문서를 동시 편집(충돌 없는 CRDT 수렴)하고, AI가 문서 근거로 Q&A·요약을 SSE 스트리밍.
- **왜(포트폴리오)**: 분산 동시성(CRDT) 직접 구현 · 언어를 제약에 맞춰 분리하는 판단력 · 단일 GPU 제약 하 AI 백엔드 설계 · 폴리글랏 단일 OTel trace.
- 진입점: [`docs/PRD.md`](docs/PRD.md) (무엇·왜) → [`docs/SDD.md`](docs/SDD.md) (어떻게) → [`docs/adr/`](docs/adr/) (결정 로그)

## 언어 전략 (B)
| 지배적 제약 | 언어 | 서비스 |
|---|---|---|
| I/O 바운드 | **Java 25 / Virtual Thread** | WS Gateway, Doc/Session |
| AI 생태계 | **Python / FastAPI + LlamaIndex** | AI Service, Indexing Consumer |
| CPU 바운드 + 정확성 critical | **Rust / yrs** | CRDT Engine |

> "I/O는 Java VT, AI는 Python, CPU+정확성(CRDT)은 Rust — 각 서비스의 지배적 제약에 언어를 배치." (Go 제외: VT가 goroutine 동시성 우위를 상쇄)

## 5-repo 폴리레포
| 레포 | 스택 | 역할 |
|---|---|---|
| `frontend` | React + Tiptap + Yjs | 에디터, 커스텀 y-websocket provider |
| `backend` | Java (gradle multi-module) | ws-gateway, doc-service |
| `ai-service` | Python | FastAPI RAG + Kafka indexer |
| `crdt-engine` | Rust | yrs 엔진 + tonic gRPC (bidi streaming) |
| **`controller`** ← 이 레포 | proto · infra · ci · docs | 컨트롤 플레인 / proto SSOT |

`proto/`가 **단일 진실 공급원(SSOT)**. ①②③④가 이 디렉터리를 git submodule로 mount하고 각자 `buf generate`로 stub 생성.

## 레포 구조
```
controller/
├── proto/        ★ proto SSOT — common / crdt / doc / ai (+ buf.yaml)
├── buf.gen.yaml  3언어 코드 생성(검증용) → gen/ (gitignored)
├── infra/        k8s(kustomize) · istio(ambient+waypoint) · argocd(app-of-apps) · terraform
├── ci/           buf breaking 게이트 + 다운스트림 트리거 (워크플로우: .github/workflows/)
├── .claude/      컨트롤러 에이전트/스킬
├── docs/         PRD.md · SDD.md · adr/
└── CLAUDE.md     에이전트 가드레일 (자동 로드)
```

## proto + buf 워크플로우
1. 모든 proto 변경은 **여기 `proto/`에서 시작**.
2. `buf lint proto` + `buf breaking proto --against <main>` 통과.
3. 다운스트림 submodule 업데이트 → 3언어 재생성(`buf generate`).
- CI 게이트: [`.github/workflows/proto-ci.yml`](.github/workflows/proto-ci.yml).

## 인프라
홈랩 KinD + 로컬 GPU(Ollama, RTX 4060Ti). Istio **Ambient** — ztunnel L4 mTLS 전부 / waypoint L7 = **CRDT Engine만**(docId consistent hash). ArgoCD app-of-apps. → [`infra/`](infra/)

## 마일스톤 (리스크 우선)
- **M0** ✅ 기획·proto·스캐폴딩
- **M1** 🔶 CRDT 코어: 두 브라우저 동시 편집 수렴 (Yjs↔yrs + bidi) ← *현재* — **수렴 본체 증명 완료**(Phase 1~3 머지), OTel·마감 남음
- M2 영속화·세션 · M3 Presence · M4 AI co-pilot · M5 인프라·관측 · M6 마감

## 가드레일
[`CLAUDE.md`](CLAUDE.md): proto는 여기서 시작 · AI는 CRDT 의존 금지 · 게이트웨이 JNI 금지 · 서비스 간 gRPC+OTel · CRDT는 "엔진"(최적화+벤치) · M1 머지 전 proptest 통과.
