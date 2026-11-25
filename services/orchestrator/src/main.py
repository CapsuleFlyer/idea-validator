"""M3 Orchestrator. Thin vertical slice of the Validate workflow (description 3.2):
evidence -> four/six scorers in parallel -> verdict engine -> trace.

STUB MODE (default): when the knowledge base returns nothing, synthetic evidence is used so the
whole system can be exercised end to end on Kubernetes early. Turn off with STUB_MODE=false.

TODO: Discover workflow, clarifying questions, budgets (tokens/steps/cost), retries and timeouts,
re-run only what changed, approvals, SSE events, persistence in M2 (results are in memory here).
"""
import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("orchestrator")
KB_URL = os.environ.get("KB_URL", "http://kb:8000")
SCORER_URL = os.environ.get("SCORER_URL", "http://scorer:8000")
VERDICT_URL = os.environ.get("VERDICT_URL", "http://verdict:8000")
AGENTOPS_URL = os.environ.get("AGENTOPS_URL", "http://agentops:8000")
STUB_MODE = os.environ.get("STUB_MODE", "true").lower() == "true"
DIMENSIONS = ("demand_pain", "competition", "differentiation", "feasibility", "risk", "learning")

app = FastAPI(title="M3 Orchestrator", version="0.1.0")
RESULTS: dict[str, dict] = {}  # TODO: move to M2 (Postgres)


class Profile(BaseModel):
    skills: list[str] = []
    hours_per_week: float = Field(gt=0, le=168)
    weeks_available: float = Field(gt=0, le=104)
    team_size: int = Field(default=1, ge=1, le=10)
    compute: str = Field(default="laptop", pattern="^(laptop|free_gpu|paid)$")
    goal: str = Field(pattern="^(startup|portfolio|course_project)$")
    interests: list[str] = []


class ValidateIn(BaseModel):
    idea: str = Field(min_length=3, max_length=2000)
    profile: Profile
    idea_id: Optional[str] = None


class Tracer:
    """Every step writes a trace record under one run id. Tracing must never break a run."""

    def __init__(self, client: httpx.AsyncClient, run_id: str):
        self.client, self.run_id, self.step = client, run_id, 0

    async def log(self, agent: str, kind: str, tool: Optional[str] = None, *, input: Any = None,
                  output: Any = None, latency_ms: int = 0, error: Optional[str] = None,
                  parent: Optional[int] = None) -> int:
        self.step += 1
        rec = {"run_id": self.run_id, "step_id": self.step, "parent_step": parent, "agent": agent,
               "kind": kind, "tool": tool, "input": input, "output": output, "latency_ms": latency_ms,
               "error": error, "ts": datetime.now(timezone.utc).isoformat()}
        try:
            await self.client.post(f"{AGENTOPS_URL}/trace", json=rec)
        except httpx.HTTPError as e:
            log.warning("trace write failed: %s", e)
        return self.step


def _stub_evidence() -> list[dict]:
    return [
        {"evidence_id": "stub_a#0", "card_id": "stub_a", "source": "hackernews", "quote": "stub"},
        {"evidence_id": "stub_b#0", "card_id": "stub_b", "source": "github", "quote": "stub"},
        {"evidence_id": "stub_c#0", "card_id": "stub_c", "source": "github", "quote": "stub"},
    ]


async def _post(client: httpx.AsyncClient, tr: Tracer, agent: str, tool: str, url: str, body: dict) -> dict:
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=body)
        r.raise_for_status()
        out = r.json()
    except (httpx.HTTPError, ValueError) as e:
        await tr.log(agent, "tool_call", tool, input=body, error=str(e),
                     latency_ms=int((time.perf_counter() - t0) * 1000))
        raise HTTPException(status_code=502, detail=f"{agent} failed: {e}") from e
    await tr.log(agent, "tool_call", tool, input=body, output=out,
                 latency_ms=int((time.perf_counter() - t0) * 1000))
    return out


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    return {"status": "ready", "stub_mode": STUB_MODE}


@app.post("/validate")
async def validate(req: ValidateIn) -> dict:
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    idea_id = req.idea_id or f"idea_{uuid.uuid4().hex[:6]}"
    profile = req.profile.model_dump()
    async with httpx.AsyncClient(timeout=15) as client:
        tr = Tracer(client, run_id)
        await tr.log("orchestrator", "decision", input={"idea_id": idea_id, "profile": profile},
                     output="start validate")

        kb = await _post(client, tr, "kb", "search_kb", f"{KB_URL}/search", {"query": req.idea, "limit": 10})
        evidence = kb.get("items", [])
        if not evidence and STUB_MODE:
            evidence = _stub_evidence()
        n_sources = len({e["card_id"] for e in evidence})
        n_platforms = len({e["source"] for e in evidence})

        results = await asyncio.gather(*[
            _post(client, tr, f"{d}_scorer", "score", f"{SCORER_URL}/score",
                  {"dimension": d, "idea": req.idea, "evidence": evidence})
            for d in DIMENSIONS
        ])
        by_dim = {r["dimension"]: r for r in results}
        abstained = [d for d, r in by_dim.items() if r.get("abstain")]
        if abstained:
            out = {"run_id": run_id, "idea_id": idea_id, "verdict": "INSUFFICIENT_EVIDENCE",
                   "reasons": [f"scorer abstained (no evidence): {', '.join(abstained)}"]}
            await tr.log("orchestrator", "decision", output=out)
            RESULTS[run_id] = out
            return out

        feats = {d: by_dim[d].get("features", {}) for d in DIMENSIONS}
        verdict_req = {
            "idea_id": idea_id, "version": 1, "run_id": run_id,
            "scores": {d: {k: by_dim[d][k] for k in ("score", "confidence", "evidence_ids", "reason") if k in by_dim[d]}
                       for d in DIMENSIONS},
            "profile": profile,
            "gate_inputs": {
                "n_sources": n_sources, "n_platforms": n_platforms,
                "estimated_build_hours": feats["feasibility"].get("estimated_build_hours", 0),
                "risk_blockers": feats["risk"].get("risk_blockers", []),
                "duplicate_product": feats["competition"].get("duplicate_product"),
            },
        }
        verdict = await _post(client, tr, "verdict_engine", "verdict", f"{VERDICT_URL}/verdict", verdict_req)
        await tr.log("orchestrator", "decision", output={"verdict": verdict["verdict"]})

    verdict["stub_mode"] = STUB_MODE
    RESULTS[run_id] = verdict
    return verdict


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    if run_id not in RESULTS:
        raise HTTPException(status_code=404, detail="unknown run")
    return RESULTS[run_id]
