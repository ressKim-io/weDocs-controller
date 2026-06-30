---
date: 2026-06-30
slug: m2-persistence-session
status: in-progress
related:
  - plans/2026-06-30-plan-audit-improvements.md
  - prd/4-data-and-permission-model.md
  - sdd/2-services-and-contracts.md
  - sdd/3-data-sync-ai-auth.md
  - adr/0011-engine-sync-fanout-bridge.md
  - adr/0012-crdt-boundary-content-vs-tree.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
  - adr/0015-outbox-app-level.md
---

# M2 — 영속화·세션·권한 (doc-service 신설)

> M2 마일스톤(SDD §13: "영속화·세션 — 재접속 복원, 권한 — Java")의 **SSOT plan**.
> 이 파일은 controller(=계획 SSOT)에 영구 기록. harness plan: `~/.claude/plans/m2-eventual-wombat.md`(휘발성).
> 서비스 코드(doc-service Java / 엔진 Rust / frontend)는 **각 서비스 레포에서 branch+PR+건별 승인**. controller(이 plan·ADR·proto·infra)만 main 직접.

## Context

**왜**: M1(실시간 수렴)은 완료됐으나 **프로세스 재시작 = 데이터 유실**(ADR-0011 트레이드오프 — Doc 미evict, in-memory only)이고 **권한이 없다**(누구나 어떤 room이든 접속). M2는 ① CRDT 상태 영속화 + 재접속/장애 복원, ② 워크스페이스·페이지 트리 데이터 모델, ③ JWT 인증 + 페이지별 권한을 추가해 "실제 사내 위키"의 최소 기능선을 만든다.

**진입 게이트(T3 readiness, 이 세션 controller 작업)**: M2 첫 줄을 쓰기 전 4개 결정·proto 계약·스키마를 확정한다. 게이트 산출물 = ADR 0012~0015 + proto-v0.2.0 + PRD/SDD 갱신. 진행 추적 = [plan-audit T3](2026-06-30-plan-audit-improvements.md).

### Lock된 결정 (2026-06-30, 사용자 확정)

| 결정 | 채택 | 근거 ADR |
|---|---|---|
| 스냅샷 영속화 트리거 | **엔진 push** (`build_client(true)`, 엔진이 N updates/T초마다 `SaveSnapshot`) | [ADR-0013](../adr/0013-snapshot-persistence-lifecycle.md) |
| 데이터 모델 | **page-tree + workspace** (PRD §4, SDD §5 평면 `documents` 대체) | [ADR-0012](../adr/0012-crdt-boundary-content-vs-tree.md) |
| 인증/인가 | JWT 발급=doc-service, 검증=gateway, `CheckPermission(user_id, page_id)` connect 시 | [ADR-0014](../adr/0014-auth-authz-boundary.md) |
| outbox | 앱레벨 트랜잭셔널 outbox (테이블/트랜잭션=M2, Kafka relay=M4) | [ADR-0015](../adr/0015-outbox-app-level.md) |

### 이미 잠긴 전제 (변경 금지)
- 엔진 = sync 권위 + per-doc `tokio::broadcast` fan-out, 게이트웨이 = 번역기, 인코딩 lib0 v1 ([ADR-0011](../adr/0011-engine-sync-fanout-bridge.md)).
- proto 배포 = buf 원격 git input, 태그 bump ([ADR-0010](../adr/0010-proto-distribution-buf-git-input.md)). 현 태그 `proto-v0.1.0` → M2 변경 시 `proto-v0.2.0`.
- doc-service = `weDocs-backend` 레포 내 Spring Boot 모듈(Security/JPA), 저장소 Postgres.

## proto 계약 — `proto-v0.2.0` (이 게이트에서 확정)

`proto/doc/doc.proto` (additive → `buf breaking` FILE 통과):
- **추가** `DocService.LoadSnapshot(LoadSnapshotRequest{doc_id}) → LoadSnapshotResponse{snapshot, version}` — 엔진 복원 pull-on-ensure. 신규 페이지 = `version=0`·빈 blob(ADR-0013). (기존 `CrdtEngine.GetSnapshot`은 엔진 in-memory 읽기라 재시작 후 복원에 재사용 불가.)
- **확장** `DocMeta`에 `workspace_id`, `parent_id` (page-tree).
- `CheckPermissionRequest` 토큰 필드 **미추가** — gateway가 JWT 검증 후 `user_id` 전달(proto 최소화, ADR-0014).
- 페이지 트리 CRUD·인증은 **REST**(클라이언트向), 내부 gRPC는 권한체크·스냅샷 저장/로드·메타 한정.

