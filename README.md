# Idea Generator with Go / No-Go

CS4032 Software Construction and Development, semester project. A multi-agent system that helps a student
choose a project: **Discover** ideas that fit a profile, or **Validate** an idea and get GO / PIVOT / NO-GO /
INSUFFICIENT EVIDENCE with the evidence behind it. Models produce evidence-backed scores; **only the Verdict Engine
(plain code, M11) decides the verdict.**

Team: Shaheer Sohail (24I-3060), Abubakr Ahmed (24I-3016)

## Run it

```bash
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose up -d --build
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
```

Kubernetes (kind + Calico so NetworkPolicy is enforced): see [docs/SETUP.md](docs/SETUP.md).

Run the tests (no dependencies needed for these two):

```bash
(cd services/verdict && python -m unittest)    # verdict engine, 35 tests
(cd services/tools && python -m unittest)      # M5 URL policy
```

## What exists today

| Module | Service | Status |
|---|---|---|
| M11 Verdict Engine | `services/verdict` | **Done** (gates, weights, thresholds, floor, confidence, sensitivity, what-if, challenge) and unit-tested; the worked example from the description is a test |
| M5 Tool Layer | `services/tools` | URL policy (https, allow-list, no IPs/credentials) done and tested. Connectors, rate limits, robots.txt, sanitiser: TODO |
| M13 AgenticOps | `services/agentops` | Trace write/read (JSONL per run, also to stdout). Budgets, replay, eval harness, drift, dashboard: TODO |
| M3 Orchestrator | `services/orchestrator` | Thin Validate slice (parallel scorers, verdict, tracing). Discover, budgets, retries, approvals: TODO |
| M1 Gateway | `services/gateway` | `/validate`, `/runs/{id}`, health, metrics. Auth, profile, Discover, SSE, rate limits: TODO (501 for now) |
| M10 Scoring Model | `services/scorer` | **Stub** (fixed score). Fine-tuned model: TODO |
| M6 Knowledge Base | `services/kb` | **Stub** (empty). Hybrid search, ingestion, cards: TODO |
| M2, M4, M6i, M7, M8, M9, M12 | not started | see [ROADMAP.md](ROADMAP.md) |
| M14 Platform | `.github/`, `Jenkinsfile`, `k8s/`, `scripts/` | Written, **not yet run against a real cluster** |

The orchestrator runs in `STUB_MODE` so the whole path (gateway to verdict) works before the data exists.
Stub verdicts are marked `"stub_mode": true` and mean nothing.

## Layout

```
services/   one folder + Dockerfile per module (gateway, orchestrator, tools, kb, scorer, verdict, agentops)
config/     verdict.json: weights, thresholds, floor (mounted as a ConfigMap on k8s)
schemas/    JSON Schemas for the shared records (profile, card, evidence, score, trace)
rubrics/    one versioned file per dimension
eval/       labelled sets, retrieval queries, baseline (never train on the labelled set)
jobs/       ingestion, finetune, evaluation
k8s/        manifests (kustomize), NetworkPolicy, kind config
scripts/    build, push, deploy, smoke test
docs/       setup, decision records, AI-usage log, contribution table
tests/      repo-level tests (ConfigMap matches config file)
```

## Day-1 checklist (do these before writing more code)

- [x] Names, roll numbers and GitHub usernames filled in (README, CODEOWNERS, contributions table)
- [ ] Fill in "Modules owned" in `docs/contributions.md` once you split the work
- [ ] Push this to a **new** repository with a clean history, add your partner, make sure markers can open it
- [ ] Protect `main` (see docs/SETUP.md): PRs only, required checks, one review from the other member
- [ ] Open one issue per task from [ROADMAP.md](ROADMAP.md) and work in small branches
- [ ] Do the deliberate merge conflict early and keep the screenshot
- [ ] Get `docker compose up` and `./scripts/smoke_test.sh` green on both laptops
- [ ] Get the thin slice onto a local Kubernetes cluster this week

Workflow rules are in [CONTRIBUTING.md](CONTRIBUTING.md). Threats and how we handle them: [THREAT_MODEL.md](THREAT_MODEL.md).
