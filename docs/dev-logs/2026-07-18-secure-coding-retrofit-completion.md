---
date: 2026-07-18
category: migration
tier: 2
importance: major
status: resolved
tags: [secure-coding, dos-chain, room-validation, resource-cap, retrofit, crdt-engine, ws-gateway, doc-service, frontend]
related:
  - plans/2026-07-03-secure-coding-retrofit.md
  - plans/2026-07-03-security-quality-standards.md
  - dev-logs/2026-07-03-craft-standards-v2-security-quality.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
---

# secure-coding retrofit 완료 — 3-레포 관통 DoS 체인 차단

## 무엇

[2026-07-03 plan](../plans/2026-07-03-secure-coding-retrofit.md)에서 게이트 시뮬레이션으로 식별한 기존 코드 `[B]` 위반(핵심 = frontend 무검증 room → gateway 무검증 전달 → engine 무한 문서 생성) 소급 정합. controller 세션과 별도로 서비스 3레포(crdt-engine·backend·frontend)에서 작업·머지되어 있었고, 이번 세션은 4레포 pull 동기화 중 plan 상태(`planned`, 체크박스 전부 미완)와 실제 머지 상태의 드리프트를 발견해 문서만 사후 정합했다 — **코드 작성은 이 세션에서 하지 않음**, 아래는 머지된 커밋의 실제 diff·커밋 메시지 근거.

## 머지된 PR (전부 2026-07-18 23:2x~23:4x, controller 마지막 동기화 시점 이후)

