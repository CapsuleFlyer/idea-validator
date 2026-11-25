#!/usr/bin/env bash
# End-to-end check on the cluster: gateway -> orchestrator -> scorer/kb -> verdict engine -> trace.
# Works from Jenkins/laptop with kubectl access (port-forward) or against any URL: BASE_URL=http://localhost:8000
set -euo pipefail
NS=idea-validator
if [ -z "${BASE_URL:-}" ]; then
  kubectl port-forward -n "$NS" svc/gateway 18000:8000 >/dev/null 2>&1 &
  PF=$!; trap 'kill $PF 2>/dev/null || true' EXIT; sleep 3
  BASE_URL=http://localhost:18000
fi
curl -fsS "$BASE_URL/health" >/dev/null && echo "health ok"
curl -fsS "$BASE_URL/ready" >/dev/null && echo "ready ok"
RESP=$(curl -fsS -X POST "$BASE_URL/validate" -H 'Content-Type: application/json' -d '{
  "idea": "A tool that turns lecture recordings into flashcards",
  "profile": {"skills": ["python"], "hours_per_week": 10, "weeks_available": 12, "team_size": 2,
              "compute": "laptop", "goal": "course_project", "interests": ["education"]}}')
echo "$RESP" | python3 -c '
import json, sys
r = json.load(sys.stdin)
assert r.get("verdict") in {"GO", "PIVOT", "NO-GO", "INSUFFICIENT_EVIDENCE"}, r
assert r.get("run_id"), r
print("verdict:", r["verdict"], "run:", r["run_id"])'
echo "smoke test passed"
