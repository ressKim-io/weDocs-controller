---
date: 2026-07-28
slug: build-test-ci-gap
status: planned
related:
  - plans/2026-07-19-m2-phase2-auth-authz.md
  - plans/2026-07-03-security-quality-standards.md
  - adr/0010-proto-distribution-buf-git-input.md
  - dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md
---

# 빌드·테스트 CI 갭 정합 (서비스 3레포)

> M2 Phase 2b 머지 직후 발견. Phase 2c 착수 **전** 실행 권고.
> 서비스 레포(backend/crdt-engine/frontend) = branch+PR+건별 승인. controller만 main 직접.

## Context

**왜**: 서비스 3레포에 **빌드·테스트 CI가 없다.** `.github/workflows/` 실사 결과:

| 레포 | 워크플로 | 빌드·테스트 게이트 |
|---|---|---|
| controller | `proto-ci.yml`(buf lint/breaking) + `security-scan.yml` | ✅ 있음(proto가 이 레포의 산출물) |
| backend | `dependency-submission.yml` + `security-scan.yml` | ❌ **없음** |
| crdt-engine | `security-scan.yml` | ❌ **없음** |
| frontend | `security-scan.yml` | ❌ **없음** |

즉 `cargo test`·Gradle 테스트·vitest가 **CI에서 한 번도 돌지 않는다**. 결과:

- **빌드를 깨는 PR도 all-green으로 보인다.** 초록 체크는 "시크릿·취약점 스캔 통과"일 뿐 "컴파일된다"는 증명이 아니다.
- 2b PR #11의 "30 tests green"도 **전부 로컬 실행**이었다. 리뷰어가 초록만 보고 머지하면 검증 없이 머지된다.
- 2026-07-17 gitleaks 사고의 교훈("게이트가 red를 못 내면 배선 안 한 것보다 나쁘다")과 **같은 계열** — 여기선 게이트가 아예 없다.
- 누적 자산이 크다: backend 148+ / engine 30 / frontend 단위+E2E. 로컬에서만 도는 테스트는 회귀 방지력이 세션 의존이다.

**지금인 이유**: Phase 3(엔진→doc-service `SaveSnapshot` push)부터는 **레포 간 런타임 결합**이 생긴다. 로컬 검증만으로는 회귀를 못 잡는 구간에 들어가기 전에 게이트를 세운다.

### 확인된 제약 (2026-07-28 실사)

- **crdt-engine**: `proto/`는 gitignored. `Makefile`의 `proto-sync`가 로컬 경로(`CONTROLLER ?= ../weDocs-controller/proto`)를 기본값으로 쓰는데 **CI엔 형제 디렉토리가 없다** → 원격 git input(ADR-0010) 필요. ⚠️ **원격 태그는 `proto-v0.1.0`뿐**(아래 D1).
- **backend**: Java 25 toolchain, 모듈 2개(`ws-gateway`·`doc-service`). doc-service 테스트 = Testcontainers(Postgres) → **Docker 필요**(GH Actions `ubuntu-latest`엔 존재, 단 첫 실행에서 실증 필요). ws-gateway는 in-process fake라 불요.
- **frontend**: `npm run test:e2e`(= `vitest run`)가 **단위와 E2E를 함께** 돌린다. `test/connection.test.ts`=순수 단위 / `test/e2e/convergence.e2e.test.ts`=**engine+gateway 실기동 필요**(`ws://localhost:8080`) → 스크립트 분리 없이는 CI에서 E2E가 타임아웃으로 실패한다.

### 발견된 드리프트 — proto 태그 (선결)

CLAUDE.md·plan은 "현 태그 `proto-v0.2.0`·로컬"이라 적었으나 **로컬·원격 어디에도 없다**:
```
git tag -l 'proto-*'            → proto-v0.1.0
git ls-remote --tags origin     → proto-v0.1.0 (만)
```
v0.2.0 *내용*(`LoadSnapshot`·`DocMeta` page-tree)은 main에 커밋돼 있다. v0.1.0 대비 변경은 **`doc/doc.proto`뿐**(+16/-1) — `crdt`/`common`은 무변경이라 그것만 컴파일하는 엔진은 v0.1.0으로도 동일 결과가 나온다. 하지만 Phase 3에서 엔진이 `LoadSnapshot`을 쓰기 시작하면 즉시 깨진다.

### 확정 결정 (사용자, 2026-07-28)

