"""M11 Verdict Engine service. Thin HTTP wrapper: all decisions live in engine.py (no LLM)."""
import json
import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException

from . import engine

# The rules live in a ConfigMap mounted here (see k8s/verdict-configmap.yaml).
CONFIG_PATH = Path(os.environ.get("VERDICT_CONFIG", "/config/verdict.json"))

app = FastAPI(title="M11 Verdict Engine", version=engine.ENGINE_VERSION)


def _load_config() -> dict:
    # Read on every request so a changed ConfigMap takes effect without a rebuild.
    cfg = json.loads(CONFIG_PATH.read_text())
    engine.validate_config(cfg)
    return cfg


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    try:
        _load_config()
    except Exception as e:  # missing or invalid rules: cannot serve
        raise HTTPException(status_code=503, detail=f"config not usable: {e}") from e
    return {"status": "ready", "engine": engine.ENGINE_VERSION}


def _run(fn, *args):
    try:
        return fn(*args)
    except engine.InputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (engine.ConfigError, OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=503, detail=f"config not usable: {e}") from e


@app.post("/verdict")
def verdict(payload: dict[str, Any] = Body(...)) -> dict:
    """In: six scores, profile, gate inputs. Out: verdict JSON (guide section 2.3)."""
    return _run(lambda: engine.decide(payload, _load_config()))


@app.post("/whatif")
def whatif(payload: dict[str, Any] = Body(...)) -> dict:
    """In: {"request": <verdict request>, "changes": {"scores": {...}, "gate_inputs": {...}}}."""
    if "request" not in payload or "changes" not in payload:
        raise HTTPException(status_code=422, detail="'request' and 'changes' are required")
    return _run(lambda: engine.whatif(payload["request"], payload["changes"], _load_config()))
