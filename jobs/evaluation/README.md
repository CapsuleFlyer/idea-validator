# M13 Evaluation harness
Runs the system on eval/labelled.jsonl, builds the confusion matrix, checks behaviour (tools used, evidence cited,
budget kept, injection resisted). Runs as a Kubernetes Job (k8s/eval-job.yaml) and nightly from Jenkins.