| # | 결정 | 근거 |
|---|---|---|
| D1 | **`proto-v0.2.0` 태그 생성 + push 후 CI가 그것을 핀** | ADR-0010의 태그 핀 원칙에 정합. 재현 가능한 빌드(controller main 변경이 엔진 CI를 예고 없이 깨지 않음). 발견된 태그 드리프트를 동시 해소. CLAUDE.md의 "push는 서비스 레포 착수 시 승인"이 가리키던 **그 시점이 지금** |
| D2 | **범위 = 3레포 빌드·테스트 CI만** (레포당 1 PR, 총 3) | 프론트 E2E는 다른 레포 서비스 2개 기동이 필요해 사실상 M5 배포 파이프라인 선행 작업 — 스코프 분리. 커버리지 게이트·벤치 회귀 가드도 범위 밖 |

## Blast Radius

| 항목 | 내용 |
|---|---|
| 직접 변경(controller) | `proto-v0.2.0` 태그 생성·push, 이 plan, CLAUDE.md 태그 서술 정정 |
| 직접 변경(crdt-engine) | `.github/workflows/ci.yml` 신설. `Makefile` proto-sync 주석의 ref 갱신(v0.1.0→v0.2.0) |
| 직접 변경(backend) | `.github/workflows/ci.yml` 신설 |
| 직접 변경(frontend) | `.github/workflows/ci.yml` 신설 + `package.json` 스크립트 분리(`test:unit` 신설, `test:e2e`는 E2E만) |
| 간접 영향 | **기존 PR 흐름에 새 필수 체크가 붙는다** — 지금까지 초록이던 상태가 red로 드러날 수 있다(그게 목적). backend Testcontainers가 CI에서 실패하면 doc-service 테스트 분리 필요 |
| 롤백 | 각 PR revert. 태그는 `git push --delete origin proto-v0.2.0`(단 다운스트림 ref가 물기 전에만) |
| 검증 | 아래 §검증 — **의도적 실패 주입으로 red 확인**이 완료 조건 |
| 다운타임 | 없음(CI만) |

## 실행 체크리스트

### 0. 선결 — proto 태그 정합 ✅ (controller, main 직접 + push 승인)
- [x] `proto-v0.2.0` annotated 태그 생성 → push 승인 → push. **대상 = `99213c3`**("feat(proto): doc-service M2 계약 — LoadSnapshot + page-tree 메타 (v0.2.0)", proto/의 마지막 변경 커밋이라 main HEAD보다 정확). 원격 확인: `refs/tags/proto-v0.2.0^{}` → `99213c3` ✅
- [x] **CI 명령 형태를 로컬에서 실증**(YAML 쓰기 전): ① 로컬 `.git#subdir=proto,ref=proto-v0.2.0` export → 4 proto ② **원격 URL** export → 동일 결과·0.95s·인증 불요(public repo) ③ 그 산출물로 `cargo build` + `cargo test --all-targets` → **30 green**. Makefile의 디렉토리 입력과 트리 레이아웃 동일.
- [ ] CLAUDE.md의 "현 태그 `proto-v0.2.0`·로컬" 서술 정정(원격 존재로)

### 1. 신규 도구 spec 사전 검증 ✅ (MANDATORY, `workflow.md` §신규 도구 — 전부 WebFetch 2026-07-28)

