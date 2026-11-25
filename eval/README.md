# Labelled sets and results
- `labelled.jsonl`: ideas with profiles and a human verdict each (clear GO, clear NO-GO, borderline, thin evidence). Note who labelled what. Used only for tuning and measuring, NEVER for training the scorer.
- `retrieval/`: 20+ hand-written queries with the cards that should come back (retrieval quality gate in CI).
- `baseline.json`: the stored baseline the nightly run compares against.
- `results/` is git-ignored.
