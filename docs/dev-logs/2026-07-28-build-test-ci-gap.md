---
date: 2026-07-28
category: meta
tier: 2
importance: critical
status: resolved
tags: [ci, github-actions, buf, testcontainers, gate, proto-tag]
related:
  - plans/2026-07-28-build-test-ci-gap.md
  - dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md
  - adr/0010-proto-distribution-buf-git-input.md
---

# 빌드·테스트 CI 갭 — 초록이 "컴파일된다"는 뜻이 아니었다

## 무엇이 문제였나

M2 Phase 2b 머지 직후 발견. 서비스 3레포에 **빌드·테스트 CI가 없었다**.

| 레포 | 있던 워크플로 | 빌드·테스트 |
|---|---|---|
| controller | `proto-ci.yml` + `security-scan.yml` | ✅ (proto가 이 레포 산출물) |
| backend | `dependency-submission` + `security-scan` | ❌ |
| crdt-engine | `security-scan` | ❌ |
| frontend | `security-scan` | ❌ |

`cargo test`·Gradle·vitest가 **CI에서 한 번도 돌지 않았다**. PR 체크가 전부 초록이어도 그건 "시크릿·취약점 스캔 통과"일 뿐이라, **빌드를 깨는 PR도 all-green으로 보였다**. 직전 2b PR의 "30 tests green"조차 전부 로컬 실행이었다.

2026-07-17 gitleaks 사고("게이트가 red를 못 내면 배선 안 한 것보다 나쁘다")와 같은 계열인데, 여기선 게이트가 **아예 없었다**.

## 결과

3 PR 전부 머지, 각 레포 main 트리거까지 green 확인.

