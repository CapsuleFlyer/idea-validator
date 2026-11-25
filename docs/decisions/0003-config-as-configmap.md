# 0003. Weights, thresholds and floors live in a ConfigMap
Status: Draft
Context: We must tune T_go, T_no, floors and weights on a labelled set without rebuilding images.
Options: (1) constants in code, (2) environment variables, (3) a JSON file mounted from a ConfigMap and read on every request.
Decision: Option 3, canonical copy in `config/verdict.json`; `k8s/verdict-configmap.yaml` must match (checked by `tests/test_config_sync.py`).
Why: Rules change without a rebuild, versions are recorded in each verdict, and the engine refuses to start on invalid rules (weights must add to 100).
Cost: Two copies of the file to keep in sync (the test catches drift).
AI use: Drafted by AI. TODO: add before/after tuning numbers once we have them.
