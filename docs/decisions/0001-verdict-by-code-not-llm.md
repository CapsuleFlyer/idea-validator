# 0001. The verdict is decided by plain code (M11), never by a model
Status: Draft (review and edit before submitting)
Context: LLM judges drift unless rubrics are locked and evidence is required; the project asks for explainable, repeatable verdicts.
Options: (1) LLM outputs the verdict, (2) LLM outputs scores and code decides, (3) LLM outputs scores plus a verdict that code may override.
Decision: Option 2. Scorers return 0-5 scores with confidence and evidence ids; `services/verdict` applies gates, weights, thresholds and sensitivity.
Why: Same input gives the same output; every gate and threshold edge is unit-tested (35 tests); an injected page cannot set the verdict.
Cost: Scores still carry model error, handled by confidence, abstention and the labelled-set tuning.
AI use: Drafted by AI. TODO: check against what we actually built and change.
