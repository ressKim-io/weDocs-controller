---
date: 2026-07-28
slug: m2-phase2c-frontend-auth
status: in-progress
related:
  - plans/2026-07-19-m2-phase2-auth-authz.md
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0014-auth-authz-boundary.md
  - adr/0017-jwt-rs256-jwks.md
  - adr/0021-ws-handshake-auth-failure-observability.md
---

# M2 Phase 2c — 프론트엔드 인증 · 페이지 선택 · 역할 인지

> Phase 2의 마지막 조각. 2a/2b가 서버측 인증·인가를 세우면서 **끊긴 클라이언트 경로를 복구**하고,
> viewer가 자기 역할을 모른 채 로컬만 divergent해지는 **정합성 버그를 근본 해소**한다.
> 성공 조건 = 브라우저에서 로그인 → 페이지 생성 → 두 탭 수렴, viewer 계정은 **편집 자체가 잠김**.

## Context

**왜 지금** — 2a(gateway 인증/인가) · 2b(engine role 강제)가 머지되면서 **프론트엔드는 현재 깨져 있다.**
`Editor.tsx`는 토큰 없이 `WebsocketProvider`를 열고 기본 room은 `demo`(비UUID)다
→ 게이트웨이가 **401**(무토큰)로 거절하고, 토큰이 있더라도 비UUID라 **403**(2a-2 D1)이다.
기존 수렴 E2E도 같은 이유로 실패 상태. **2c는 신규 기능이 아니라 복구 작업이다.**

**왜 원래 계획보다 큰가** — 기존 phase2 plan의 2c는 "`protocols` 옵션으로 JWT 전달" 한 줄이었다.
그러나 프론트엔드에는 **로그인이 전혀 없고**(토큰 출처 없음) **페이지 UUID를 얻을 방법도 없다**
(1c에서 만든 REST를 아무도 소비하지 않는다). 토큰 수동 주입으로 우회하면 데모가 사실상 사용 불가다.

**사용자 결정(2026-07-28)**

| # | 결정 | 근거 |
|---|---|---|
| E1 | **로그인 + 페이지 목록까지 제대로 만든다** (토큰 주입 우회 채택 안 함) | 1c REST의 첫 실사용자. `?token=` URL 전달은 history·referrer·로그 유출이라 secure-coding상 부적절 |
| E2 | **viewer 문제를 근본 해결** — doc-service가 effective role을 노출하고 프론트가 편집을 잠근다 | 아래 §viewer 문제의 실체. 사용자: "초기에 프론트 신경을 못 써서 약한 부분 — 근본적으로 해결하면서 가자" |
| E3 | **E2E는 REST 부트스트랩 자동화** (환경변수 토큰 주입 채택 안 함) | 자기완결적 · viewer/editor/무토큰 3케이스를 실제로 검증 가능. 대가 = 사전조건 2프로세스 → 4프로세스 |

### viewer 문제의 실체 (E2가 푸는 것)

게이트웨이는 viewer의 update를 **조용히 drop**한다(`ws_write_dropped_total{reason=viewer}`).
그런데 **클라이언트는 자기 역할을 알 방법이 없다** — `PageResponse`에 역할 필드가 없고,
핸드셰이크는 SENTINEL만 echo한다(토큰도 역할도 반향 안 함).

결과: viewer가 타이핑하면 로컬 `Y.Doc`에는 반영되지만 서버엔 영원히 가지 않고, 이후 서버 업데이트와
머지되며 **로컬만 divergent**해진다 → 새로고침하면 조용히 유실. **UX 문제가 아니라 정합성 버그다.**
근본 해결 = 역할을 노출하고 viewer면 Tiptap을 `editable: false`로 잠가 **애초에 발생시키지 않는다**.

### 사전 검증 완료 ✅ (2026-07-28, 설치된 소스·실코드 직접 확인 — 추측 아님)

