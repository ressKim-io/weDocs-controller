---
date: 2026-07-04
slug: m2-phase1b-docservice-grpc
status: done
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0012-crdt-boundary-content-vs-tree.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
  - prd/4-data-and-permission-model.md
  - dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md
---

# M2 Phase 1b — gRPC `DocService` 4-RPC 구현 (weDocs-backend/doc-service)

> M2 세션 plan([2026-06-30-m2-persistence-session.md](2026-06-30-m2-persistence-session.md))의 Phase 1b 하위 실행 plan.
> 이 파일은 controller(계획 SSOT)에 영구 기록. harness plan: `~/.claude/plans/fable-validated-quasar.md`(휘발성, 참고용).
> 실제 코드는 **weDocs-backend 레포**(sibling 디렉토리)에서 branch+PR+건별 승인으로 진행.

## Context

M2 Phase 1a(page-tree 스키마+JPA+Testcontainers)는 backend PR #3 머지로 완료됐다. controller SSOT(`CLAUDE.md`, M2 세션 plan)는 다음 단계로 Phase 1b(gRPC `DocService` 4 RPC 구현)를 명시한다. proto 계약(`CheckPermission`/`SaveSnapshot`/`LoadSnapshot`/`GetDocMeta`)과 ADR 4종(0012~0015)은 이미 확정됐지만, doc-service 모듈에는 현재 데이터 레이어만 있고 gRPC 서버 자체가 없다 — `buf.gen.yaml`도 ws-gateway용 출력만 있다. 이번 작업은 이 gap을 TDD로 메운다.

**사전 확인된 결정**: proto `DocMeta.owner_id`는 `pages` 테이블에 페이지별 owner/creator 컬럼이 없어 매핑 공백이 있었다 — 사용자 확인 결과 **워크스페이스의 `owner_id`로 매핑**(PRD §4.3: workspace owner는 전 페이지에 사실상 owner 권한). 코드에 "1c `created_by` 도입 전 임시 매핑" 주석을 남긴다.

## 범위

**포함**: 4 RPC 서버 구현, `WorkspaceMember`/`PagePermission` JPA 엔티티(+enum+컨버터, 이 코드베이스 최초 복합키 패턴), 권한 해석 서비스(PRD §4.2), gRPC 서버 배선(`SmartLifecycle`), 관련 테스트 전체.

**범위 밖**: `system_admin` 우회, ws-gateway의 실제 `CheckPermission` 호출 연동(Phase 2), crdt-engine의 실제 `SaveSnapshot`/`LoadSnapshot` 연동(Phase 3), REST/JWT(1c), 페이지 reparent API(proto에 없음), outbox 연동(Phase 5), 아웃바운드 unary `withDeadlineAfter`(호출자인 Phase 2/3 클라이언트 쪽 관심사).

## 신규/변경 파일

프로덕션 코드(`doc-service/src/main/java/io/wedocs/doc/`):
`domain/{WorkspaceRole,WorkspaceRoleConverter,PagePermissionLevel,PagePermissionLevelConverter,WorkspaceMemberId,WorkspaceMember,PagePermissionId,PagePermission}.java`,
`repository/{WorkspaceMemberRepository,PagePermissionRepository}.java`,
`service/{EffectivePermission,PermissionService,PageNotFoundException,SnapshotService,DocMetaService}.java`,
`grpc/{DocServiceImpl,GrpcServerLifecycle}.java`.

테스트(`doc-service/src/test/java/io/wedocs/doc/`):
`DocFixtures.java`, `PermissionPersistenceTest.java`, `service/PermissionServiceTest.java`, `grpc/{DocServiceGrpcIntegrationTest,GrpcServerLifecycleTest}.java`, `src/test/resources/application.yml`(grpc-enabled: false).

변경: `weDocs-backend/buf.gen.yaml`(doc-service output 추가), `doc-service/build.gradle.kts`(grpc 1.82.1/protobuf 4.34.1, ws-gateway와 동일 버전), `doc-service/src/main/resources/application.yml`(grpc-port 50052 등 3개 키).

**핵심 주의**: `WorkspaceMember`/`PagePermission`은 DDL에 `created_at`/`updated_at` 컬럼이 없어 `BaseTimeEntity`/`BaseCreatedEntity`를 상속하면 `ddl-auto=validate`가 즉시 실패한다 — 순수 엔티티로 작성.

## 설계 결정 요약

| 항목 | 결정 |
|---|---|
| `DocMeta.owner_id` | 워크스페이스 `owner_id` 매핑(사용자 확인 완료) |
| CheckPermission "없음" | page/user 없음·비멤버·권한 없음 = 전부 에러 아님, `allowed=false, ROLE_UNSPECIFIED`(존재 비노출) |
| SaveSnapshot/GetDocMeta "없음" | page 없음 = 진짜 `NOT_FOUND` |
| LoadSnapshot "없음" | 스냅샷 없음(신규 페이지) = 에러 아님, `version=0`+빈 bytes(ADR-0013) |
| 조상 탐색 상한 | `MAX_ANCESTOR_DEPTH=64`(방어적, 운영 튜닝 대상 아님) |
| gRPC 서버 lifecycle | `SmartLifecycle` + VT executor(`Executors.newVirtualThreadPerTaskExecutor()`) + 명시적 `maxInboundMessageSize` |
| 신규 config | `wedocs.doc-service.grpc-port`(50052)·`grpc-enabled`(true, 테스트는 false)·`grpc-max-inbound-message-size`(4194304) |

