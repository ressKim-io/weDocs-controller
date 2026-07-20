---
date: 2026-07-20
category: troubleshoot
tier: 2
importance: major
status: resolved
tags: [virtual-threads, jep-491, grpc, pinning, jfr, ws-gateway, measurement]
related:
  - plans/2026-07-19-m2-phase2-auth-authz.md
  - dev-logs/2026-07-19-m2-gateway-authn-observability.md
  - adr/0021-ws-handshake-auth-failure-observability.md
  - adr/0014-auth-authz-boundary.md
---

# VT pinning 실측 — 맞는 결론, 틀린 근거 (gRPC blocking stub)

## Context

M2 Phase 2a-1이 남긴 이월 검증점: **"VT pinning 재검 = 2a-2(CheckPermission 블로킹 gRPC)"**.
2a-2는 WS 핸드셰이크(가상 스레드) 안에서 doc-service로 **블로킹 unary gRPC**를 호출한다. 블로킹 호출이
캐리어 스레드를 고정하면 가상 스레드의 이점이 사라지고, 핸드셰이크 처리량이 캐리어 풀 크기에 묶인다
(가드레일 3의 정신 — 게이트웨이는 VT를 막는 것을 도입하지 않는다).

## 무엇을 했나

### 1) 측정 (JFR)

`jdk.VirtualThreadPinned`는 기본/profile 설정에서 **20ms 임계**로 기록된다. 전체 ws-gateway 테스트를
JFR과 함께 돌렸다 — deadline(300ms)을 초과시키는 `slowDocService_hitsDeadlineAndRejects` 포함.

```bash
# init script로 test JVM에 JFR 부착
jvmArgs "-XX:StartFlightRecording=name=vt,settings=profile,filename=<path>/vt-pinning.jfr,dumponexit=true"
./gradlew :ws-gateway:test --rerun-tasks -I <init>.gradle

jfr summary vt-pinning.jfr | grep VirtualThreadPinned
#  jdk.VirtualThreadPinned    0    0
```

### 2) 공허한 green 배제

`jdk.VirtualThreadPinned`가 0인데 `jdk.VirtualThreadStart`도 0이었다. **"pinning이 없다"와 "가상 스레드가
아예 안 쓰였다"는 겉으로 똑같이 0건**이다. (Start/End는 기본 비활성이라 0이 정상이지만, 그것만으로는
구분되지 않는다.) 인터셉터에 일회성 프로브를 넣어 확인:

```
VT-PROBE thread=VirtualThread[#59,tomcat-handler-0]/runnable@ForkJoinPool-1-worker-1 virtual=true
```

→ 핸드셰이크가 실제로 가상 스레드에서 실행됨을 확인한 뒤에야 0건이 의미를 갖는다.

## 근본 원인 — 내 최초 근거가 틀렸다

착수 시점에 나는 pinning 안전성을 **"Java 25이므로 JEP 491(synchronized 미고정)"** 으로 설명했다.
게이트 리뷰(java-expert)가 `grpc-stub-1.82.1.jar`를 디컴파일해 교정했다:

| | 최초 근거(틀림) | 실제 근거(검증됨) |
|---|---|---|
| 왜 안전한가 | Java 25의 JEP 491이 `synchronized` 고정을 없앰 | grpc-java blocking stub은 `ThreadlessExecutor.waitAndDrain()` → **`LockSupport.park`** 로 대기 |
| 버전 의존성 | JDK 24+ 필요 | **JDK 버전 무관** — `park`는 원래부터 가상 스레드를 언마운트 |
| 무엇에 의존하나 | JDK | **grpc-java 내부 구현(현재 1.82.1 고정)** |

JEP 491이 다루는 것은 `synchronized`/`Object.wait()` 경로다. 이 호출은 애초에 그 경로를 타지 않는다.
**결론(pinning 없음)은 맞았지만 이유가 틀렸고, 이유가 틀리면 재검증 조건도 틀린다** — "JDK만 유지하면
안전"이 아니라 **"grpc-java를 크게 올리거나 호출 방식(blockingV2 등)을 바꾸면 재측정"** 이 맞다.

## 조치

- `DocServiceClient.checkPermission` 호출부에 정정된 근거 + 재측정 트리거를 주석으로 명시.
  라이브러리 내부에 걸린 사실은 코드를 읽어서는 보이지 않고, 이를 지키는 회귀 테스트도 없다.
- 이 dev-log에 JFR 명령/결과를 기록 — "0건"이 레포만 보고 검증 가능해야 한다.

## 교훈

1. **맞는 결론이 검증을 통과시키지 못한다.** 근거가 틀리면 결론이 우연히 맞아도 재검증 조건·유효 범위가
   함께 틀어진다. 이번엔 "JDK 업그레이드 감시"라는 엉뚱한 가드를 세울 뻔했다.
2. **0건짜리 측정은 공허함부터 배제한다.** 억제와 무력화가 같은 모습이라는 점은
   [gitleaks 대조군 사례](2026-07-17-gitleaks-fingerprint-squash-trap.md)와 같은 구조다 — 그때는
   "진짜 키를 넣어 룰 생존 증명", 이번은 "`isVirtual()` 프로브로 VT 사용 증명".
3. **서드파티 내부에 걸린 안전성은 주석 없이는 유실된다.** 측정은 그 시점의 스냅샷이고, 다음 사람은
   측정했다는 사실조차 모른다. 근거·버전·재측정 트리거를 호출부에 남긴다.

## 참고

- 측정 대상 코드: `ws-gateway` `DocServiceClient`(blocking stub + `withDeadlineAfter`), Phase 2a-2
- 검증 도구: JFR `jdk.VirtualThreadPinned`(임계 20ms) + 일회성 `isVirtual()` 프로브
- 확정 사실(리뷰 디컴파일): `io.grpc:grpc-stub:1.82.1` `ClientCalls.blockingUnaryCall` → `ThreadlessExecutor` → `LockSupport.park/unpark`
