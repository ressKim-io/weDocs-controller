# ADR-0014 — 인증/인가 경계 (JWT 발급=doc-service, 검증=gateway)

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: [PRD §4.4](../prd/4-data-and-permission-model.md) (D-5) · SDD §6.2·§8 · [plan-audit T3-2](../plans/2026-06-30-plan-audit-improvements.md) (M2F-05/SEC-01) · [ADR-0011](0011-engine-sync-fanout-bridge.md) · 가드레일 4
- 범위: M2 인증·연결시 인가. 연결 중 권한 강등 즉시반영·인증 서비스 분리 = 2차/후속(범위 밖).

## 맥락

M1은 인증이 없다 — 누구나 어떤 room이든 접속. M2 = JWT 인증 + 페이지별 권한(viewer/editor, 상속). 정해야 할 것: ① JWT 발급/검증 위치, ② WS 핸드셰이크에 토큰을 어떻게 싣나(브라우저 `WebSocket` API는 커스텀 헤더 불가), ③ viewer write를 어디서 차단하나, ④ 인증/인가 실패 시 close code.

제약: 가드레일 4(서비스 간 gRPC + OTel). 인증 서비스는 M2에서 **분리하지 않고 doc-service 내장**(SDD §15, 분리는 후속).

## 결정

1. **발급 = doc-service**(REST 로그인 → JWT). **검증**: WS 경로는 **gateway**(핸드셰이크), REST 경로는 doc-service(self). 게이트웨이↔doc-service는 Istio ztunnel mTLS.
2. **WS 토큰 전달 = `Sec-WebSocket-Protocol` 서브프로토콜** — 브라우저 `WebSocket`이 헤더 커스텀 불가하므로 subprotocol 값으로 토큰 전달(서버가 echo). query param·첫 메시지 대비 우수(아래 비교).
3. **연결시 인가**: gateway → `DocService.CheckPermission(user_id, page_id)` → effective level(상속 해석은 doc-service). `none` → 연결 거부.
   - **proto에 토큰 필드 미추가** — gateway가 JWT를 검증해 `user_id`를 추출·전달. doc-service는 `user_id`만 받음(proto 최소화, mTLS로 gateway 신뢰).
4. **viewer write 차단 = gateway 1차 + 엔진 방어**(D-5): gateway가 viewer 스트림의 `client→server update`를 **drop**(server→client만 통과). **엔진 방어 = Sync 스트림 open 시 gateway가 `role`을 gRPC 메타데이터로 전달**(doc-id와 동일 채널, [ADR-0011](0011-engine-sync-fanout-bridge.md) 결정 4) → 엔진이 viewer 스트림에 도착한 write 프레임을 거부. **proto 변경 불요**(메타데이터 out-of-band). 클라이언트 read-only 플래그만 신뢰 금지(보안).
5. **실패 close code**: 인증 실패(토큰 없음/만료/무효) = **4401**, 인가 실패(권한 없음) = **4403** (RFC 6455 application range 4000–4999, HTTP 401/403 미러링). 표준 정책위반은 1008 병용.
6. **JWT TTL** = `T`(초기 제안 **24h** — 예상 편집 세션보다 길게). 연결 중 만료는 **재접속 시 재검증**으로 대응(MLP — 권한 강등 비전파와 동일 정책). 연결 중 토큰 주기 재검증은 후속.

매핑: PRD §4.4 시퀀스(`connect(pageId, JWT)` → `CheckPermission` → viewer=read-only / editor=양방향 / none=거부)에 그대로 끼워진다.

## 대안 비교

### 축 1 — JWT 검증 위치
| 방안 | WS 차단 시점 | 게이트웨이 책임 | 판정 |
|---|---|---|---|
| **발급=doc-service, WS검증=gateway** (채택) | 핸드셰이크(빠름) | 토큰 검증+user_id 추출 | ✅ 엔진 도달 전 차단, doc-service는 user_id만 |
| 전부 doc-service 검증(gateway는 통과만) | 연결 후 CheckPermission까지 지연 | 얇음 | △ 무효 토큰도 일단 연결, 자원 낭비 |
| 엔진 검증 | 엔진 도달 후 | — | ❌ 엔진=내용 권위, 인증은 책임 밖(가드레일 5) |

### 축 2 — WS 토큰 전달
| 방안 | 로그 유출 | 핸드셰이크 차단 | 판정 |
|---|---|---|---|
| **`Sec-WebSocket-Protocol`** (채택) | ✅ 헤더(access log 미기록) | ✅ 핸드셰이크 | ✅ 브라우저 헤더 커스텀 불가 우회 표준 |
| query param(`?token=`) | ❌ access log·Referer 유출 | ✅ | ❌ 보안 |
| 첫 WS 메시지 | ✅ | ❌ 연결 수립 후 검사 | ❌ 무인증 연결 잠깐 허용 |

### 축 3 — viewer write 차단
| 방안 | 보안 | 판정 |
|---|---|---|
| **gateway 1차 drop + 엔진 방어** (채택) | ✅ 다층 | ✅ |
| gateway만 | △ 단일 지점 | △ |
| 클라이언트 read-only 플래그 | ❌ 우회 가능 | ❌ (D-5 명시) |

## 결과

- proto-v0.2.0: `CheckPermissionRequest`는 `{doc_id, user_id}` 유지(토큰 필드 불요) → 변경 최소.
- gateway가 인증 게이트(가드레일: 엔진 도달 전 차단). doc-service = JWT 발급 + 권한 해석(상속) 단독 소유.
- M2 Phase 2(인증/인가)·Phase 6(권한 E2E) 검증 경로 확정.

## 트레이드오프 (인정)

- **연결시 1회 검사** → 연결 중 권한 강등 즉시 미반영. MLP는 **재연결 시 반영**(PRD §5). 즉시 무효화는 후속(권한 변경 → 엔진 스트림 종료 신호).
- **gateway가 user_id를 신뢰** → gateway↔doc-service mTLS(ztunnel) 전제. 메시 밖 호출 금지.
- **`Sec-WebSocket-Protocol`에 토큰** → 서브프로토콜 협상 헤더에 노출(TLS 하 OK). 서버가 선택 subprotocol을 echo해야 핸드셰이크 성립.
- **인증 doc-service 내장** → 후속 인증 서비스 분리 시 발급 로직 이전 비용(SDD §15, 수용).
