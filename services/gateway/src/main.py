"""M1 API Gateway: the only entrance. Browsers never call other services directly.

Implemented: /validate and /runs/{id} (proxied to the orchestrator), /health, /ready, /metrics.
TODO: auth (register/login, hashed passwords, sessions), profile, /discover, SSE events,
approvals, ideas/versions/compare, rate limiting, input validation on every route.
All upstream addresses come from environment variables (never hard-code localhost).
"""
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000")
app = FastAPI(title="M1 API Gateway", version="0.1.0")
_counts: dict[str, int] = {}


@app.middleware("http")
async def count_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    key = f'{request.method} {request.url.path.split("/")[1] or "/"} {response.status_code}'
    _counts[key] = _counts.get(key, 0) + 1
    response.headers["X-Process-Time-Ms"] = str(int((time.perf_counter() - t0) * 1000))
    return response


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


def _not_built(name: str):
    raise HTTPException(status_code=501, detail=f"{name} is not implemented yet")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            (await c.get(f"{ORCHESTRATOR_URL}/ready")).raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="orchestrator not ready") from e
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> Response:
    lines = [f'gateway_requests_total{{route="{k}"}} {v}' for k, v in sorted(_counts.items())]
    return Response("\n".join(lines) + "\n", media_type="text/plain")


async def _forward(method: str, path: str, **kw: Any) -> Any:
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.request(method, f"{ORCHESTRATOR_URL}{path}", **kw)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="orchestrator unreachable") from e
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", "upstream error"))
    return r.json()


@app.post("/validate")
async def validate(req: ValidateIn) -> dict:
    return await _forward("POST", "/validate", json=req.model_dump())


@app.get("/runs/{run_id}")
async def run(run_id: str) -> dict:
    return await _forward("GET", f"/runs/{run_id}")


@app.post("/auth/register")
def register() -> None:
    _not_built("auth")


@app.post("/auth/login")
def login() -> None:
    _not_built("auth")


@app.get("/profile")
def get_profile() -> None:
    _not_built("profile")


@app.put("/profile")
def put_profile() -> None:
    _not_built("profile")


@app.post("/discover")
def discover() -> None:
    _not_built("discover")
