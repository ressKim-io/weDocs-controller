# 버전 핀 매트릭스

> 서비스별 핵심 의존성 버전과 업그레이드 정책. 버전 변경 시 이 문서를 함께 갱신한다.

**최종 갱신**: 2026-08-03

---

## crdt-engine (Rust)

| 의존성 | 핀 버전 | 업그레이드 정책 | 비고 |
|---|---|---|---|
| Rust toolchain | stable (edition 2024) | `rust-toolchain.toml` 관리, CI 고정 | |
| yrs | 0.27.x | minor bump 시 proptest 재실행 필수 | wire format 호환 검증 |
| tonic | 0.14.x | prost와 동시 bump | gRPC 코어 |
| prost | 0.14.x | tonic과 동시 bump | proto codegen |
| tokio | 1.x | patch 자유, minor 검토 | async runtime |
| parking_lot | 0.12.x | patch 자유 | 동기 Mutex |
| metrics | 0.24.x | M5에서 도입 시 고정 | 관측 |

## weDocs-backend (Java)

| 의존성 | 핀 버전 | 업그레이드 정책 | 비고 |
|---|---|---|---|
| Java | 25 | LTS 주기 검토 (25 = non-LTS, 다음 LTS = 25?) | VT 필수 |
| Spring Boot | 4.1.x | minor 단위, changelog 확인 | BOM 관리 |
| grpc-java | 1.82.x | proto 재생성 필요 | gRPC 코어 |
| protobuf-java | 4.34.x | grpc-java와 호환 확인 | proto runtime |
| Flyway | 11.x | 마이그레이션 호환 확인 | 스키마 |
| Testcontainers | 2.x | minor 자유 | 테스트 인프라 |
| Jackson (tools.jackson) | 3.x | Boot BOM 따름 (Boot 4.x = Jackson 3) | JSON |
| nimbus-jose-jwt | 10.x | JWT 알고리즘 호환 확인 | 인증 |

## weDocs-frontend (TypeScript)

| 의존성 | 핀 버전 | 업그레이드 정책 | 비고 |
|---|---|---|---|
| Node.js | 24.x (CI) / 26.x (로컬) | CI 핀, 로컬 유연 | engines 교집합 |
| React | 19.x | major 검토 | UI 프레임워크 |
| Vite | 8.x | minor 자유 | 빌드 도구 |
| Tiptap | 3.27.x | 에디터 동작 회귀 확인 | 블록 에디터 |
| yjs | 13.x | yrs wire 호환 확인 | CRDT 클라이언트 |
| y-websocket | 2.x | 프로토콜 변경 확인 | WS 동기화 |

## weDocs-ai-service (Python, M4 예정)

| 의존성 | 핀 버전 | 업그레이드 정책 | 비고 |
|---|---|---|---|
| Python | 3.12+ | uv lock 관리 | |
| FastAPI | 0.115+ | minor 자유 | API 프레임워크 |
| LlamaIndex | 0.12+ | RAG 품질 회귀 테스트 | RAG 코어 |
| pgvector | 0.3+ | 임베딩 차원 호환 확인 | vector store |

## 인프라 도구

| 도구 | 핀 버전 | 비고 |
|---|---|---|
| buf | 1.72.x | proto lint/breaking/generate |
| Gradle | 9.1.x | wrapper로 관리 |
| Docker / OrbStack | 29.x | Testcontainers 호환 |
| Istio | 1.24+ (Ambient GA) | M5에서 고정 |
| ArgoCD | 2.14+ | M5에서 고정 |
| Jaeger | 2.19+ | OTLP 기본 활성 (v2) |

---

## 업그레이드 규칙

1. **의존성 변경은 단독 커밋** — 기능 변경과 섞지 않는다
2. **security advisory 발생 시 24h 내 patch** — `cargo audit` / `npm audit` / Dependabot
3. **major bump = ADR** — blast radius 큰 변경은 대안 비교 필수
4. **proto 의존성(grpc-java, tonic, prost)은 양 레포 동시 bump** — 버전 skew = 컴파일 에러
5. **CI에서 정확 버전 핀** — range(`^`, `~`) 허용은 로컬 개발만, lock 파일이 진실
