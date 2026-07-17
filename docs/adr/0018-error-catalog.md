# ADR-0018 — 에러 카탈로그 컨벤션 (서비스별 ErrorCode enum + 카테고리 예외)

- 상태: **Accepted**
- 날짜: 2026-07-17
- 관련: [error-handling.md P7](../../.claude/rules/error-handling.md) (표준 본문) · [ADR-0014](0014-auth-authz-boundary.md)(비노출 원칙) · [plan 2026-07-17](../plans/2026-07-17-error-catalog-package-by-feature.md) (③-1이 doc-service 소급 적용)
- 범위: 서비스(배포 단위)별 도메인 에러의 **정의·전달·wire 포맷** 컨벤션. 경계 입력검증(Bean Validation·gRPC `INVALID_ARGUMENT`)·앱 배선 fail-fast는 비대상(P7 제외 조항).

## 맥락

doc-service 1c 완료 시점의 에러 처리: 실패 종류마다 leaf 예외 클래스(12개, 메시지는 각 생성자에 1개씩 분산) + HTTP advice가 카테고리 단위 type URI(`errors/not-found` 등)와 상태코드를 하드코딩 + gRPC 어댑터(`DocServiceImpl.failNotFound`)가 별도 description을 하드코딩. 결과: ① 실패 종류 추가 = 클래스 1개 신설 ② HTTP/gRPC 메시지가 이미 드리프트(REST는 uuid 보간 노출, gRPC는 고정 문구) ③ 카탈로그 부재로 "이 서비스가 낼 수 있는 실패 전체"를 한눈에 볼 수 없음 — AI/사람 모두 관리 비용 증가.

사용자 요구(2026-07-17): 에러 메시지를 서비스(k8s pod) 단위 enum으로 중앙 관리. 단 기존 `error-handling.md` P2("실패는 타입 — 호출자가 분기·매칭 가능")와 충돌하지 않아야 한다.

## 결정

1. **서비스별 `ErrorCode` enum이 실패 전체 집합의 SSOT.** 필드 = `slug`(kebab-case wire 식별자) · `message`(고정 영어 문구) · `HttpStatus` · `io.grpc.Status.Code`. 실패 종류 추가 = enum 엔트리 1줄.
2. **던지는 타입은 카테고리 예외 4~5종만**: `NotFoundException` / `ConflictException` / `ForbiddenException` / `UnauthorizedException` / `InvariantViolationException` — 각자 enum 엔트리를 보유하고, 생성자에서 카테고리↔status 정합을 검증. leaf 예외 클래스 증식 금지. (P2 충족: 호출자·advice는 카테고리 타입으로 매칭)
3. **코드 체계 = 도메인 slug** (`page-not-found`). `DOC-001`류 번호 체계 기각 — P2의 anti-opaque(의미 없는 번호)와 정면 충돌하고, 솔로 프로젝트에서 번호 대장 관리 비용만 추가.
4. **HTTP wire (RFC 9457 ProblemDetail)**: `type = https://wedocs.io/errors/<slug>`(코드 단위 — 현행 카테고리 URI에서 세분화), `detail = message`(고정 문구), 확장 property `code = <slug>`. 5xx 계열은 detail 고정 `"unexpected error"`(내부 message 미노출). 근거: RFC 9457 — "type = 문제 유형의 1차 식별자", "detail은 파싱 금지 → 기계 정보는 확장 멤버로" (✅ verified 2026-07-17).
5. **gRPC wire**: 어댑터가 `Status.fromCode(code.grpc()).withDescription(code.message())` — 경계 한 곳, HTTP와 같은 enum 경유. 매핑 지침: 미존재=`NOT_FOUND` / 중복=`ALREADY_EXISTS` / 사이클·교차 ws 등 상태 교정 필요=`FAILED_PRECONDITION`(gRPC 공식: "상태를 명시적으로 고치기 전 재시도 불가") / 권한=`PERMISSION_DENIED` / 인증=`UNAUTHENTICATED` / 불변식=`INTERNAL`.
6. **메시지 정책**: 고정 영어 문구, id·내부 상태 보간 금지(클라이언트는 요청 컨텍스트로 이미 앎, 필요 시 property·서버 로그로). AIP-193 정합: "동적 정보는 message가 아니라 metadata에".

