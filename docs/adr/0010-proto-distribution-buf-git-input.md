# ADR-0010 — proto 배포 = buf 원격 git input

- 상태: **Accepted**
- 날짜: 2026-06-25
- 관련: ADR-0006(5-repo 폴리레포 + buf) · SDD §12·§15 · [proto/README.md](../../proto/README.md)
- 대체: ADR-0006의 "submodule" 가정 — proto는 submodule이 아니라 buf 원격 git input으로 배포

## 맥락
proto는 controller가 SSOT다. 다운스트림 gRPC 소비자(`weDocs-crdt-engine`·`weDocs-backend`)가 이 계약을 어떻게 가져가 stub을 생성할지 미확정이었다(이전 세션 다운스트림 블로커). 초기 가정은 git submodule이었으나, **git submodule은 "레포 단위"라 다른 레포의 하위 디렉터리(`proto/`)만 선택적으로 mount할 수 없다.** controller는 proto 외 `infra/`·`docs/`·`.claude/`를 함께 담고 있어 통째 submodule은 과하다.

## 결정
다운스트림은 **buf의 원격 git input**으로 controller의 `proto/` 서브디렉터리를 직접 참조한다(submodule 불필요).

```
buf export 'https://github.com/ressKim-io/weDocs-controller.git#subdir=proto,ref=<tag>,depth=50' -o proto
```

- `ref`를 **태그로 핀**(예: `proto-v0.1.0`)해 재현성 확보. 계약 변경 = controller 태그 → 다운스트림 `ref` bump.
- 언어별 codegen:
  - **Rust**(crdt-engine) = `buf export`로 vendoring 후 `tonic-prost-build`(build.rs) — buf 원격 플러그인과 tonic 버전 skew 회피(tonic 0.14 = prost 0.14, hyper 1.0 계열).
  - **Java**(backend) = `buf generate`(`protocolbuffers/java` + `grpc/java` 플러그인).
- SSOT는 controller 유지(기존 결정 보존). frontend는 gRPC 비소비자(y-websocket) → proto 의존 없음.

## 대안 비교

| 방안 | proto만 선택 | SSOT 위치 | 외부 의존 | CI 인증 | 재현성 | 판정 |
|---|---|---|---|---|---|---|
| **buf 원격 git input** (채택) | ✅ `subdir=` | controller | 없음 | 불필요(공개 repo) | tag/commit 핀 | ✅ |
| git submodule (proto만) | ❌ 서브디렉터리 불가 | — | 없음 | — | commit 핀 | ❌ 기술적 불가 |
| controller 통째 submodule | △ 경로 참조 | controller | 없음 | — | commit 핀 | ❌ infra·docs까지 끌고 옴, 무겁다 |
| 별도 `weDocs-proto` 레포 | ✅ | proto 레포(분산) | 없음 | — | tag 핀 | ❌ SSOT가 controller 밖으로 |
| BSR (buf.build 레지스트리) | ✅ | BSR | hosted | 필요 | 버전 핀 | △ 가장 제품화되나 hosted 의존+인증, M1엔 과함 |

## 결과
- 이전 세션 다운스트림 블로커 해소 → M1 수직 슬라이스 착수 가능.
- `proto/README.md`·`proto/buf.yaml` 주석을 buf git-input으로 갱신, SDD §12 "submodule" → buf git-input, §15 미해결에서 제거.
- 검증 출처: buf.build/docs/reference/inputs (2026-06-25) — `subdir`/`ref`/`depth` 문법 확인.
- 후속: BSR는 M5(관측·계약 거버넌스 showcase) 단계에서 승격 검토 여지(재검증 후).

## 트레이드오프 (인정)
- buf 원격 input은 생성 시마다 git fetch → 오프라인/에어갭 빌드엔 `buf export` vendoring 보완 필요(crdt-engine은 `proto/` vendored + gitignored + `make proto-sync`).
- 태그 수동 bump = 휴먼 스텝. 자동화는 controller CI의 다운스트림 트리거(후속 M5)로 흡수.
