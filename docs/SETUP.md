# Setup

## 1. Local development (docker compose)
```bash
cp .env.example .env && $EDITOR .env
docker compose up -d --build
docker compose ps                         # wait until healthy
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
docker compose logs -f agentops           # traces appear here as JSON lines
```
Only the gateway is published (port 8000). Compose cannot enforce the M5-only internet rule on the gateway (it sits on a
non-internal network so the port can be published); Kubernetes does enforce it, and that is what you demonstrate.

## 2. Kubernetes with NetworkPolicy enforcement (kind + Calico)
Default kind does **not** enforce NetworkPolicy. Use this cluster config and install Calico.
```bash
kind create cluster --name idea-validator --config k8s/kind-config.yaml
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/tigera-operator.yaml
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/custom-resources.yaml
kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=300s
# metrics-server is needed for the autoscaler and `kubectl top` (follow its install docs; kind needs --kubelet-insecure-tls)
```
Check the Calico version and URLs against the current Calico docs before running; they change.

First deploy without a registry (images loaded straight into kind):
```bash
for s in gateway orchestrator tools kb scorer verdict agentops; do
  docker build -t registry/$s:dev services/$s && kind load docker-image registry/$s:dev --name idea-validator
done
kubectl apply -f k8s/secrets.example.yaml   # copy to k8s/secrets.yaml first and edit; it is git-ignored
kubectl apply -k k8s
kubectl get pods -n idea-validator
```
Because the manifests use `registry/<name>:dev`, add `imagePullPolicy: IfNotPresent` if kind tries to pull.
For Jenkins you need a real registry (GHCR or a local registry): decide and write a decision record.

## 3. NetworkPolicy test (screenshot for the report)
```bash
# from a NON-M5 pod: must FAIL
kubectl exec -n idea-validator deploy/kb -- python -c "import urllib.request as u; print(u.urlopen('https://api.github.com', timeout=5).status)"
# from M5: must WORK
kubectl exec -n idea-validator deploy/tools -- python -c "import urllib.request as u; print(u.urlopen('https://api.github.com', timeout=5).status)"
```

## 4. Rollout and rollback (screenshot)
```bash
kubectl set image deploy/gateway gateway=registry/gateway:bad -n idea-validator
kubectl rollout status deploy/gateway -n idea-validator   # stalls: maxUnavailable 0 keeps old pods serving
kubectl rollout undo deploy/gateway -n idea-validator
```

## 5. Protect `main` on GitHub
Settings > Branches > Add rule for `main`: require a pull request, require 1 approval, require status checks
(`test`, `manifests`, and each `docker (<service>)`), no direct pushes, dismiss stale approvals.
Screenshot the rule and one PR showing the checks.

## 6. Jenkins
Run Jenkins in a container with the Docker socket and your kubeconfig added as a **Jenkins credential** (id `kubeconfig-test`).
A GitHub webhook cannot reach a laptop: the Jenkinsfile uses SCM polling every 2 minutes (or use ngrok).
Set the `REGISTRY` environment variable on the job.
