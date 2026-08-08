# weDocs 온보딩 · 멀티레포 셋업 · 재현성 가이드

다른 머신(Linux 등)에서 `git clone`/`git pull` 후 **Mac 개발 환경과 동일하게** 빌드·작업하기 위한 가이드.
"무엇이 git으로 따라오고, 무엇이 머신 로컬인지"를 명확히 한다.

> 진입점: [PRD](../PRD.md) → [SDD](../SDD.md) → [ADR](../adr/) → 현재 상태·다음 작업 SSOT [`status/current.md`](../status/current.md). 완료 이력은 [`status/history.md`](../status/history.md), 상세 실행 계획은 [`plans/`](../plans/).

---

## 1. 레포 레이아웃 (★ sibling 클론)

5-repo 폴리레포. **반드시 한 부모 디렉터리 아래 형제(sibling)로 클론**한다 — proto vendoring이 `../weDocs-controller/proto` 상대경로를 쓴다.

```
weDocs/
├── weDocs-controller/    # 컨트롤 플레인 (proto SSOT · infra · .claude · docs)  ← 진입점
├── weDocs-crdt-engine/   # Rust (yrs + tonic)
├── weDocs-backend/       # Java (ws-gateway, Spring Boot 4 / VT)
└── weDocs-frontend/      # React 19 + Tiptap 3 + Yjs
```

```sh
mkdir weDocs && cd weDocs
git clone https://github.com/ressKim-io/weDocs-controller.git
git clone https://github.com/ressKim-io/weDocs-crdt-engine.git
git clone https://github.com/ressKim-io/weDocs-backend.git
git clone https://github.com/ressKim-io/weDocs-frontend.git
```

> sibling이 아니어도 됨: proto는 controller가 SSOT라 **buf 원격 git input(태그 핀)**으로도 가져올 수 있다 → 각 Makefile/`buf.gen.yaml` 주석의 `ref=proto-v0.1.0` 형태 참조(ADR-0010). 단 기본값은 sibling 로컬 경로(빠른 dev iteration).

## 2. 사전 요구 도구 (환경 의존 — git으로 안 따라옴)

| 도구 | 버전(검증 2026-06-25) | Linux 설치 |
|------|----------------------|-----------|
| **buf** | 1.71+ | `BIN=/usr/local/bin && curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m)" -o $BIN/buf && chmod +x $BIN/buf` |
| **Rust** | edition 2024 → cargo/rustc **1.85+** (Mac는 1.96) | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| **JDK** | **25** | `sdk install java 25-tem` (SDKMAN) 또는 배포판 OpenJDK 25 |
| **Node** | 22+ (Mac는 26) | nvm `nvm install --lts` |
| Gradle | 9.1 | **설치 불필요** — `./gradlew`가 자동 다운로드 |
| protoc | — | **설치 불필요** — crdt-engine은 `protoc-bin-vendored`(linux-x86_64 포함)가 빌드시 제공 |

## 3. 레포별 셋업 (★ 반드시 `make` 타깃 사용)

proto는 vendoring/생성물이라 **gitignored** → 빌드 전 `make proto-*`가 먼저 돌아야 한다. **bare `cargo build`/`./gradlew build` 단독 실행은 fresh clone에서 실패**한다(proto 없음).

```sh
# crdt-engine (Rust)
cd weDocs-crdt-engine && make proto-sync && make check      # cargo check (proto export + tonic-prost-build)
make test                                                    # proptest 수렴 골격

# backend (Java) — gradlew가 Gradle 9.1 자동 download
cd ../weDocs-backend && make proto-gen && make compile        # buf generate(java+grpc) + compileJava

# frontend (React) — proto 의존 없음. lockfile 그대로 재현한다.
cd ../weDocs-frontend && npm ci && npm run test:unit && npm run build
```

검증 통과 기준: `cargo check --all-targets`·`cargo test` / backend compile·Checkstyle·PMD / frontend `npm run test:unit`·`npm run build`. doc-service 전체 통합 테스트는 Testcontainers를 사용하므로 Docker(OrbStack/Colima/Linux daemon)가 필요하다. M3 Phase 2의 CollaborationCaret 3.27.1은 frontend 변경이 머지된 뒤 `package-lock.json`과 `npm ci`로 재현하며 수동 전역 설치하지 않는다.

