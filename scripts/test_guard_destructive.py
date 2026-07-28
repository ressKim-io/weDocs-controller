#!/usr/bin/env python3
"""guard_destructive.py 대조군 테스트.

이 파일이 Bash 인라인이 아니라 별도 파일인 이유: 가드는 Bash 커맨드 **문자열 전체**를
검사하므로, 테스트 케이스를 heredoc이나 echo 인자로 넣으면 가드가 자기 테스트 하니스를
차단한다(2026-07-28 실측). 케이스를 파일 안에 두면 Bash가 보는 커맨드는 `python3 이파일`뿐.

실행: python3 scripts/test_guard_destructive.py  (exit 0 = 전부 통과)
"""
import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).with_name("guard_destructive.py")


def check(cmd: str) -> str:
    p = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True, text=True,
    )
    return "DENY" if p.stdout.strip() else "allow"


DENY = [
    "argocd app sync myapp --force",
    "argocd app sync --force myapp",            # 플래그가 앞 — deny 접두사 규칙이 못 잡는 케이스
    "git push origin main --force",
    "git push -f origin main",
    "kubectl --namespace prod delete pod x",    # 전역 플래그가 동사보다 앞
    "cd /tmp && kubectl apply -f x.yaml",       # 체이닝 뒤 세그먼트
    "echo hi; git push --force origin main",    # 세미콜론 뒤 세그먼트
    "KUBECONFIG=/tmp/k kubectl delete ns foo",  # env 프리픽스
    "cat x.yaml\nkubectl apply -f x.yaml",      # 개행 뒤 세그먼트 (heredoc 아님)
]

ALLOW = [
    "git push origin main",
    "git push --force-with-lease origin feat",  # lease는 안전한 형태 — 막지 않는다
    "kubectl get pods",
    "kubectl describe pod x",
    "kubectl logs -f pod/x",
    "argocd app sync myapp",
    "buf lint proto",
    "python3 scripts/claude_context_budget.py --json",
    # 인용부호 안 인용 — 앵커링으로 고친 오탐 클래스
    'echo \'{"command":"argocd app sync x --force"}\' > /tmp/t.json',
    "git commit -m 'docs: kubectl delete 사고 기록'",
    "grep -rn 'kubectl apply' docs/",
    # heredoc 본문 = 데이터. 사고 명령을 커밋 메시지·문서에 인용하는 것을 막으면 안 된다.
    "git commit -F - <<'EOF'\nfix: 사고 기록\n\nargocd app sync myapp --force 로 stuck 발생\nkubectl delete pod 로 복구 시도함\nEOF",
    "cat > /tmp/runbook.md <<EOF\ngit push --force origin main\nEOF",
]

fails = 0
print("=== 차단 기대 ===")
for c in DENY:
    r = check(c)
    ok = r == "DENY"
    fails += not ok
    print(f"  {'PASS      ' if ok else 'FAIL(미탐)'}  {c[:52]!r:<56} → {r}")

print("\n=== 통과 기대 (오탐 검증) ===")
for c in ALLOW:
    r = check(c)
    ok = r == "allow"
    fails += not ok
    print(f"  {'PASS      ' if ok else 'FAIL(오탐)'}  {c[:52]!r:<56} → {r}")

print(f"\n{'전부 통과' if not fails else str(fails) + '건 실패'} "
      f"({len(DENY)} deny / {len(ALLOW)} allow)")
sys.exit(1 if fails else 0)
