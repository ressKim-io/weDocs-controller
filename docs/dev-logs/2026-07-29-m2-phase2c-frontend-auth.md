---
date: 2026-07-29
category: decision
tier: 2
importance: major
status: resolved
tags: [frontend, auth, websocket, craft-gate, e2e, phase2]
related:
  - plans/2026-07-28-m2-phase2c-frontend-auth.md
  - plans/2026-07-19-m2-phase2-auth-authz.md
  - adr/0014-auth-authz-boundary.md
  - dev-logs/2026-07-28-rules-do-not-cross-repo.md
---

# M2 Phase 2c — 프론트엔드 인증 배선에서 배운 것

Phase 2(인증/인가)의 마지막 조각. backend 1 PR + frontend 4 PR로 끝났고, 이로써
**로그인 → 워크스페이스 → 페이지 → 두 클라이언트 수렴**이 실기동으로 확인된다.
여기 남기는 것은 진척이 아니라 **재발할 함정**이다(진척 = `status/history.md`).

## 1. 폴백은 "조용히 실패하는 경로"를 유지한다

`connection.ts`에는 `DEFAULT_ROOM = 'demo'`가 있었다. 무효한 `?room=`이면 `demo`로 폴백한다 —
M1에서는 합리적이었다. 그런데 2a-2가 인가를 붙이면서 **게이트웨이는 비UUID `doc_id`를
`CheckPermission` 왕복도 없이 403으로 끊는다.** 즉 폴백 경로는 **무조건 실패**로 바뀌어 있었다.

실측(4프로세스 실기동):

| 시나리오 | 결과 |
|---|---|
| 토큰 + 페이지 UUID | **OPEN**, negotiated=`wedocs.sync.v1` |
| 무토큰 / SENTINEL 없이 토큰만 | **401** / **401** |
| **비UUID room(`demo`)** | **403** |
| 권한 없는 페이지 UUID | **403** |

**교훈**: 인가를 새로 붙였으면 **기존 기본값·폴백이 그 관문을 통과하는지** 확인한다.
폴백은 실패를 없애지 않고 **실패 지점을 옮겨 숨긴다**. 처방은 폴백 제거 + 실패를 값으로 반환
(`sanitizeRoom(raw): string` → `parseRoom(raw): string | null`) — 호출자가 "연결하지 않는다"를 고를 수 있게.

## 2. 브라우저는 WS 실패의 상태 코드를 볼 수 없다 → 연결 **전에** 막는 것이 유일한 대책

위 401/403은 **Node `ws`에서만 관측된다.** 브라우저 `WebSocket` API는 실패를 `code 1006`으로만 주고,
y-websocket은 그것을 상한 2500ms backoff **무한 재접속**으로 흡수한다. 사용자에게는 원인 없는
"연결 중"만 보인다.

그래서 두 가지를 클라이언트가 **미리** 판단한다:
- **토큰 만료** — `token.ts`가 만료 시각을 들고 있다가 만료면 `getToken()`이 null을 준다
- **room 형식** — `parseRoom`이 UUID를 요구한다(엔진 `DocId` 문자집합 규칙보다 **엄격** → false-accept 없음)

둘 중 하나라도 어긋나면 **`WebsocketProvider`를 생성하지 않는다.**

**교훈**: 관측할 수 없는 실패는 **발생시키지 않는 것**이 유일한 처방이다.
"실패하면 알려주자"는 그 실패를 볼 수 있을 때만 성립한다.

## 3. 서버 정책을 클라이언트가 재유도하지 않는다 — `canEdit` 단일 출처

C1이 `GET /api/pages/{id}`에 `myRole`과 `canEdit`을 **둘 다** 내보낸 것이 여기서 값을 했다.
역할만 줬다면 프론트가 `role === 'EDITOR' || role === 'OWNER'`를 쓸 수밖에 없고, 그건
**서버 정책의 복제**다 — 역할이 하나 추가되는 순간 두 곳이 갈라진다.