## 4. 재현성 매트릭스 — git으로 따라오는 것 vs 머신 로컬

| 항목 | 위치 | `git pull`로 따라옴? |
|------|------|:---:|
| 에이전트/스킬/룰/템플릿 | `weDocs-controller/.claude/` (254 files) | ✅ |
| **plan 기록** | `weDocs-controller/docs/plans/` | ✅ |
| ADR · SDD · dev-logs · PRD | `weDocs-controller/docs/` | ✅ |
| proto SSOT + buf 설정 | `weDocs-controller/proto/` | ✅ |
| 빌드 lock (재현) | `Cargo.lock` · `package-lock.json` · `gradle/wrapper/*`(실행권한 보존) | ✅ |
| **Claude 동작 룰(plan-logging 등)** | `.claude/rules/*` + `CLAUDE.md @import` | ✅ |
| proto 생성물 | `crdt-engine/proto/`, `backend/.../generated/` | ⛔ gitignored — `make proto-*`로 재생성 |
| 의존성 캐시 | `target/`, `node_modules/`, `.gradle/` | ⛔ gitignored — 빌드시 재취득 |
| **memory** | `~/.claude/projects/<절대경로-key>/memory/` | ❌ **머신 로컬** (아래 §5) |
| Claude 전역 설정/권한 | `~/.claude/settings*.json` | ❌ 머신 로컬(이 프로젝트는 미사용) |

→ **결론**: 프로젝트 산출물·Claude 자산(에이전트/스킬/룰/plan 기록)은 전부 controller 레포로 따라온다. 유일한 비동기화는 user-level `~/.claude` (memory·전역설정)뿐.

## 5. memory gap (중요 — 그러나 비핵심)

`~/.claude/projects/-Users-jun-my-file-weDocs-weDocs-controller/memory/` 의 memory 파일(MEMORY.md 등)은:
- **레포 밖** + 디렉터리 key가 **절대 홈경로**(`-Users-jun-...`)라 Linux(`-home-...`)에선 key 자체가 다름 → 따라오지 않는다.

**왜 문제되지 않나**: 핵심 동작인 **plan-logging은 memory가 아니라 룰이 강제**한다 — [`.claude/rules/plan-logging.md`](../../.claude/rules/plan-logging.md)가 레포에 있고 `CLAUDE.md`의 항상-적용 `@import`로 로드된다. memory의 `plan-logging-mandatory`는 보조 리마인더일 뿐. 즉 **Linux에서도 plan은 `docs/plans/`에 기록·커밋된다.**

원한다면 Linux의 `~/.claude/projects/<그-머신의-key>/memory/`에 수동 복사 가능하나, 프로젝트 재현에는 불필요.

## 6. 현재 상태 / 다음 (roadmap)

- **M0** ✅ 기획·proto·스캐폴딩
- **M1** ✅ CRDT 코어·두 브라우저 수렴·Java→Rust thin trace
- **M2** ✅ doc-service·인증/인가·스냅샷 저장/복원·outbox·E2E
- **M3** 🔶 Presence + 멀티인스턴스 진행 중. Phase 1 awareness 로컬 릴레이는 머지됐고, Phase 2 커서·선택 UI는 로컬 working tree 구현 후 Docker/2브라우저 증거와 서비스 PR을 기다린다.
- **M4~M6** AI co-pilot → 인프라·관측 → 문서·데모 마감

자주 바뀌는 branch/PR/검증 상태는 이 문서에 복제하지 않는다. 항상 [`docs/status/current.md`](../status/current.md)를 먼저 읽고, 완료 이력은 [`docs/status/history.md`](../status/history.md), 실행 상세는 [`docs/plans/`](../plans/)에서 확인한다.

## 7. 자주 막히는 곳

- `cargo build`가 `proto 컴파일 실패` → `make proto-sync` 먼저 (proto는 gitignored).
- backend compile 에러(CrdtEngineGrpc 없음) → `make proto-gen` 먼저.
- sibling 레이아웃 아님 → proto-sync 실패 → §1 레이아웃대로 클론 또는 remote 태그 input 사용.
- JDK 25 아님 → Gradle toolchain 에러 → JDK 25 설치(§2).