| 사실 | 근거 |
|---|---|
| y-websocket 3.0.0이 `protocols` 지원 | `node_modules/y-websocket/src/y-websocket.js:274`(기본 `[]`) · `:294`(`this.protocols = protocols`) · `:176`(`new provider._WS(url, provider.protocols)`) |
| 재접속마다 `provider.protocols`를 **다시 읽음** | `:176`이 `setupWS` 내부 → 토큰 갱신은 배열 교체로 반영 가능 |
| 무토큰이면 **무한 재접속**(backoff 상한 2500ms) | `:277 maxBackoffTime = 2500` · `:164`. ⚠️ **브라우저는 401을 볼 수 없다**(WS 실패는 code 1006뿐) → **연결 전에 막는 것이 유일한 근본 대책** |
| `connect: false` + `provider.connect()/disconnect()` 존재 | `:318` · `:499` · `:507` |
| 게이트웨이 규약 = `[SENTINEL, <jwt>]`, SENTINEL=`wedocs.sync.v1` | `ws-gateway/…/auth/AuthSubprotocol.java` — 토큰이 정확히 1개가 아니면 fail-closed 거절 |
| **권한 해석기는 이미 단일 소유** | `PermissionService.resolve()` ← gRPC `DocServiceImpl.java:56` **와** REST `PageAccessGuard` 양쪽이 호출 → REST 노출은 **로직 추가 없이** 기존 반환값을 흘리기만 하면 됨 = **드리프트 0** |
| `PageAccessGuard.requireRead()`가 이미 `EffectivePermission`을 **반환**하는데 `PageTreeService.get()`이 **버리고 있다** | `PageAccessGuard.java:20-26` · `PageTreeService.java:89-92` |
| CORS·Origin 화이트리스트에 `localhost:5173` 이미 설정 | doc-service `SecurityConfig`(`cors-allowed-origins`) · gateway `application.yml`(`allowed-origins`) → 신규 인프라 작업 불요 |
| Node E2E(Origin 헤더 없음)도 Spring Origin 검사 통과 | 기존 수렴 E2E가 동일 구성으로 동작했음 |
| doc-service 포트·엔드포인트 | REST `:8081` · gRPC `:50052` · `POST /api/auth/{signup,login}` · `/api/workspaces` · `/api/pages` · `PUT /api/pages/{id}/permissions/{userId}` |

## Blast Radius

| 항목 | 내용 |
|---|---|
| 직접 변경(controller) | 이 plan · phase2 plan §2c(링크로 교체) · `docs/status/current.md` |
| 직접 변경(backend) | `PageTreeService.get` 반환 확장 · `PageController` 단건 응답 타입 신설 · 테스트 |
| 직접 변경(frontend) | `src/api/*` · `src/auth/token.ts` · `LoginForm`/`WorkspaceBootstrap`/`PageList` 신규 · `App.tsx`·`Editor.tsx`·`connection.ts` 변경 · `test/e2e/` 재작성 · README·`.env.example` |
| 간접 영향 | `GET /api/pages/{id}` 응답 shape 변경(현 소비자 = 테스트뿐) · E2E 사전조건 2 → 4 프로세스 |
| 롤백 | 각 PR revert. **proto 무변경** → 태그 bump 불요 |
| 다운타임 | 없음(로컬 dev/test). 클러스터 배포 = M5 |

## 실행 체크리스트

> 서비스 레포(backend·frontend)는 전부 **branch + PR + 건별 승인**. controller만 main 직접.

### C0. controller — plan 기록 (main 직접)
- [ ] **C0** `docs(plan):` 이 plan + phase2 §2c 링크 교체 + `current.md` 갱신 → **커밋**(코드 작업의 전제)

### C1. doc-service — 호출자의 effective role 노출 (backend PR)

역할 해석 로직을 **새로 쓰지 않는다.** 이미 반환되는 값을 버리지 않고 흘리는 것이 전부다(드리프트 0).

- [x] **C1-1** `PageTreeService.get()`이 `pageAccess.requireRead()`의 반환값(`EffectivePermission`)을 함께 반환 (`PageView`)
- [x] **C1-2** `GET /api/pages/{pageId}` 응답에 `myRole` 추가 — **단건 전용 `PageDetailResponse`**.
      ⚠️ `myRole`(표시용) + **`canEdit`(판단용)** 을 **둘 다** 내보냈다. 역할만 주면 "editor 또는 owner가 편집 가능"이라는
      **서버 정책을 클라이언트가 재구현**하게 되고 그 자리가 곧 드리프트 지점이다 → 프론트(C3-4)는 **반드시 `canEdit`으로 분기**한다
