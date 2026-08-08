# Definition of Done 트래커

> PRD §7 DoD 9개 항목의 마일스톤별 진척·검증증거 추적.
> NFR(§6)별 측정수단·소유 마일스톤 매핑 포함.

**최종 갱신**: 2026-08-08

---

## DoD 항목 × 마일스톤

| # | DoD 항목 | 소유 M | 상태 | 검증증거 |
|---|---|---|---|---|
| 1 | 두 브라우저 동시 편집 수렴 | M1 | ✅ | E2E green `e8f0c83`, proptest 수렴 |
| 2 | 재접속 후 문서 상태 복원 | M2 | ✅ | SnapshotRestoreE2ETest 8건 green (PR #25 `ba0406c`), 엔진 save/load 실기동 확인 (PR #15·#17) |
| 3 | 타 사용자 커서·선택 실시간 표시 | M3 | 🔶 | 로컬 working tree 구현 + frontend 74/74·build, backend compile/Checkstyle/PMD 통과. Docker 회귀·4프로세스 2브라우저 스크린샷/로그·commit/PR/merge 대기 |
| 4 | 문서 근거 AI 답변 스트리밍 출력 | M4 | ⬜ | — |
| 5 | 로컬 GPU 과부하 시 클라우드 폴백 | M4 | ⬜ | — |
| 6 | Java→Rust→Python 단일 trace 관측 | M1(2-hop) / M4(3-hop) | 🔶 | 2-hop(Java→Rust) thin 증명 ✅ M1. 3-hop = M4 대기 |
| 7 | K8s(홈랩) GitOps 배포 | M5 | ⬜ | — |
| 8 | CRDT 수렴 property-based 검증 | M1 | ✅ | `proptest` convergence 테스트 green |
| 9 | README 아키텍처 결정 문서화 | M6 | ⬜ | — |

---

## NFR 측정수단 매핑

| NFR | 목표 | 측정수단 | 소유 M | 비고 |
|---|---|---|---|---|
| 동시 편집자/문서 ~50명 | p95 수렴 < 100ms @ 50 clients | k6/Gatling WebSocket 부하 테스트 | M3 | M1은 2-client 기능 증명만 |
| 동시 WS 커넥션 ~수천 | gateway VT saturation 미발생 | k6 ramp-up + JFR/async-profiler | M3 | VT pinning 부재 확인 포함 |
| 편집 반영 지연 p95 < 100ms | 서버 수신→broadcast 측정 | OTel histogram (`crdt.merge_duration`) | M3/M5 | 콜사이트 = T4-2 |
| AI 응답 시작 p95 < 5s | SSE 첫 토큰 latency | OTel histogram (`ai.inference.ttft`) | M4 | GPU 큐 대기 포함 |
| CRDT 수렴 100% | 어떤 머지 순서에도 동일 결과 | proptest (모든 순열) | M1 ✅ | — |
| 보안 (mTLS·JWT·하드닝) | 서비스간 평문 거부, 경계 검증 | Istio mTLS STRICT + 평문 curl 실패 테스트 | M5 | M2=앱 경계만 |
| 코드 품질 | 크래프트 `[B]` 위반 0 | 크래프트 게이트 리뷰 | 상시 | PR 머지 조건 |
| 관찰성 (폴리글랏 trace) | 단일 trace 3-hop | Jaeger UI trace 검색 | M4/M5 | 2-hop=M1 ✅ |

---

## 범례
- ✅ = 완료 (검증증거 존재)
- 🔶 = 부분 완료
- ⬜ = 미착수
