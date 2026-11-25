"""M13 AgenticOps: trace store (guide section 2.3 / 7). One JSONL file per run."""
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

TRACE_DIR = Path(os.environ.get("TRACE_DIR", "/data/traces"))
RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # run ids become file names: no path tricks
_lock = threading.Lock()

app = FastAPI(title="M13 AgenticOps", version="0.1.0")


class TraceRecord(BaseModel):
    run_id: str
    step_id: int
    parent_step: Optional[int] = None
    agent: str
    kind: str = Field(pattern="^(tool_call|llm_call|decision)$")
    tool: Optional[str] = None
    input: Any = None
    output: Any = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    retries: int = 0
    model: Optional[str] = None
    cache_hit: bool = False
    error: Optional[str] = None
    ts: Optional[str] = None


def _path(run_id: str) -> Path:
    if not RUN_ID.match(run_id):
        raise HTTPException(status_code=422, detail="invalid run id")
    return TRACE_DIR / f"{run_id}.jsonl"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    try:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        probe = TRACE_DIR / ".probe"
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        raise HTTPException(status_code=503, detail=f"trace volume not writable: {e}") from e
    return {"status": "ready"}


@app.post("/trace", status_code=201)
def write_trace(rec: TraceRecord) -> dict:
    path = _path(rec.run_id)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    line = rec.model_dump_json()
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)  # traces also go to stdout as JSON lines (guide section 9)
    return {"ok": True}


@app.get("/runs/{run_id}/trace")
def read_trace(run_id: str) -> list[dict]:
    path = _path(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no trace for this run")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