전체 알고리즘 스케치·크래프트 게이트([B] 체크리스트) 매핑·회귀 위험 상세는 harness plan(`~/.claude/plans/fable-validated-quasar.md`) 참조 — 두 문서 내용은 동일하며 이 파일이 영구 SSOT.

## 실행 체크리스트

- [x] backend 브랜치 생성: `feature/m2-doc-service-grpc` (main `0992f70`에서 분기)
- [x] `buf.gen.yaml`에 doc-service output 추가 + `doc-service/build.gradle.kts`에 grpc 의존성 추가 (`3f4feba`) — `io.grpc.inprocess`가 grpc-core 전이의존이 아니라 별도 `grpc-inprocess` 아티팩트임을 실측으로 발견해 정정
- [x] Stage 1 — WorkspaceMember/PagePermission 복합키 엔티티(TDD, `49d2091`) — PermissionPersistenceTest 4건
- [x] Stage 2 — PermissionService(TDD, `27df61b`) — PermissionServiceTest(순환참조 방어 캡 포함)
- [x] Stage 3 — SnapshotService/DocMetaService(`ebe72d2`)
- [x] Stage 4 — DocServiceImpl + GrpcServerLifecycle(TDD, `86829ae`) — DocServiceGrpcIntegrationTest 11건
- [x] Stage 5 — GrpcServerLifecycleTest 실 TCP 소켓 스모크(`d84e9f5`) — VT executor 실사용(virtual-* 스레드) 로그로 확인
- [x] 회귀 확인: 기존 `PageTreePersistenceTest` 재실행 → gRPC 포트 바인딩 로그 없음 확인(grpc-enabled=false 정상 적용, 로그로 실측)
- [x] 전체 테스트 green(`./gradlew :doc-service:test`) + 빌드 확인 — 최종 32개 테스트 green
- [x] 크래프트 게이트 self-check(java-expert + code-reviewer 병렬, `28613e4`) — [B] 1건 + minor 5건 발견·전부 수정, 핵심 로직 3곳(조상탐색 캡·owner_id 매핑·Base*Entity 미상속) 버그 없음 교차 확인
- [x] PR 생성 — 사용자 승인(1-PR 진행) 후 push + [backend PR #6](https://github.com/ressKim-io/weDocs-backend/pull/6) 오픈
- [x] max-effort 10-앵글 코드리뷰(fable 모델, `--comment`) — 인라인 8건 게시(HIGH 1·MEDIUM 2·LOW 5), 오탐 2건은 검증 단계에서 기각
- [x] 리뷰 findings 7/8건 반영(`77f8278`) + push — 4MB 캡 헤드룸(#6)은 리뷰가 자체적으로 "코드 수정 불필요" 명시해 미반영
- [x] PR #6 머지 완료(`1d7ce7b`, main 반영)

## 검증

1. 단위: `./gradlew :doc-service:test --tests "*PermissionServiceTest"` (DB 불필요, <1초)
2. 영속화: `./gradlew :doc-service:test --tests "*PermissionPersistenceTest"` (Testcontainers)
3. gRPC 통합: `./gradlew :doc-service:test --tests "*DocServiceGrpcIntegrationTest"` (4 RPC × happy/edge/error)
4. 회귀: `./gradlew :doc-service:test --tests "*PageTreePersistenceTest"` — 포트 바인딩 로그 없어야 함
5. 전체: `./gradlew :doc-service:test` green + `./gradlew :doc-service:build`(선행: `make proto-gen`)

## 범위 밖 (재확인)

M2 세션 plan §범위 밖과 동일 — consistent-hash 라우팅/Redis 복원(M3), outbox Kafka relay(M4), 클러스터 매니페스트(M5), 트리 CRDT/공개링크/버전히스토리(2차).

## 재개 지점 (Resume) — 완료

**최종 완료**: 구현(Stage 1~5) + 크래프트 게이트 self-check(java-expert+code-reviewer) + max-effort 10-앵글 코드리뷰(fable 모델) + 두 리뷰 findings 전부 반영 + [backend PR #6](https://github.com/ressKim-io/weDocs-backend/pull/6) **머지 완료**(`1d7ce7b`, 2026-07-04). 커밋 9개(`3f4feba`~`77f8278`), 32개 테스트 green, `make build` green. 1-PR 통짜로 진행(사용자 확정).

두 번째 리뷰 라운드에서 반영한 항목: test application.yml이 main을 완전 대체해 `ddl-auto=validate`가 꺼져있던 HIGH 이슈, `PermissionService` 조상 탐색 캡의 fail-open→fail-closed 전환(MEDIUM, `AncestorWalkResult`로 "루트 도달" vs "캡 도달" 구분), 나머지 3개 RPC의 `RuntimeException` catch-all 비대칭(MEDIUM-LOW), `SnapshotService` TOCTOU 제거, `GrpcServerLifecycle` executor 생성 시점 조정, `Makefile` doc-service 커버리지 확장. 4MB 캡 헤드룸(LOW)은 의도적으로 미반영(Phase 3 계약 문서화 대상).

**다음**: M2 세션 plan([2026-06-30-m2-persistence-session.md](2026-06-30-m2-persistence-session.md)) 재개지점을 "Phase 1c REST/JWT 진입"으로 갱신 → 새 세션에서 1c 착수.
