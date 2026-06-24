# argocd — GitOps

`app-of-apps.yaml` = 루트 Application. ArgoCD가 controller 레포를 SSOT로 watch하며
`infra/k8s/overlays/homelab`을 클러스터에 동기화한다.

## 적용
```sh
kubectl apply -n argocd -f app-of-apps.yaml
```

## TODO
- `repoURL` 실제 값으로 교체(원격 push 후).
- 서비스가 늘면 단일 Application → 하위 Application 목록(진짜 app-of-apps)으로 분리.
- istio waypoint/DestinationRule을 별도 Application(또는 동일 overlay)으로 포함할지 결정.
