# ci — proto 게이트 + 다운스트림 트리거

컨트롤러 CI의 책임: **proto 계약을 지키는 문지기**.

## 게이트 (`.github/workflows/proto-ci.yml`)
1. `buf lint proto` — 스타일 강제.
2. `buf format --diff` — 포맷 검사.
3. `buf breaking proto --against <main>` — wire 호환성 파괴 차단.

`proto/**` 변경 PR은 이 셋을 통과해야 머지 가능.

## 다운스트림 트리거 (M5)
main에 proto가 머지되면 → 다운스트림 레포(`backend` / `ai-service` / `crdt-engine`)에
`repository_dispatch`(또는 submodule bump PR)로 재생성·빌드를 트리거.

> 폴리레포 비용(proto 동기화, CI 5벌)을 컨트롤러의 멀티레포 오케스트레이션 + buf 게이트로
> 관리하는 것 자체가 DevOps showcase (SDD §12).

## 가드레일
proto 변경은 **반드시 여기서 시작**한다. 다운스트림에서 직접 수정한 proto는 SSOT 위반.
