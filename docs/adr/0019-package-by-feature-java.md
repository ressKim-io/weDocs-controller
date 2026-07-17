# ADR-0019 — Java 서비스 패키지 구조 = package-by-feature

- 상태: **Accepted**
- 날짜: 2026-07-17
- 관련: [layering-readability.md P7](../../.claude/rules/layering-readability.md) (표준 본문) · [ADR-0018](0018-error-catalog.md)(`common/error/` 거처) · [plan 2026-07-17](../plans/2026-07-17-error-catalog-package-by-feature.md) (③-3이 doc-service 소급 적용)
- 범위: **doc-service의 구체 패키지 트리 결정** + Java 서비스 일반 원칙. ws-gateway는 이번 비대상(아래 결과 참조).

## 맥락

doc-service는 1a~1c 동안 레이어 우선 구조(`api/`·`service/`·`repository/`·`domain/`)로 성장했고, 그 결과 `service/` 통패키지에 22파일(서비스 7 + 가드 2 + 값객체 1 + **예외 12**)이 혼재, auth feature는 3개 패키지(`api/`·`service/`·`auth/`)에 분산됐다. "네이밍/위치만 보고 어떤 작업인지 알 수 있어야 한다"는 요구(2026-07-17)에 대해 레이어 구조는 구조적으로 불리하다 — 한 기능의 변경이 항상 4개 패키지를 가로지른다.

파일 ~50개인 지금이 이동 비용이 가장 싼 시점이고, M2 후속(스냅샷 저장·복원·outbox)으로 파일 수는 계속 는다.

## 결정

1. **패키지는 기능(도메인) 기준** — 각 feature 패키지가 자기 controller·service·entity·repository를 **평면으로** 보유. feature 내부에 계층 서브패키지 재생성 금지: 같은 패키지여야 package-private 은닉이 가능(Spring Modulith: "모듈의 API = 패키지의 public 타입", ✅ verified 2026-07-17).
2. **doc-service 목표 트리** (`io.wedocs.doc` 하위):

```
DocServiceApplication            (루트 유지)
auth/       AuthController · JwksController · Signup/Login/Token/UserResponse dto
            · AuthService · User · SystemRole(+Converter) · UserRepository
            · SecurityConfig · AuthWebConfig · JwtConfig · JwtKeys · JwtProperties
            · JwtTokenService · CurrentUserId(+ArgumentResolver)     ← 기존 auth/* 제자리
workspace/  WorkspaceController · dto 4종 · WorkspaceService · WorkspaceAccessGuard
            · Workspace · WorkspaceMember(+Id) · WorkspaceRole(+Converter)
            · WorkspaceRepository · WorkspaceMemberRepository
page/       PageController · PageSharingController · dto 5종
            · PageTreeService · PageSharingService · PermissionService
            · PageAccessGuard · EffectivePermission · DocMetaService
            · Page · PagePermission(+Id) · PagePermissionLevel(+Converter)
            · PageRepository · PagePermissionRepository
snapshot/   SnapshotService · PageSnapshot · PageSnapshotRepository
grpc/       DocServiceImpl · GrpcServerLifecycle      (크로스-feature 전송 어댑터 — 제자리)
common/
  error/    DocErrorCode · DomainException · 카테고리 예외 5종 · GlobalExceptionHandler
  jpa/      BaseCreatedEntity · BaseTimeEntity · JpaAuditingConfig
  validation/ MaxUtf8Bytes(+Validator)
```

3. **배치 근거**:
   - **가드 = 소유 feature**: `PageAccessGuard`→page, `WorkspaceAccessGuard`→workspace — 가드가 그 feature의 "공개 API"(다른 feature는 repo 직접 주입 대신 가드 경유, layering P7 [A]행).
   - **PermissionService·EffectivePermission·공유 = page**: 페이지 권한 해석이 본질(workspace baseline 접근은 [A] 지양 항목으로 존치, ③-3에서 행동 변경 없이 이동만).
   - **DocMetaService = page**: 페이지 메타 read 모델. `grpc/`는 호출자일 뿐.
   - **JwtTokenService = auth**: `@Service`지만 인증 인프라 — auth feature 평면에 잔류(레이어명 패키지로 이동하지 않음).
   - **Converter = enum과 동거**, **DTO record = feature 평면**(별도 `dto/` 서브패키지 금지 — 평면 원칙).
   - **`grpc/` top-level 유지**: page/workspace/snapshot 3개 feature를 단일 proto 서비스로 디스패치하는 어댑터 — P7의 명시 예외.
4. **base package(`io.wedocs.doc`) 불변** — 컴포넌트 스캔·JPA 엔티티 스캔·Flyway 무영향.
5. **Spring Modulith 도입은 비목표** — 검증기(`ApplicationModules.verify()`)·이벤트는 필요 근거가 생기면 별도 결정. 지금은 컨벤션+게이트로 충분(의존 최소 가드레일).

## 대안 비교

| 방안 | 변경 지역성 | 은닉 | 이동 diff | 판정 |
|---|---|---|---|---|
| **package-by-feature 평면** (채택) | ✅ 기능 변경=패키지 1곳 | ✅ package-private 활용 가능 | 큼(1회, 순수 이동) | ✅ 파일 50개인 지금이 최저 비용, M2 성장 대비 |
| 레이어 유지 + `exception/` 신설 등 최소 정리 | ❌ 여전히 4패키지 횡단 | ❌ 전 타입 public 강제 | 최소 | ❌ 통패키지 비대화 문제(1a→1c 실증) 지속, 미봉 |
| feature + 내부 계층 서브패키지(`page/api/`, `page/service/`) | ✅ | ❌ 서브패키지 갈라지면 전부 public 필요 | 큼 | ❌ 은닉 포기 — Modulith "API=패키지 public 타입" 원칙과 상충 |
| Spring Modulith 풀 도입(검증기+이벤트) | ✅ | ✅ | 큼+의존 추가 | △ 과투자 — 컨벤션 먼저, 검증기는 모듈 경계 위반이 반복 관측되면 |

## 결과

- `layering-readability.md` P7 + `[B]`(통패키지 신설·비대화)·`[A]`(교차 feature repo 주입) 게이트 강제(시뮬레이션 2026-07-17: 오탐 0).
- doc-service 소급 = plan ③-3 (`refactor/doc-service-package-by-feature`, move-only PR — git.md §Size Limit 단서).
- 테스트도 미러 이동. `RestTestSupport`는 교차 패키지화로 public 승격(비-이동 diff로 PR 본문에 열거).
- **ws-gateway 비대상**: 파이프라인형 소형 모듈(6파일, feature 개념 없음 — ws↔gRPC 브리지 단일 관심사). 구조 변경이 필요해지는 시점(M2 Phase 2 인증 등)에 이 ADR 적용 여부 재판단.

## 트레이드오프 (인정)

- **1회성 대형 diff** → git rename detection(`-M90%`)으로 리뷰 부담 통제, 로직 0 변경 규율 + squash 단일 revert 롤백.
- **평면 패키지는 파일 수가 늘면 다시 붐빈다** → feature가 ~20파일을 넘으면 그 feature를 쪼개는 게 정답(서브패키지가 아니라 feature 분화). page가 최대(19)로 경계 근처 — 공유/권한이 커지면 `sharing/` 분화 후보.
- **교차 feature 접근이 드러난다**(PermissionService→workspace repo 등) → 단점이 아니라 의도: 숨어 있던 결합이 [A] 행으로 가시화, backstop(사유 주석)으로 관리.