| 레포 | PR | squash | 실행 시간 |
|---|---|---|---|
| crdt-engine | [#12](https://github.com/ressKim-io/weDocs-crdt-engine/pull/12) | `fab982d` | 1m58s → **40s**(캐시) |
| backend | [#18](https://github.com/ressKim-io/weDocs-backend/pull/18) | `181b8de` | ~2m (148 테스트 + Postgres 컨테이너) |
| frontend | [#4](https://github.com/ressKim-io/weDocs-frontend/pull/4) | `ff2e077` | 수십 초 |

## 교훈

### 1. 완료 조건은 "워크플로 파일 존재"가 아니라 "실패를 잡는다"

각 레포에서 **의도적 실패를 주입해 red를 확인**하고 되돌렸다. 이걸 안 했으면 "게이트는 있는데 아무것도 못 잡는" 상태를 구분할 수 없다.

| 레포 | 주입 | 실패 지점 | 증명한 것 |
|---|---|---|---|
| engine | fmt 위반 | `cargo fmt --check` | fmt가 **마지막 단계** → 앞의 build·test·clippy가 전부 실행·통과했다는 것까지 동시 증명 |
| engine | 테스트 단언 뒤집기 | `cargo test --all-targets` | 테스트가 머지를 막는다 |
| backend | Testcontainers 테스트 단언 | `./gradlew build` | **`148 tests completed, 1 failed`** ← 결정적 |
| frontend | 단위 테스트 단언 | `npm run test:unit` | test가 마지막 → build·타입체크 실행·통과 증명 |
| frontend | 타입 에러 | `npm run build` | `tsc --noEmit`이 실제 게이트 |

**설계 요령**: 체인의 **마지막 단계**에 실패를 주입하면 "앞 단계가 전부 실행됐다"까지 한 번에 증명된다. 단계마다 주입하면 fail-fast 때문에 실행 수가 선형으로 늘어난다.

**`148 tests completed`가 왜 결정적인가**: "Docker 없으면 조용히 skip"은 Testcontainers 프로젝트의 흔한 실패 양식이다. 그러면 초록이 다시 거짓말이 된다. 단순 red가 아니라 **테스트 수와 실패 지점(파일:라인)까지 확인**해야 "엉뚱한 이유의 red"를 배제할 수 있다.

### 2. gitignored 생성물에 의존하는 빌드는 CI에서 반드시 깨진다 — 레포마다 확인하라

engine은 `proto/`(buf export), backend는 Java 스텁(`buf generate` → `build/` 아래). **양쪽 다 gitignored이고, 양쪽 다 로컬 형제 경로(`../weDocs-controller/proto`)를 기본 input으로 쓴다.**

engine은 이걸 예상해 처음부터 배선했는데, **backend는 "proto vendoring이 없다"고 단정**해서 첫 실행이 20 컴파일 에러로 깨졌다. 확인하지 않고 단정한 대가다. 두 레포의 구조가 같았다.

처방은 설정 파일을 고치는 게 아니라 **CLI 인자로 input만 오버라이드**:
```
buf generate 'https://github.com/…/weDocs-controller.git#subdir=proto,ref=proto-v0.2.0'
```
`buf.gen.yaml`의 `plugins:`(출력 경로·protobuf/grpc 버전)는 그대로 쓰이고 `inputs:`만 덮인다 — 로컬 개발은 형제 경로를 유지해 빠르고(0.95s vs 원격), CI만 태그를 핀한다. **배선 전 로컬에서 실증**했다(원격 input → 72 스텁 → `compileJava` 통과).

### 3. 문서가 가리키는 태그가 실재하지 않았다

CLAUDE.md·plan이 "현 태그 `proto-v0.2.0`·로컬"이라 적었으나 **로컬·원격 어디에도 없었다**(원격 = `proto-v0.1.0`뿐). v0.2.0 *내용*은 main에 커밋돼 있었지만 태그는 만들어진 적이 없다.

- CI가 원격 ref를 핀해야 해서 **드러났다** — 안 그랬으면 Phase 3(엔진이 `LoadSnapshot` 사용)에서 터졌을 것이다.
- 태그는 main HEAD가 아니라 **proto의 마지막 변경 커밋 `99213c3`** 에 달았다(더 정확).
- 같은 stale ref가 **engine `Makefile`과 backend `buf.gen.yaml` 주석 양쪽**에 `proto-v0.1.0`으로 남아 있었다 — 한 곳의 드리프트가 다운스트림 주석으로 복제돼 있던 것. 셋 다 갱신.

### 4. 액션 버전은 추측하면 3건 중 3건 틀린다

전부 WebFetch로 확인했고, 추측했으면 틀렸을 것들:

| 추측했을 값 | 실제 |
|---|---|
| `bufbuild/buf-setup-action` | **deprecated** → `buf-action@v1` |
| `buf-action@v1` 그냥 사용 | **`setup_only: true` 필수** — 미지정 시 `lint`/`format`/`breaking`이 **기본 true**로 돌아 proto 원본 없는 레포에서 오작동 |
| `dtolnay/rust-toolchain@v1` | **@v1 없음** — rev 자체가 툴체인(`@stable`) |
| `Swatinem/rust-cache` 아무데나 | **툴체인 step 뒤 필수**(rustc가 캐시 키) |
| `actions/setup-java@v6` | v6는 개발 중·**비권장**, v5가 stable |

Node 버전도 추측 대신 **설치된 툴체인의 `engines` 교집합**으로 도출했다 — vite 8.1.0 `^20.19.0 || >=22.12.0` ∩ vitest 4.1.9 `^20.0.0 || ^22.0.0 || >=24.0.0` → 24(LTS). 레포에 `.nvmrc`·`engines` 핀이 없어서 근거를 워크플로 주석에 남겼다.

### 5. 크래프트 게이트를 서브에이전트로 병렬 spawn하면 세션 한도를 태운다

2b 게이트 리뷰에서 `rust-expert`+`code-reviewer`를 병렬로 띄웠다가 **2세션 연속 한도 초과로 중단**됐다(각자 크래프트 표준 6종 + 엔진 소스를 콜드 스타트로 재적재 = 예산 2배). 3회차는 **인라인 직접 실행**으로 전환해 완주했고 BLOCKING 0 + Major 2 + Minor 4를 냈다.

**판단**: 단일 레포·중간 규모 diff의 크래프트 게이트는 인라인이 비용·완주율 모두 우위다. 서브에이전트는 진짜 병렬 fan-out(10+ 파일 탐색)에 쓴다.

## 남은 것

- **프론트 E2E의 CI 실행** — engine + ws-gateway 실기동이 필요한 크로스 레포 통합 테스트라 사실상 M5 배포 파이프라인 선행 작업. 제외 사유를 워크플로 주석·README에 명시.
- **커버리지 게이트**(80%/95%, `testing.md`)·**criterion 벤치 회귀 가드**(M1.5 `--save-baseline`) → 후속. 이번 목표는 "깨지면 red"였다.
- **다운스트림 자동 트리거**(controller proto 변경 → 서비스 레포 `repository_dispatch`) → `proto-ci.yml`의 기존 TODO(M5).
- `actions/setup-node` v7 bump 판단(베이스라인 green 확인됨).
