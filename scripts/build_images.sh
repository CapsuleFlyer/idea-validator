#!/usr/bin/env bash
# usage: scripts/build_images.sh <registry> <tag>   (tag = commit SHA, never only "latest")
set -euo pipefail
cd "$(dirname "$0")/.."; . scripts/_services.sh
REGISTRY="${1:?registry}"; TAG="${2:?tag}"
for s in $SERVICES; do
  docker build -t "$REGISTRY/$s:$TAG" "services/$s"
done