## 데이터 모델 — page-tree (SDD §5 갱신, ADR-0012 경계)

```
users(id, email, password_hash, display_name, created_at)
workspaces(id, name, owner_id, created_at)
workspace_members(workspace_id, user_id, role)          role: owner | member
pages(id, workspace_id, parent_id, title, position, archived, created_at, updated_at)   -- self-tree (parent_id NULL=루트)
page_permissions(page_id, user_id, level)               level: editor | viewer   (override, 상속)
page_snapshots(page_id PK, snapshot bytea, version bigint, created_at)   -- 최신 1행 UPSERT(ADR-0013, 엔진 권위 버전)
outbox(id, aggregate_id, event_type, payload, traceparent, created_at, published_at)   -- aggregate_id=page_id, 멱등키=id(ADR-0015)
```
- **CRDT 경계**(ADR-0012): 페이지 *내용* 동시성 = CRDT(엔진), 페이지 *트리* 동시성 = 관계형(doc-service 트랜잭션, 이동 시 사이클 검사). PRD §3.
- 유효 권한 = 명시 PagePermission > 조상 상속 > workspace baseline > 거부 (PRD §4.2). member 기본 = editor (D-3).

## M2 구현 Phase 분해 (서비스 레포, 게이트 통과 후)

> 각 Phase = 해당 서비스 레포 branch+PR+승인. Phase 경계마다 이 plan 재개지점 갱신.

- **Phase 1 — doc-service 스켈레톤 + 스키마** (backend, `weDocs-backend` 레포) — 3 PR로 분할(PR ≤400줄):
  - **1a 데이터 레이어** (착수): `settings.gradle.kts`에 `doc-service` 모듈 추가 + `doc-service/build.gradle.kts`(Spring Boot 4.1.0 BOM·Java 25·JPA·PostgreSQL·Flyway·Testcontainers) + `DocServiceApplication` + `application.yml` + **Flyway `V1__init_page_tree.sql`(7테이블)** + JPA 엔티티 7종·Repository + **Testcontainers 영속 테스트**(스키마 마이그레이션·page-tree 저장·snapshot UPSERT). TDD(테스트 먼저). 코드=`io.wedocs.doc.*`.
  - **1b gRPC 서버**: `DocService` 4 RPC(`CheckPermission` 권한 상속 해석·`SaveSnapshot` UPSERT·`LoadSnapshot` 신규=빈 blob·`GetDocMeta`). proto 소비=`buf.gen.yaml` 로컬 경로(태그 push 불요). Testcontainers + grpc 통합 테스트.
  - **1c REST + 인증 발급**: 페이지 CRUD(트리 이동 사이클 검사)·workspace·멤버 초대 REST + JWT 발급(로그인). (검증 발급=1c, gateway 검증=Phase 2)
  - 로컬 Postgres compose(`infra/local/`)는 1a에서 추가(또는 Testcontainers만으로 충분 시 후속).
- **Phase 2 — 인증/인가** (backend doc-service + gateway): doc-service JWT 발급/검증, gateway WS 핸드셰이크 인증(`Sec-WebSocket-Protocol` 서브프로토콜), connect 시 `CheckPermission`, **viewer write-block = gateway 1차(client→server update drop) + 엔진 방어**(D-5), 인가 실패 close code.
- **Phase 3 — 엔진 영속화 (save)** (crdt-engine): `build.rs` `build_client(true)` flip, 엔진→`doc-service.SaveSnapshot` 트리거(N updates/T초, ADR-0013), 트랜잭션 경계·중복저장 방지. rust-expert 리뷰.
- **Phase 4 — 복원 (restore)** (crdt-engine + doc-service): doc ensure 시 엔진→`LoadSnapshot`→`decode_v1`→apply→SyncStep2. 장애 재라우팅 복원. 보장 경계 = 최종 스냅샷(in-flight 유실 허용, Redis 버퍼=M5).
- **Phase 5 — outbox 테이블** (backend doc-service): 페이지 변경 트랜잭션에 outbox insert 동봉(ADR-0015), traceparent 주입. **relay·Kafka 소비는 M4**(테이블·트랜잭션만 M2).
- **Phase 6 — E2E 복원·권한 검증** (frontend/통합): 재접속 후 복원 green(M2 DoD), viewer read-only·editor 양방향 E2E, 멤버십/상속 권한 케이스.