## doc-service 카탈로그 (leaf 12 + raw 1 → 11 엔트리)

| enum | slug | HTTP | gRPC | 흡수 대상 |
|---|---|---|---|---|
| PAGE_NOT_FOUND | page-not-found | 404 | NOT_FOUND | PageNotFoundException |
| WORKSPACE_NOT_FOUND | workspace-not-found | 404 | NOT_FOUND | WorkspaceNotFoundException |
| USER_NOT_FOUND | user-not-found | 404 | NOT_FOUND | UserNotFoundException |
| EMAIL_ALREADY_USED | email-already-used | 409 | ALREADY_EXISTS | EmailAlreadyUsedException |
| DUPLICATE_MEMBER | duplicate-member | 409 | ALREADY_EXISTS | DuplicateMemberException |
| PAGE_CYCLE | page-cycle | 409 | FAILED_PRECONDITION | PageCycleException.cycle() |
| PAGE_DEPTH_CAP_EXCEEDED | page-depth-cap-exceeded | 409 | FAILED_PRECONDITION | PageCycleException.depthCapExceeded() |
| CROSS_WORKSPACE_PARENT | cross-workspace-parent | 409 | FAILED_PRECONDITION | CrossWorkspaceParentException |
| INSUFFICIENT_PERMISSION | insufficient-permission | 403 | PERMISSION_DENIED | ForbiddenException |
| INVALID_CREDENTIALS | invalid-credentials | 401 | UNAUTHENTICATED | InvalidCredentialsException |
| INVARIANT_BROKEN | invariant-broken | 500 | INTERNAL | DocMetaService raw IllegalStateException |

## 대안 비교

| 방안 | 파일 수 | P2(타입 분기) | 중앙 관리 | 판정 |
|---|---|---|---|---|
| **카테고리 예외 + ErrorCode enum** (채택) | enum 1 + 클래스 5 | ✅ 카테고리 매칭 | ✅ enum 1곳 | ✅ P2·중앙 관리 동시 충족, 매핑 SSOT |
| 단일 `BusinessException(code)` (Toss류) | 클래스 1 + enum 1 | ❌ 타입 분기 포기 | ✅ | ❌ P2 위반 — advice·호출자가 code 값으로 분기(문자열/enum switch 회귀). 표준 개정 비용까지 추가 |
| per-leaf 예외 유지 (현행) | 클래스 12+, 계속 증가 | ✅ | ❌ 12파일 분산 | ❌ 실패 전체 집합 비가시·HTTP/gRPC 드리프트 실증(uuid 보간 vs 고정 문구) |
| 번호 코드(`DOC-001`) + 대장 | — | △ | △ | ❌ P2 anti-opaque 충돌, 번호↔의미 대장 이중 관리 |

## 결과

- `error-handling.md` P7 + `[B]` 2행·`[A]` 1행으로 게이트 강제(시뮬레이션: 기대 발화 전부·오탐 0, 2026-07-17).
- doc-service 소급 = plan ③-1 (`refactor/doc-service-error-catalog`). ws-gateway·crdt-engine: Rust는 `thiserror` enum이 그 자체로 카탈로그(P7 Rust 실현), gateway는 도메인 에러 표면이 생길 때 적용.
- **선언된 wire 변경**(소비자=자사 frontend, 아직 에러 포맷 미소비): type URI 카테고리→코드 단위, `code` property 추가, detail의 uuid 보간 제거.

## 트레이드오프 (인정)

- **type URI 세분화** → 기존 통합 테스트의 type 단언 3곳 갱신 필요. 카테고리 URI 유지+code만 추가하는 절충안은 테스트 무변경이 장점이지만, type의 식별력(RFC 9457 "1차 식별자")을 버리고 HTTP status와 중복되는 정보만 남겨 기각.
- **카테고리 5종 고정** → 새 실패가 기존 카테고리에 안 맞으면 카테고리 신설 필요(예외적). 카테고리↔status 정합 assert가 오배치를 컴파일·기동 시점이 아닌 생성 시점에 잡는 한계는 `DocErrorCodeTest`(파라미터라이즈 전수 검증)로 보완.
- **고정 문구** → 디버깅 컨텍스트가 응답에서 사라짐. 서버 로그(P6)와 property가 대체 — 클라이언트 노출 최소화(secure-coding P4)와 정합.
