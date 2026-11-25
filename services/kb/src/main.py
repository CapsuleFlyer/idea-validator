"""M6 Knowledge Base (RAG). STUB: empty results.

TODO: hybrid search (vector + keyword) with reranking, filters by date/source/niche, card ids for
citations, freshness and coverage tracking. Measure retrieval on 20+ hand-written queries (eval/).
"""
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="M6 Knowledge Base (stub)", version="0.1.0")


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    source: Optional[str] = None
    niche: Optional[str] = None
    since: Optional[str] = None  # ISO date


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    return {"status": "ready"}  # TODO: check Postgres and the vector store


@app.post("/search")
def search(req: SearchIn) -> dict:
    return {"items": [], "note": "stub: knowledge base not built yet"}
