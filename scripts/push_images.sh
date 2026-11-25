#!/usr/bin/env bash
# usage: scripts/push_images.sh <registry> <tag>
set -euo pipefail
cd "$(dirname "$0")/.."; . scripts/_services.sh
REGISTRY="${1:?registry}"; TAG="${2:?tag}"
for s in $SERVICES; do
  docker push "$REGISTRY/$s:$TAG"
done
