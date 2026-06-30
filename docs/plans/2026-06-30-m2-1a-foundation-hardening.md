---
date: 2026-06-30
slug: m2-1a-foundation-hardening
status: planned
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0014-auth-authz-boundary.md
  - adr/0012-crdt-boundary-content-vs-tree.md
  - prd/4-data-and-permission-model.md
---

# M2 1a 기초 보강 — 감사필드 · 공통화 · enum 제약 · 시스템 admin

## Context

[backend PR #3](https://github.com/ressKim-io/weDocs-backend/pull/3)(M2 1a 데이터 레이어, 브랜치 `feature/m2-doc-service-skeleton`, 커밋 1089ec8, **미머지**)에 대한 사용자 점검 요청에서 기초 구멍 다수 확인. 핵심:

1. **감사 필드 미매핑** — DDL엔 `created_at`/`updated_at`이 있으나 엔티티가 하나도 매핑 안 함. `ddl-auto=validate`는 *매핑된* 컬럼만 검사하므로 통과(정합성 착시). `updated_at`은 `default now()`(INSERT only)뿐 — UPDATE 트리거도 JPA `@LastModifiedDate`도 없어 수정 시각이 **생성 시각에 박제**(기능 버그).
2. **공통화 부재** — `@MappedSuperclass` 베이스 없음. 4 엔티티가 id/생성자/getter 반복.
3. **권한 매직 스트링** — `workspace_members.role`·`page_permissions.level`이 `varchar(16)`에 CHECK·enum 없음(`clean-code.md` 위반).
4. **시스템 admin 부재** — PRD §4.3은 `workspace owner`까지만 정의. 전역 시스템 관리자 미설계 → **사용자 결정: 추가 필요**.

사용자 결정(2026-06-30): **① 시스템 관리자 역할 추가, ② P0를 이번 1a PR 브랜치에서 보강.**

### 확정한 설계 결정 (근거)

| # | 결정 | 근거 |
|---|---|---|
| D1 | **시각 감사**: `BaseTimeEntity`(@MappedSuperclass, `@CreatedDate` createdAt[updatable=false] + `@LastModifiedDate` updatedAt) → User/Workspace/Page 적용. `@EnableJpaAuditing`. PageSnapshot은 createdAt만(스냅샷은 통째 교체) | 사용자 핵심 지적("create/update date") |
| D2 | **행위자 감사(created_by/updated_by)는 1c로 미룸** — 인증 SecurityContext가 1c에 생김. 지금 `AuditorAware` 소스가 없어 컬럼 추가해도 항상 null = 죽은 컬럼(방금 비판한 "validate가 가리는 미사용 컬럼"과 동일 악취). 1c에서 컬럼+`@CreatedBy`/`@LastModifiedBy`+AuditorAware 동시 추가 | 카고컬트 회피 |
| D3 | **enum + CHECK**: `users.system_role`(enum `SystemRole{USER, SYSTEM_ADMIN}`, DEFAULT 'user') · `workspace_members.role` CHECK in('owner','member') · `page_permissions.level` CHECK in('editor','viewer'). Java enum `WorkspaceRole`/`PagePermissionLevel`도 지금 추가(엔티티는 1b여도 타입은 미리) | `clean-code.md` 매직 넘버 제거 |
| D4 | **시스템 admin = User 전역 속성** `users.system_role`. 워크스페이스/페이지 역할은 관계형(상황별)이지만 시스템 admin은 사람 단위 전역 → User에 둠 | PRD §4 모델 확장 |
| D5 | **V1 직접 수정**(V2 신설 아님) — PR 미머지, V1은 Testcontainers(휘발성)에서만 적용 → checksum 변경 무해 | 미적용 마이그레이션 |
| D6 | **UUID 생성**: 현행 app-side `UUID.randomUUID()` 유지. UUIDv7(인덱스 지역성) 채택은 별도 ADR 후속(생성기/의존성 결정 필요) — P0에서 새 의존성 도입 안 함 | scope 최소 |
| D7 | **Lombok 미도입** — 현 컨벤션(ws-gateway 포함 순수 Java) 유지. `@NoArgsConstructor`는 Lombok 전제라 전역 결정 사안 → 별도 검토(JDK 25 지원 버전 검증 포함). BaseEntity로 보일러플레이트만 축소 | 컨벤션 일관성 |

### 범위 밖 (이 plan에서 안 함)
- WorkspaceMember/PagePermission **엔티티 매핑**·상속 해석 로직 → **1b**(plan §108대로). 본 plan은 enum 타입 + DDL CHECK까지만.
- created_by/updated_by 컬럼·AuditorAware → **1c**(인증 후).
- UUIDv7 전환, Lombok 도입, E1(트리 동시성 @Version), E4(실 UPSERT 테스트) → 후속.
- 역방향 인덱스(E3, `user_id`) — 1b 권한 조회 시 추가(엔티티와 함께). 단 한 줄이라 리뷰 시 포함 여부 사용자 확인.

## 실행 체크리스트

### Part 1 — controller (시스템 admin 설계, main 직접)
- [ ] `docs/adr/0016-system-admin-role.md` — 전역 시스템 admin 결정(대안: User 전역 role vs 별도 admin 테이블 vs 외부 IdP). PRD §4.3 권한표에 `system_admin` 티어 추가 근거
- [ ] `docs/prd/4-data-and-permission-model.md` §4.3 권한 레벨표에 시스템 admin 행 추가 + §2 엔티티표 User에 `system_role` 속성
- [ ] (plan 커밋은 ★ 먼저 — 아래 라이프사이클)

### Part 2 — backend 1a 브랜치 (건별 승인·push 승인)
- [ ] `V1__init_page_tree.sql` 수정: users/workspaces에 `updated_at` 추가 · users에 `system_role varchar(16) not null default 'user'` + CHECK · workspace_members.role CHECK · page_permissions.level CHECK
- [ ] `domain/BaseTimeEntity.java` 신설(@MappedSuperclass + Auditing 콜백)
- [ ] `config/JpaAuditingConfig.java` 신설(`@EnableJpaAuditing`)
- [ ] `domain/SystemRole.java`·`WorkspaceRole.java`·`PagePermissionLevel.java` enum 신설
- [ ] `User`/`Workspace`/`Page` → `extends BaseTimeEntity`, User에 `systemRole` 매핑. `PageSnapshot`에 createdAt 매핑
- [ ] `PageTreePersistenceTest` 갱신 + 감사 테스트(createdAt 채워짐 / updatedAt이 update 시 갱신) + system_role 기본값 + CHECK 위반 거부
- [ ] `./gradlew :doc-service:test` green

## 검증
```bash
# backend
cd ../weDocs-backend && ./gradlew :doc-service:test
# 감사: 저장 후 createdAt non-null, update 후 updatedAt > createdAt
# system_role: 기본 'user', enum 매핑 STRING
# CHECK: 잘못된 role/level INSERT 시 DataIntegrityViolation
```
- validate 통과만으로 정합 판단 금지(이번 사고의 교훈) — 감사 필드는 **값 검증 테스트**로 확인.

## 재개 지점 (Resume)
- **마지막 완료**: plan 작성(이 파일).
- **다음**: Part 1 controller ADR-0016 + PRD §4.3 → 커밋(main). 이어 Part 2 backend 브랜치 작업(건별 승인).
- **주의**: backend = 서비스 레포 → 커밋/push 건별 승인. V1 직접 수정(미머지라 안전). created_by/UUIDv7/Lombok은 **이 plan 범위 밖**(후속).

## 범위 밖
위 "범위 밖" 섹션 참조. 1b(권한 엔티티·gRPC)·1c(인증·행위자 감사)로 명확히 분리.