| 레포 | PR | 커밋 | 대상 |
|---|---|---|---|
| crdt-engine | [#9](https://github.com/ressKim-io/weDocs-crdt-engine/pull/9) | `5854b72` | P0 엔진측 |
| backend (ws-gateway) | [#14](https://github.com/ressKim-io/weDocs-backend/pull/14) | `1d94a9a` | P0/P1 게이트웨이측 |
| backend (doc-service) | [#15](https://github.com/ressKim-io/weDocs-backend/pull/15) | `a74667b` | P2 |
| frontend | [#3](https://github.com/ressKim-io/weDocs-frontend/pull/3) | `f7b5b92` | P2 |

## 한 일 (plan 체크리스트 대비)

### P0 — 엔진 (`5854b72`)
- **SC-P1**: `DocId` — `From` 무검증 wrap → `TryFrom<&str>`(길이 1..=128·`[A-Za-z0-9_-]`). 위반은 서버 로그 + 클라 분류 code(`invalid-doc-id`)만 반환.
- **SC-P2**: `DocRegistry::open()` → `Result` 반환, `MAX_DOCUMENTS`(기본 10,000, 테스트 주입 가능) 초과 시 `resource_exhausted`. **기존 문서 재open은 상한 무관**(fast-path). `main.rs`에 `max_decoding_message_size` 4MB 명시(tonic 기본과 동일값이지만 암묵 의존 해소) + HTTP/2 keepalive.
- **SC-P4**: doc-id mismatch 에러의 서버측 값 에코백 제거 — 분류 code만 클라에 노출.
- **DP-P4/P5**: `ServerFrame` 수동 조립 4곳 → `sync_step1`/`update_only` 스마트 생성자로 단일화.
- **P1**: `Sync`/`GetSnapshot` 신뢰 경계 주석 추가(인가 구현은 M2 Phase 2, mTLS/NetworkPolicy는 M5 — retrofit 범위 아님을 명시).
- 부수: `crossbeam-epoch` 0.9.18→0.9.20 (RUSTSEC-2026-0204, criterion 경유 dev-dep transitive — 프로덕션 바이너리 무관이나 audit 전체 lockfile 검사라 해소).
- 검증: 17 테스트 green(수렴 proptest 회귀 포함), clippy `-D warnings`·fmt 통과. 크래프트 게이트(rust-expert 🦀 + code-reviewer) 블로킹 0.

### P0 — 게이트웨이 (`1d94a9a`)
- **SC-P1/DP-P6**: `RoomId` 도메인 타입 신설 — **엔진 `DocId`와 동일 규칙**(길이·문자집합 대칭). `RoomHandshakeInterceptor`가 WS 업그레이드 **전** 검증 → 무효 room은 HTTP 400(세션 미생성), 유효 `RoomId`만 세션 attribute로 관통.
- **SC-P2**: `ServletServerContainerFactoryBean`으로 WS 바이너리 프레임 상한 명시(엔진 gRPC 4MB에서 `ClientFrame` 재포장 오버헤드만큼 뺀 값 — "게이트웨이는 수락, 엔진은 거부" 경계 실패 방지) + 텍스트 8KB + 세션 idle 10분. Tomcat 기본 8192B 암묵 의존 해소.
- **SC-P5**: `setAllowedOriginPatterns("*")` → `setAllowedOrigins`(화이트리스트, prod는 `WEDOCS_GATEWAY_ALLOWED_ORIGINS` 미주입 시 fail-closed).
- **P1**: `EngineClient` gRPC 채널 keepalive(30s/10s) — 엔진 HTTP/2 keepalive와 대칭.
- 검증: 40 테스트 green(RoomId 16·통합 5·Lib0 9·codec 10). 크래프트 게이트(java-expert ☕ 바이트코드 검증 + code-reviewer) findings 반영(경계 마진·pre-handshake 이동·거부 테스트 보강).

### P2 — doc-service (`a74667b`)
- 커밋된 dev DB 크리덴셜(main `application.yml`의 localhost/wedocs 기본값) 제거 → env 주입 필수(fail-closed). 로컬 dev 기본값은 `application-dev.yml`(`SPRING_PROFILES_ACTIVE=dev`, `make run-doc`)로 분리.
- dead 쿼리 `PageRepository.findByWorkspaceId`(무상한·미사용) 삭제. `findByParentId`는 테스트 전용 주석 명시.
- **plan 대비 편차**: "무페이지네이션 조회 Pageable" 항목은 재확인 결과 **이미 처리돼 있었음**(트리 쿼리 = Limit 적용, `findById_UserId`는 기존에 문서화된 의도적 예외) — 신규 코드 변경 없이 체크만 완료.
- 검증: 148 테스트 green. 크래프트 게이트(java-expert + code-reviewer, env 미설정 실기동으로 fail-closed 실측) 블로킹 0.

### P2 — frontend (`f7b5b92`)
- `sanitizeRoom(?room=)`: 엔진/게이트웨이와 동일 규칙(길이 1..=128·`[A-Za-z0-9_-]`) 검증, 위반/미지정 시 `demo` 폴백 — 클라이언트 선방어(defense-in-depth).
- `resolveWsUrl`: https 페이지에서 평문 `ws://` → `wss://` 강제 승격(mixed-content 차단). 순수 함수로 분리해 node 환경 테스트 가능.
- 검증: typecheck·unit 5·prod build green. 크래프트 게이트(code-reviewer, 3-레포 규칙 정합 대조) 블로킹 0.

## 결정 (decisions)
- **DocId(engine) / RoomId(gateway) / sanitizeRoom(frontend)가 동일 검증 규칙(길이 1..=128·`[A-Za-z0-9_-]`)을 3레포에 독립 구현** — 공용 라이브러리로 묶지 않음. 폴리글랏(Rust/Java/TS) 경계라 공유 코드보다 규칙 동기화 문서화가 실용적이라는 기존 판단(plan 원문)대로 유지.
- ADR 신설 없음 — 이 규칙은 각 PR 커밋 메시지 + 본 dev-log로 추적. 3번째 레포가 같은 규칙을 또 어긴다면 그때 ADR 승격 검토.

## 다음
- Phase 2(M2 인증) 착수 — `docs/plans/2026-06-30-m2-persistence-session.md` §재개지점.
- 이 세션에서 발견한 것처럼, **서비스 레포에서 진행된 작업이 controller plan 상태에 반영되지 않는 드리프트**가 재발할 수 있음 — 서비스 레포 PR 머지 후 controller plan 갱신을 세션 종료 체크리스트에 포함 고려.

## 관련 자료
- plan = `docs/plans/2026-07-03-secure-coding-retrofit.md`(done)
- 게이트 시뮬레이션 실측 원본 = `docs/dev-logs/2026-07-03-craft-standards-v2-security-quality.md`