- [x] **C1-3** 노출 enum(`PageDetailResponse.Role`)에서 `NONE` 제외 + 도달 시 fail-closed. 단위 테스트로 고정
- [x] **C1-4** 테스트 154 green(+6): 해석 네 갈래(ws owner / ws member baseline / 명시 공유 / **조상 상속**) 종단 검증 + 매핑 단위
- [x] **C1-5** 크래프트 게이트(☕ 6종, **인라인 실행**) → **[B] 1건 발견·수정** → PR
- [x] 커밋 `099f90b` · **[backend PR #19](https://github.com/ressKim-io/weDocs-backend/pull/19)** (머지 대기)

> **게이트 [B] 소거(2026-07-28)**: `toRole`의 raw `IllegalStateException` = error-handling **P7 위반**
> (`InvariantViolationException` doc 주석이 이 금지를 명시, `DocMetaService`에 같은 위반이 retrofit으로 제거된 선례).
> 카탈로그 예외로 교체 → 부수적으로 secure-coding **P4**(내부 상세 노출 경로)도 닫힘.
> **교훈**: 이 레포는 "불변식 위반"에도 카탈로그 경로(`INVARIANT_BROKEN` + `isInternal()`)가 이미 있다 —
> 새 코드에서 raw `IllegalState`/`IllegalArgument`로 서버 불변식을 표현하지 않는다.

### C2. frontend — 인증 셸 (login → 토큰) (frontend PR)

- [ ] **C2-1** `src/api/client.ts` — fetch 래퍼. base = `VITE_API_URL`(기본 `http://localhost:8081`),
      `Authorization: Bearer`, **RFC 9457 ProblemDetail 파싱**(doc-service `problemdetails.enabled: true`)
- [ ] **C2-2** `src/api/auth.ts` — `signup`/`login` → `TokenResponse {accessToken, tokenType, expiresInSeconds}`
- [ ] **C2-3** `src/auth/token.ts` — 토큰 + **만료 시각** 보관, `isExpired()`.
      **왜 만료를 클라가 아나**: 만료 토큰으로 재접속하면 게이트웨이가 401을 주는데 브라우저는 그걸 볼 수 없어
      무한 재시도에 빠진다(§사전검증) → 만료를 알면 재접속 대신 재로그인으로 보낸다.
      ⚠️ 저장은 **메모리 기본** — localStorage는 XSS 시 토큰 탈취(secure-coding P1/P5)라 기본값으로 두지 않는다
- [ ] **C2-4** `src/LoginForm.tsx` + `App.tsx` 토큰 게이팅(회원가입 전환 포함)
- [ ] **C2-5** 테스트(vitest, **CI 게이트 대상**): 만료 판정 경계 · ProblemDetail 에러 매핑 · 로그인 실패 표시
- [ ] **C2-6** 크래프트 게이트 → PR → 승인 → 머지

### C3. frontend — 페이지 선택 + 에디터 배선 + E2E (frontend PR)

- [ ] **C3-1** `src/api/pages.ts` — 워크스페이스 목록/생성 · 페이지 목록/생성 · 단건 조회(`myRole`)
- [ ] **C3-2** `WorkspaceBootstrap.tsx`(없으면 생성 유도) + `PageList.tsx`(평면 목록 + "새 페이지") — 선택한 `page.id`(UUID)가 곧 room
- [ ] **C3-3** `connection.ts`: **`DEFAULT_ROOM = 'demo'` 제거**. `sanitizeRoom` → `parseRoom(raw): string | null`.
      **왜**: `demo` 폴백은 2a-2 D1에 의해 **무조건 403**이라, 폴백을 남기는 것은 "조용히 실패하는 경로"를 유지하는 것과 같다.
      무효/미지정이면 **연결하지 않고** 페이지 선택 화면을 보여준다
- [ ] **C3-4** `Editor.tsx`: `protocols: [SENTINEL, token]`(SENTINEL 리터럴은 상수 1곳) ·
      `myRole === VIEWER` → Tiptap **`editable: false`** + 읽기 전용 배지 ·
      토큰 부재/만료면 provider를 **아예 생성하지 않는다**(무한 401 재시도 차단)
- [ ] **C3-5** E2E 재작성 — REST 부트스트랩 헬퍼(고유 email signup → login → workspace → page 생성 → 그 UUID로 접속):
      ① editor 2클라 양방향 수렴(기존 테스트 이관) ② **viewer read-only**(공유 PUT으로 viewer 부여 → 쓰기 미반영 + 읽기 정상 수신)
      ③ 무토큰 연결 실패
- [ ] **C3-6** README §E2E + `.env.example` 갱신(사전조건 **2 → 4 프로세스**)
- [ ] **C3-7** 크래프트 게이트 → PR → 승인 → 머지
- ⚠️ C3이 **400줄 초과 시 E2E(C3-5·C3-6)를 별도 PR로 분리**하고 PR 본문에 근거 명시(2a-2 D2 선례)

## 검증

```bash
# C1 (backend) — ⚠️ colima 필수. 없으면 initializationError
cd ../weDocs-backend
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
make test

# C2·C3 (frontend) — CI 게이트와 동일한 두 명령
cd ../weDocs-frontend
npm run build      # tsc --noEmit + vite build
npm run test:unit
```

```bash
# E2E — 로컬 4프로세스 (⚠️ CI 밖: 크로스 레포 실기동이라 워크플로 범위 밖)
docker run --rm -e POSTGRES_DB=wedocs -e POSTGRES_USER=wedocs -e POSTGRES_PASSWORD=wedocs \
  -p 5432:5432 postgres:16-alpine
cd ../weDocs-backend    && make run-doc   # :8081 REST + :50052 gRPC
cd ../weDocs-backend    && make run       # :8080 gateway
cd ../weDocs-crdt-engine && cargo run     # :50051
cd ../weDocs-frontend   && npm run test:e2e
```

**수동 확인(브라우저)**: `npm run dev` → 로그인 → 페이지 생성 → 두 탭 동시 편집 수렴 →
같은 페이지를 다른 계정에 viewer로 공유 → 그 계정에서 **편집 불가(잠김)** + 상대 편집은 실시간 수신.

**관측 역방향 신호**: viewer 경로에서 `ws_write_dropped_total{reason=viewer}`가 **더 이상 증가하지 않아야** 한다
(프론트가 애초에 안 보내므로). 증가하면 `editable: false` 배선이 안 먹은 것 — 무신호 실패 방지용 대조 신호.

**게이트**: 크래프트 표준 6종 `[B]` 체크리스트.
⚠️ 그 룰들은 서비스 레포에서 **자동 로드되지 않는다**(실측 2026-07-28, [dev-log](../dev-logs/2026-07-28-rules-do-not-cross-repo.md))
→ `java-expert`(C1) · `code-reviewer`(C2·C3)를 **에이전트로** 실행.
단 2b에서 병렬 spawn이 2세션 연속 한도 초과로 중단된 전례가 있어 **인라인 직접 실행을 우선** 고려한다.

## 재개 지점 (Resume)

```
마지막 완료 = C1 코드·게이트 완료 → backend PR #19 (커밋 099f90b, 머지 대기)
              브랜치 feature/m2-phase2c-page-role · 154 green · 게이트 [B] 1건 소거
다음        = ① PR #19 CI green 확인 → 머지 승인 요청 → 머지
              ② C2(frontend 인증 셸)
주의        = ① 서비스 레포는 branch+PR+건별 승인 (push·PR 생성·머지 각각)
              ② C1이 C3-4(viewer 잠금)의 선행 — 순서 역전 불가
              ③ 프론트는 myRole이 아니라 **canEdit으로 분기**한다(정책 재구현 금지)
              ④ proto 무변경 → proto-v0.2.0 태그 bump 불요
              ⑤ backend 테스트는 colima env 2개 없으면 initializationError
              ⑥ E2E는 CI에 없다 — 로컬 4프로세스로 직접 확인해야 완료
```

**응답 계약(C2·C3가 소비)** — `GET /api/pages/{pageId}`:
`{ id, workspaceId, parentId, title, position, archived, myRole: "VIEWER"|"EDITOR"|"OWNER", canEdit: boolean }`
목록 `GET /api/workspaces/{id}/pages`는 **역할 없음**(구조 필드만, N+1 회피).

## 범위 밖

- **페이지 목록에 역할 배지** — `list()`는 최대 1,000행이고 `resolve()`는 조상 walk라 **N+1**이 된다.
  역할은 **단건 조회에서만** 노출한다(에디터를 여는 그 순간에만 필요). 목록용 배치 해석은
  **두 번째 해석 경로를 만드는 일**이라 드리프트 위험 > 이득 → 필요해지면 별도 트랙.
- 연결 중 권한 강등 즉시 반영 · 연결 중 토큰 주기 재검증 → 후속(ADR-0014, 재연결 시 반영이 MLP).
- 페이지 rename/move/archive UI · 트리(계층) 렌더링 → M3. 이번엔 **평면 목록 + 생성**까지.
- refresh token → 비범위(TTL 24h, 만료 = 재로그인).
- 권한 E2E 풀세트 → Phase 6. 엔진 저장·복원 → Phase 3/4.
