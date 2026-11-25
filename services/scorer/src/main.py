"""M10 Scoring Model service. STUB: returns a fixed mid score so the pipeline runs end to end.

TODO (fine-tuning work): load the merged LoRA model, apply the rubric in rubrics/, validate the
output against the schema, retry once, then fall back to the hosted model and log the fallback.
"""
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

DIMENSIONS = ("demand_pain", "competition", "differentiation", "feasibility", "risk", "learning")

app = FastAPI(title="M10 Scoring Model (stub)", version="0.1.0")


class ScoreIn(BaseModel):
    dimension: str = Field(pattern="^(demand_pain|competition|differentiation|feasibility|risk|learning)$")
    idea: str = Field(min_length=1, max_length=4000)
    evidence: list[dict[str, Any]] = []
    rubric_version: str = "stub@v0"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    return {"status": "ready", "model": "stub"}


@app.post("/score")
def score(req: ScoreIn) -> dict:
    ids = [e["evidence_id"] for e in req.evidence if "evidence_id" in e]
    if not ids:  # no evidence id, no score: the scorer abstains
        return {"dimension": req.dimension, "abstain": True, "reason": "no evidence to cite"}
    features: dict[str, Any] = {"n_sources": len({e.get("card_id") for e in req.evidence})}
    if req.dimension == "feasibility":
        features["estimated_build_hours"] = 60
    if req.dimension == "risk":
        features["risk_blockers"] = []
    if req.dimension == "competition":
        features["duplicate_product"] = None
    return {
        "dimension": req.dimension, "score": 3.0, "confidence": 0.6, "evidence_ids": ids[:3],
        "features": features, "reason": "STUB score; replace with the fine-tuned scorer.",
        "rubric_version": req.rubric_version, "model": "stub",
    }
