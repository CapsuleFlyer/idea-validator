"""M5 Tool Layer: the single controlled exit to the internet (NetworkPolicy enforces it in k8s).

TODO: connectors (HN Firebase, GitHub REST, Product Hunt/Reddit), per-domain rate limits,
robots.txt, cache, and the sanitiser that strips text aimed at models. Fetched text is data.
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .policy import check_url, parse_allow_list

ALLOWED = parse_allow_list(os.environ.get(
    "ALLOWED_DOMAINS",
    "hacker-news.firebaseio.com,api.github.com,www.reddit.com,api.producthunt.com",
))
app = FastAPI(title="M5 Tool Layer", version="0.1.0")


class FetchIn(BaseModel):
    url: str
    source: str = "generic"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    return {"status": "ready", "allowed_domains": sorted(ALLOWED)}


@app.post("/fetch")
def fetch(req: FetchIn) -> dict:
    ok, reason = check_url(req.url, ALLOWED)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    raise HTTPException(status_code=501, detail="connectors not implemented yet")
