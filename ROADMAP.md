# Roadmap (suggested order; make each line an issue)

**Week 1-2: thin version of everything, running on Kubernetes**
- [ ] Push repo, protect `main`, both laptops green on compose + smoke test
- [ ] Deploy the current slice to kind (Calico), take the pods / NetworkPolicy / rollout+rollback screenshots early
- [ ] Jenkins in a container, SCM polling, one green and one deliberately failing run
- [ ] M2: Postgres schema + migrations + Redis cache (keys include profile/rubric/config version)

**Week 2-4: data first (everything depends on it)**
- [ ] M5 connectors: Hacker News, GitHub, one of Reddit/Product Hunt; rate limits, robots.txt, sanitiser
- [ ] M4 scouts (CronJob + on demand) and M6i ingestion: 1,500+ cards, 3+ sources, no duplicates
- [ ] M6 hybrid search + rerank; 20+ hand-written retrieval queries; CI retrieval gate

**Week 4-7: intelligence**
- [ ] Rubrics for all six dimensions with anchors and examples
- [ ] M9 scorers with computed features + M10 interface (hosted model first, fine-tuned later)
- [ ] M7 niche clustering and trend series; gap list
- [ ] M8 Ideator / Gap Analyst / Skeptic with limited rounds; M12 critic and injection defence
- [ ] M3: Discover workflow, budgets, approvals, retries, SSE progress

**Week 6-9: fine-tuning, tuning, UI**
- [ ] 300+ examples, 60+ hand-checked; LoRA on free GPU; base vs fine-tuned vs hosted table
- [ ] Labelled set, confusion matrices before/after, tune `config/verdict.json`
- [ ] M1 UI: login, profile, Discover, live progress, verdict card, challenge, what-if, history, compare, INSUFFICIENT EVIDENCE card
- [ ] M13: replay, eval harness (Job + nightly), drift report, dashboard

**Last weeks:** report (max 10 pages), screenshots with captions, contribution table, decision records, README check on a clean machine.