| 도구 | 검증 결과 | 출처 |
|---|---|---|
| buf action | ⚠️ **`buf-setup-action`은 deprecated** → `bufbuild/buf-action@v1` 사용. **`setup_only: true` 필수** — 미지정 시 PR에서 `lint`/`format`/`breaking`이 **기본 true**로 돌아 proto 원본이 없는 엔진 레포에서 오작동한다(`action.yml` inputs 확인) | [buf-setup(deprecation)](https://github.com/marketplace/actions/buf-setup) · [buf-action action.yml](https://raw.githubusercontent.com/bufbuild/buf-action/main/action.yml) |
| `actions/setup-java` | **v5가 현행 stable**(v5.6.0, 2026-07-16). ⚠️ v6는 `main`에서 개발 중·**프로덕션 비권장**. `temurin` + `java-version: '25'` 지원 확인 | [releases](https://github.com/actions/setup-java/releases) |
| `dtolnay/rust-toolchain` | ⚠️ **@v1 태그 방식이 아니다** — `@stable`/`@1.89.0` 같은 **rev 자체가 툴체인 선택**. 컴포넌트는 `with: components: clippy, rustfmt` | [repo](https://github.com/dtolnay/rust-toolchain) |
| `Swatinem/rust-cache` | **v2**. ⚠️ **툴체인 설정 step 뒤에 배치 필수** — rustc 버전을 캐시 키로 쓰기 때문 | [repo](https://github.com/Swatinem/rust-cache) |
| `gradle/actions/setup-gradle` | **v6**(v6.2.0) | [releases](https://github.com/gradle/actions/releases) |
| `actions/setup-node` | v7이 2026-07-14 릴리스(ESM 마이그레이션)이나 **2주밖에 안 됐다** → 베이스라인은 **v6**(v6.5.0)로 세우고 green 확인 후 bump 판단(근거 있는 보수 선택, 워크플로 주석에 기록) | [releases](https://github.com/actions/setup-node/releases) |

- 엔진은 `protoc` 설치 불요 — `build.rs`가 `protoc-bin-vendored`로 주입(기존 구현).

### 2. PR① crdt-engine `ci.yml` (🦀 게이트)
- [ ] buf 설치 → `buf export '…#subdir=proto,ref=proto-v0.2.0' -o proto` → `cargo build`
- [ ] `cargo test --all-targets` / `cargo clippy --all-targets -- -D warnings` / `cargo fmt --check`
- [ ] 트리거 = `pull_request` + `push: [main]`. rust-cache로 빌드 시간 단축
- [ ] ⚠️ `Makefile`의 canonical 주석 ref를 `proto-v0.2.0`으로 갱신(코드-문서 정합)

### 3. PR② backend `ci.yml` (☕ 게이트)
- [ ] Java 25 setup + Gradle 캐시 → `./gradlew build`(= compile + test, 두 모듈)
- [ ] **Testcontainers 실증**: doc-service 테스트가 CI Docker에서 실제로 뜨는지 첫 실행으로 확인. 실패 시 대안 = 서비스 컨테이너(`services: postgres`) 또는 doc-service 테스트 잡 분리 — **추측으로 미리 배선하지 말고 실패를 보고 결정**
- [ ] 기존 `dependency-submission.yml`·`security-scan.yml`과 중복 트리거 없는지 확인

### 4. PR③ frontend `ci.yml`
- [ ] `package.json` 스크립트 분리 — `test:unit`(E2E 제외) 신설, `test:e2e`는 E2E만 지목. 기존 `test:e2e` 의미가 바뀌므로 README 갱신 동반
- [ ] `npm ci` → `npm run typecheck` → `npm run build` → `npm run test:unit`
- [ ] E2E는 CI 제외 + **제외 사유를 워크플로 주석에 명시**(다른 레포 서비스 2개 기동 필요 → M5 배포 파이프라인과 함께)

### 5. 마감
- [ ] 3 PR 머지 후 각 레포 main에서 CI green 확인(**squash 후 main 트리거까지** — 2026-07-17 교훈)
- [ ] dev-log 작성 + 이 plan `status: done`
- [ ] CLAUDE.md·Phase 2 plan의 "CI 갭" 경고 문구 해소

## 검증

**완료 조건은 "워크플로 파일 존재"가 아니라 "실패를 실제로 잡는다"** (`secure-coding.md` §자동 스캔 게이트 완료 조건의 정신을 빌드 게이트에 적용).

각 레포에서 **대조군**으로 증명한다 — 임시 커밋으로 의도적 실패를 주입해 CI가 **red**가 되는지 확인하고 되돌린다:

| 레포 | 주입할 실패 | 기대 |
|---|---|---|
| crdt-engine | 컴파일 에러 1줄 / 단언 뒤집은 테스트 / `cargo fmt` 위반 | build·test·fmt 각각 red |
| backend | 컴파일 에러 / 실패하는 테스트 | Gradle red |
| frontend | 타입 에러 / 실패하는 단위 테스트 | typecheck·test red |

- 트리거 전수: `pull_request` green ≠ `push: main` green (트리거별 범위 차이가 gitleaks 사고의 원인이었다)
- 실행 시간 기록 — 캐시 미스 시 과도하게 길면 튜닝 대상

## 재개 지점 (Resume)

- **마지막 완료**: (없음 — plan 작성 시점)
- **다음 = 단계 0**(proto 태그 정합). ⚠️ 태그 push는 **승인 게이트**. 태그가 원격에 없으면 단계 2가 성립하지 않으므로 순서를 바꾸지 말 것.
- **주의**: 서비스 3레포는 branch+PR+건별 승인. controller만 main 직접. 신규 액션은 전부 **spec 사전 검증 후** 작성(단계 1) — 이 레포의 반복 함정이 "버전·기본값 추측"이다(`config-contract-audit.md`).

## 범위 밖

- **프론트 E2E의 CI 실행** → 다른 레포 서비스 2개 기동 필요. M5 배포 파이프라인과 함께 재판정.
- 커버리지 게이트(80%/95% — `testing.md`)·criterion 벤치 회귀 가드(M1.5의 `--save-baseline`) CI 배선 → 후속. 지금은 "깨지면 red"가 목표.
- 다운스트림 자동 트리거(controller proto 변경 → 서비스 레포 `repository_dispatch`) → `proto-ci.yml`의 기존 TODO(M5).
- 릴리스·이미지 빌드·배포 파이프라인 → M5.
- ai-service → 레포 미생성(M4).