프론트는 `canEdit`으로만 분기하고 `myRole`은 **배지 표시용**으로만 쓴다. 이 의도를 테스트로 고정했다:
`myRole: 'EDITOR'`인데 `canEdit: false`인 응답도 **잠근다**.

**교훈**: "파생 가능한 값"을 계약에 넣는 것이 중복이 아니라 **드리프트 방지**일 때가 있다.
기준은 "그 파생 규칙이 누구의 정책인가"다.

## 4. 크래프트 표준 [B]는 프론트엔드에도 그대로 발화한다

C2에서 3건(layering P7 `src/api/` · error-handling P4 cause 유실 · secure-coding P1 무검증 캐스트),
C3에서 자체 발견 3건(언마운트 후 상태 갱신 순서 · `return` 뒤 함수 선언 · README가 거짓이 됨).

특히 **layering P7**은 "Java 패키지 규칙"으로 읽히지만 `src/api/`·`src/service/` 같은 프론트 관행에
정확히 발화한다. 이 레포에서 `src/<layer>/`를 새로 만들지 않는다 — feature 평면 + `common/<관심사>/`.

⚠️ 그 룰들은 서비스 레포에서 **자동 로드되지 않는다**([dev-log](2026-07-28-rules-do-not-cross-repo.md)).
2c는 전 PR에서 **체크리스트를 직접 읽어 인라인 실행**했다(에이전트 spawn 한도 전례 때문).

## 5. E2E는 자기 사전조건을 스스로 만들어야 권한 케이스를 검증할 수 있다

토큰을 환경변수로 주입받는 방식을 채택하지 않았다(plan E3). 그 방식은 (a) 사람이 매번 발급해야 하고
(b) **그 계정의 권한에 따라 결과가 달라져 viewer 케이스를 아예 검증할 수 없다.**

부트스트랩이 실행마다 고유 이메일로 owner·viewer 계정 + 워크스페이스 + 페이지를 만들면
editor 수렴 / viewer read-only / 미인증 거절 **세 경로를 한 번에** 재현한다.
`userId`는 JWT를 디코드하지 않고 **signup 응답**에서 얻는다 — 테스트가 토큰 내부 구조에 의존하지 않게.

대가는 사전조건이 **2 → 4프로세스**(postgres·doc-service·gateway·engine)로 늘어난 것이고,
그래서 이 E2E는 여전히 **CI 밖**이다.

## 6. 메트릭을 대조 신호로 쓴다 (무신호 실패 방지)

검증 중 게이트웨이 메트릭이 시나리오와 **정확히 일치**했다:

```
ws_handshake_total{result="ok"}           4.0
ws_handshake_total{result="authn_fail"}   2.0
ws_handshake_total{result="authz_denied"} 2.0
ws_write_dropped_total{reason="viewer"}   2.0
```

`ws_write_dropped_total{reason=viewer}`는 **UI 잠금을 우회해 일부러 보냈을 때** 올라간 값이다.
실제 브라우저 사용에서는 프론트가 애초에 보내지 않으므로 이 카운터는 **평평해야** 정상이고,
**증가하면 `editable: false` 배선이 풀린 것**이다.

**교훈**: "동작한다"의 증거만 모으지 말고 **"고장 나면 움직일 신호"**를 함께 정해 둔다.

## 남은 것 (이월)

- 서버 `WorkspaceService.listMine`에 **조회 상한 없음**(secure-coding P2) — 형제인 `PageTreeService.list`는
  `MAX_PAGE_LIST`(1,000)로 자른다. 클라 절단은 서버 갭을 감추므로 채택하지 않았다 → 다음 backend PR 동승.
- **브라우저 클릭 검증 미수행** — Chrome 확장 미연결 환경이었다. 화면 로직은 jsdom 컴포넌트 테스트로,
  연결·권한 경로는 위 실측으로 덮었지만 "사람이 실제로 클릭하는 경로"는 아직 한 번도 안 지나갔다.
