# ADR-0016 — 시스템 관리자(system_admin) 전역 역할

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: [PRD §4.3](../prd/4-data-and-permission-model.md) (D-7) · [ADR-0014](0014-auth-authz-boundary.md)(인증/인가 경계) · [M2 1a 보강 plan](../plans/2026-06-30-m2-1a-foundation-hardening.md)
- 범위: 시스템 관리자의 **데이터 모델 + enum 제약**까지. admin 전용 API·승격 플로우·인가 강제 = 후속(1c 인증 이후).

## 맥락

ADR-0014/PRD §4는 **워크스페이스 안** 권한만 정의했다: 멤버십 role(owner|member) + 페이지 공유 level(editor|viewer), 상속 해석. 이 모델엔 **플랫폼 운영자**가 없다 — 워크스페이스를 가로질러 인스턴스를 운영(워크스페이스 생성/삭제·계정 정지·장애 대응·데이터 점검)할 주체. 1a 데이터 레이어 점검에서 "User에 권한 차등(생성자/편집자/어드민)이 없다"는 지적이 나왔고, 그중 **어드민 = 시스템 관리자**로 확인됨(사용자 결정, 2026-06-30).

정해야 할 것: 시스템 관리자를 ① 어디에 모델링하나(전역 vs 관계형), ② 워크스페이스 역할과 어떻게 구분하나.

## 결정

1. **시스템 관리자 = `User`의 전역 속성** `system_role` (`user` | `system_admin`, 기본 `user`). 워크스페이스 역할(관계형)과 **직교(orthogonal)** — 사람 단위로 단 하나.
2. **enum + DB CHECK로 강제**: Java `enum SystemRole { USER, SYSTEM_ADMIN }`(JPA `@Enumerated(STRING)`) + `users.system_role varchar(16) NOT NULL DEFAULT 'user' CHECK (system_role IN ('user','system_admin'))`. 매직 스트링 금지(`clean-code.md`). 동일 원칙을 기존 `workspace_members.role`·`page_permissions.level`에도 CHECK로 소급.
3. **부여 = M2 범위 밖**(수동 시드). admin 승격 API·UI·감사는 후속. 1a는 컬럼+enum+기본값까지.
4. **인가 강제 위치 = 1c 인증과 함께**(REST 엔드포인트 가드 / `@PreAuthorize` 류). 1a는 인증이 없으므로 강제 로직 없음 — 모델만 선반영해 1c가 컬럼 추가 없이 바로 wire.

## 대안 비교

| 방안 | 모델 | M2 비용 | 멀티테넌시 적합 | 판정 |
|---|---|---|---|---|
| **User 전역 컬럼 `system_role`** (채택) | 사람 단위 단일 enum | 컬럼 1 + enum | ✅ 운영자는 워크스페이스 무관 전역 | ✅ 단순·명확, 1c에서 가드만 추가 |
| 별도 `system_admins` 테이블 | 관계(0..1) | 테이블+조인 | ✅ | △ 사람당 0/1행에 테이블은 과설계. 다중 admin 권한 분화 생기면 그때 |
| 워크스페이스 role에 `super` 추가 | 기존 관계형 재사용 | 작음 | ❌ | ❌ 시스템 운영은 워크스페이스 직교 — 멤버십에 끼우면 "모든 워크스페이스에 행 추가" 모순 |
| 외부 IdP/RBAC(Keycloak 등) | 외부 위임 | 큼(인프라) | ✅ | ❌ MLP 과투자. 가드레일(서비스 최소)·SDD §15 인증 내장과 충돌 |

## 결과

- `users.system_role` 추가 + 3개 enum 테이블(users/workspace_members/page_permissions)에 CHECK 제약 → 잘못된 역할 값을 DB가 거부.
- ADR-0014 인증 흐름과 정합: 1c에서 JWT 클레임에 `system_role` 포함 → 게이트웨이/doc-service가 admin 엔드포인트 가드.
- PRD §4.3에 system_admin 직교 역할 명문화.

## 트레이드오프 (인정)

- **전역 컬럼** → 향후 admin 권한 분화(예: billing-admin vs ops-admin)가 필요해지면 테이블로 승격 마이그레이션 필요. MLP에선 단일 admin으로 충분(YAGNI).
- **부여를 수동 시드**로 미룸 → M2에선 admin 승격 UI 없음. 부트스트랩 admin은 마이그레이션/시드 스크립트로(후속 문서화).
- **1a는 강제 없음** → 컬럼만 있고 인가 가드는 1c. 그 사이 admin 컬럼은 동작에 영향 없음(미사용이 아니라 **선반영**, AuditorAware 같은 죽은 컬럼과 달리 enum 기본값으로 의미 보유).
