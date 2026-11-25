# Working agreement (both members)

- `main` is protected: pull requests only, required checks green, one review from the **other** member.
- One issue per task, one branch per issue, one purpose per branch, small PRs. Link them (`Closes #12`).
- Conventional commits: `feat(verdict): add duplicate gate`, `fix(kb): dedupe by url`, `test(scouts): add source failure case`, `docs:`, `chore:`, `ci:`.
- Branch names: `feat/m11-whatif`, `fix/m5-allowlist`.
- Both members commit code and review the other's PRs. The contribution table must match the git history.
- Never commit keys, passwords, `.env`, kubeconfigs, model weights or private data.
- Keep `docs/ai-usage-log.md` current: what AI wrote, what you changed, why. You are responsible for every line.
- Any design choice with trade-offs gets a short record in `docs/decisions/` (at least 3 are required).

## Deliberate merge conflict (required screenshot)
1. Branch `conflict-a` and `conflict-b` from `main`; both edit the same lines in `docs/conflict-demo.md`.
2. Merge A by PR. Open the PR for B: GitHub reports a conflict.
3. Resolve in the PR (or locally), push, screenshot the conflict and the resolved PR, then delete `docs/conflict-demo.md` in a later PR.

## Definition of done for a module
Own Dockerfile, `/health` and `/ready`, schema-validated input and output, tests, probes and resource numbers measured with
`kubectl top`, traces written to M13, documented in README.
