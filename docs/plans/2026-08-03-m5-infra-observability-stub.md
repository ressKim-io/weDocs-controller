---
date: 2026-08-03
slug: m5-infra-observability-stub
status: stub
related:
  - adr/0007-istio-ambient.md
  - design/observability-callsites.md
  - status/dod-tracker.md
---

# M5 — 인프라·관측 (Plan Stub)

> M5 착수 시 이 stub을 정식 plan으로 확장한다. 범위와 검증 시나리오만 선고정.

## 목표

- K8s(홈랩 KinD) GitOps 배포 (ArgoCD)
- 서비스 간 mTLS STRICT (Istio Ambient, ADR-0007)
- 폴리글랏 단일 trace (Java→Rust→Python, OTel)
- 핵심 대시보드·알림 (observability-callsites.md 기준)

## 범위

| 항목 | 산출물 |
|---|---|
| 컨테이너화 | Dockerfile 4서비스 (multi-stage, cargo-chef/jib) |
| Kustomize 매니페스트 | base + overlays (local/staging) |
| ArgoCD Application | GitOps — main push 시 자동 sync |
| Istio Ambient 설치 | ztunnel 전체 + waypoint(engine만) |
| mTLS 검증 | PeerAuthentication STRICT + 평문 curl 실패 테스트 |
| NetworkPolicy | 엔진 직접 접근 차단 (gateway만 허용) |
| OTel Collector | traces → Jaeger, metrics → Prometheus |
| Grafana 대시보드 | 4패널 (observability-callsites.md §대시보드 구성) |
| 알림 | 4규칙 (observability-callsites.md §알림 후보) |
| 통합 compose | 로컬 개발 docker-compose (postgres+engine+gateway+doc-service+jaeger) |

## 검증 시나리오 (착수 시 테스트로 구현)

1. **mTLS STRICT**: `istioctl proxy-config` + 평문 `grpcurl` → connection refused
2. **NetworkPolicy**: pod 외부에서 engine gRPC 직접 호출 → timeout
3. **단일 trace**: 브라우저 편집 → Jaeger에서 3-hop trace 검색 성공
4. **GitOps sync**: main에 manifest push → ArgoCD가 자동 배포 확인
5. **알림 발화**: `authz.backend.error` 인위 주입 → alert 수신 확인

## 선결 조건

- M3 완료 (consistent hash 라우팅 = waypoint 설정의 전제)
- M4 완료 (ai-service 존재해야 3-hop trace 가능)
- 또는 M3/M4 없이 2-hop(Java→Rust) 부분 배포로 시작 가능

## 범위 밖

- 멀티클라우드 failover (별도 프로젝트에서 이미 증명, PRD §5)
- CDN / 정적 에셋 배포 (프론트엔드 별도)
- 로드밸런서 외부 노출 (홈랩 내부망)
