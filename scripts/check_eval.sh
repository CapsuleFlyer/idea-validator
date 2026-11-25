#!/usr/bin/env bash
# TODO: wait for the eval Job, read its result JSON, compare with eval/baseline.json, exit 1 if worse.
set -euo pipefail
kubectl wait --for=condition=complete job/eval -n idea-validator --timeout=900s
echo "TODO: compare results with the stored baseline"