## Blast Radius

| 항목 | 내용 |
|---|---|
| 직접 변경(이 게이트) | `proto/doc/doc.proto`, `docs/adr/0012~0015`, `docs/prd/4`, `docs/sdd/{2,3,5}`, `docs/plans/*`, `CLAUDE.md` |
| 직접 변경(M2 구현) | backend `doc-service/`(신설)·`ws-gateway/`(인증), crdt-engine `build.rs`+save/restore, `infra/local/` Postgres compose, frontend 인증·복원 E2E |
| 간접 영향 | proto 소비자(backend/crdt-engine) `ref` bump 필요 → 재생성. gateway WS 핸드셰이크 변경 = frontend provider 토큰 전달 변경 |
| 롤백 | controller = git revert. 서비스 레포 = PR revert. proto = `proto-v0.1.0`로 ref 되돌림(additive라 하위호환) |
| 검증 | `buf lint/breaking` green · doc-service Testcontainers green · **재접속 복원 E2E green**(M2 DoD) · 권한 E2E green |
| 다운타임 | 없음(신규 서비스·로컬 dev). 클러스터 배포는 M5 |

## 검증 (M2 DoD)

- **재접속 복원**(PRD §7 DoD M2): 편집 → 스냅샷 저장 → 엔진 재시작 → 재접속 → 마지막 스냅샷까지 복원 확인.
- **권한**: viewer는 write drop(gateway+엔진), editor는 양방향, 비멤버는 connect 거부(403/close).
- 게이트: `buf lint proto && buf breaking proto --against '.git#branch=main,subdir=proto'` green · ADR 4종 `documentation.md` 검증규칙 충족.

## 범위 밖

- consistent-hash 멀티인스턴스 라우팅·Redis 버퍼 복원 → **M3**.
- outbox Kafka relay·인덱싱 소비·AI → **M4**.
- 클러스터 Postgres/Redis/Kafka 매니페스트·Istio mTLS STRICT 실배포 → **M5**(M2 dev/test = 로컬 compose + Testcontainers).
- 트리 CRDT(동시 이동 자동 머지)·공개링크·버전 히스토리 UI·연결 중 권한 강등 → 2차 확장(PRD §5).
- 인증 서비스 분리(M2 = doc-service 내장 발급/검증).

## 재개 지점 (Resume)

> **마지막 완료**: **Phase 1a 데이터 레이어 — [backend PR #3](https://github.com/ressKim-io/weDocs-backend/pull/3) OPEN**(브랜치 `feature/m2-doc-service-skeleton`, 커밋 `1089ec8`, push 완료). doc-service 모듈 + Flyway 7테이블 + 핵심 엔티티 4종 + Testcontainers 영속 테스트 3건 green. 함정 2건 = [dev-log](../dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md).
> **다음(새 세션 진입점)**: ① **PR #3 머지 확인**(미머지면 머지) → ② **Phase 1b gRPC 서버** — `weDocs-backend` 같은 패턴, 신규 브랜치 `feature/m2-doc-service-grpc`. `DocService` 4 RPC 구현: `CheckPermission`(권한 상속 해석, PRD §4.2)·`SaveSnapshot`(UPSERT)·`LoadSnapshot`(신규=빈 blob, version 0)·`GetDocMeta`. **WorkspaceMember/PagePermission 엔티티 추가**(스키마엔 이미 존재, 1a는 미매핑). proto 소비 = `make proto-gen`(buf.gen 로컬 경로 `../weDocs-controller/proto`, 태그 push 불요). Testcontainers + grpc 통합 테스트(TDD). → 이후 1c REST/JWT.
> **주의**: 서비스 레포(backend/crdt-engine/frontend)는 전부 건별 승인(브랜치·PR·push). controller만 main 직접. 엔진 `build_client(false)→true` flip은 Phase 3. **proto 태그 push·다운스트림 `ref` bump = 승인 게이트**(CI 정합 시). 게이트 트랙(T3 done·T4) = [plan-audit](2026-06-30-plan-audit-improvements.md). 빌드 함정 = 위 dev-log(Spring Boot 4.x=스타터 필수·TC 2.x=좌표).
