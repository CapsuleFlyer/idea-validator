#!/usr/bin/env bash
# usage: scripts/deploy.sh <registry> <tag>   Needs KUBECONFIG and kubectl.
# Renders k8s/ with the registry and commit-SHA tag, applies it, waits for every rollout.
# If a rollout fails the script fails (so Jenkins stops). Roll back with:
#   kubectl rollout undo deploy/<name> -n idea-validator
set -euo pipefail
cd "$(dirname "$0")/.."; . scripts/_services.sh
REGISTRY="${1:?registry}"; TAG="${2:?tag}"
NS=idea-validator
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cp -r k8s "$TMP/k8s"
REGISTRY="$REGISTRY" TAG="$TAG" SERVICES="$SERVICES" python3 - "$TMP/k8s/kustomization.yaml" <<'PY'
import os, re, sys
path = sys.argv[1]
text = open(path).read()
text = text.split("images:")[0] + "images:\n" + "".join(
    f"  - name: registry/{s}\n    newName: {os.environ['REGISTRY']}/{s}\n    newTag: {os.environ['TAG']}\n"
    for s in os.environ["SERVICES"].split())
open(path, "w").write(text)
PY
kubectl apply -k "$TMP/k8s"
for s in $SERVICES; do
  kubectl rollout status "deploy/$s" -n "$NS" --timeout=120s
done
