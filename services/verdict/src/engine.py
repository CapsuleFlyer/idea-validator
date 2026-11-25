"""M11 Verdict Engine.

Plain code. No LLM, no network, no clock, no randomness: the same input always gives
the same output. Models produce evidence-backed scores; only this module decides.

Flow (project description, Figure 4):
  gates (evidence, feasibility, risk, duplicate) -> confidence -> weighted score ->
  thresholds + floor -> sensitivity check -> what-would-make-GO.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

ENGINE_VERSION = "m11@v1"

DIMENSIONS = ("demand_pain", "competition", "differentiation", "feasibility", "risk", "learning")
FLOOR_DIMENSIONS = DIMENSIONS[:5]  # the floor applies to the first five only
GATE_ORDER = ("evidence", "feasibility", "risk", "duplicate")

GO = "GO"
PIVOT = "PIVOT"
NO_GO = "NO-GO"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


class InputError(ValueError):
    """The request is malformed. Callers should return HTTP 422."""


class ConfigError(ValueError):
    """The rules (ConfigMap) are inconsistent. The service must report not-ready."""


# --------------------------------------------------------------------------- config
def validate_config(cfg: dict) -> None:
    try:
        presets = cfg["weight_presets"]
        th = cfg["thresholds"]
        cfg["gates"], cfg["sensitivity"], cfg["challenge"]
    except KeyError as e:
        raise ConfigError(f"missing config section: {e}") from e
    for goal, w in presets.items():
        if set(w) != set(DIMENSIONS):
            raise ConfigError(f"preset '{goal}' must define exactly {DIMENSIONS}")
        if abs(sum(w.values()) - 100) > 1e-9:
            raise ConfigError(f"preset '{goal}' weights must add to 100")
    if not th["T_no"] < th["T_go"]:
        raise ConfigError("T_no must be lower than T_go")
    if not 0 <= th["min_confidence"] <= 1:
        raise ConfigError("min_confidence must be in [0, 1]")


# --------------------------------------------------------------------------- maths
def weighted_score(values: dict[str, float], weights: dict[str, float]) -> float:
    """Sum of weight x score, scaled to 0..100 (scores are 0..5)."""
    total_w = sum(weights[d] for d in DIMENSIONS)
    raw = sum(weights[d] * values[d] for d in DIMENSIONS)
    return round(raw / total_w * 20, 6)


def shift_weight(weights: dict[str, float], dim: str, factor: float) -> dict[str, float]:
    """Scale one weight by `factor` and share the difference over the others pro rata."""
    new = dict(weights)
    new[dim] = weights[dim] * factor
    freed = weights[dim] - new[dim]
    others_total = sum(w for d, w in weights.items() if d != dim)
    if others_total == 0:
        return new
    for d, w in weights.items():
        if d != dim:
            new[d] = w + freed * (w / others_total)
    return new


def classify(values: dict[str, float], weights: dict[str, float], th: dict) -> str:
    """GO / PIVOT / NO-GO for an idea that already passed every gate."""
    score = weighted_score(values, weights)
    breach = any(values[d] < th["floor"] for d in FLOOR_DIMENSIONS)
    if score >= th["T_go"] and not breach:
        return GO
    if score >= th["T_no"]:
        return PIVOT
    return NO_GO


def overall_confidence(confidences: dict[str, float], n_sources: int) -> float:
    mean_conf = sum(confidences[d] for d in DIMENSIONS) / len(DIMENSIONS)
    return round(0.7 * mean_conf + 0.3 * min(1.0, n_sources / 5), 6)


# --------------------------------------------------------------------- validation
def _validate_request(req: dict, cfg: dict) -> tuple[dict, dict, dict]:
    scores = req.get("scores")
    if not isinstance(scores, dict):
        raise InputError("'scores' must be an object with six dimensions")
    for d in DIMENSIONS:
        s = scores.get(d)
        if not isinstance(s, dict):
            raise InputError(f"missing score for '{d}'")
        for key, lo, hi in (("score", 0, 5), ("confidence", 0, 1)):
            v = s.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise InputError(f"'{d}.{key}' must be a number in [{lo}, {hi}]")
        ids = s.get("evidence_ids")
        if not isinstance(ids, list):
            raise InputError(f"'{d}.evidence_ids' must be a list")
        if cfg.get("require_evidence_ids", True) and not ids:
            raise InputError(f"'{d}' has no evidence ids: the scorer must abstain, not score")
    profile = req.get("profile") or {}
    for key in ("goal", "hours_per_week", "weeks_available"):
        if key not in profile:
            raise InputError(f"profile.{key} is required")
    if profile["goal"] not in cfg["weight_presets"]:
        raise InputError(f"unknown goal '{profile['goal']}'")
    gi = req.get("gate_inputs") or {}
    for key in ("n_sources", "n_platforms", "estimated_build_hours"):
        if not isinstance(gi.get(key), (int, float)) or isinstance(gi.get(key), bool):
            raise InputError(f"gate_inputs.{key} must be a number")
    return scores, profile, gi


# ----------------------------------------------------------------------- gates
def check_gates(scores: dict, profile: dict, gi: dict, cfg: dict) -> tuple[dict, dict, dict]:
    g = cfg["gates"]
    hours_available = profile["hours_per_week"] * profile["weeks_available"]
    blockers = list(gi.get("risk_blockers") or [])
    dup = gi.get("duplicate_product")
    diff = scores["differentiation"]["score"]

    gates = {
        "evidence": "pass" if gi["n_sources"] >= g["min_sources"] and gi["n_platforms"] >= g["min_platforms"] else "fail",
        "feasibility": "pass" if gi["estimated_build_hours"] <= hours_available else "fail",
        "risk": "pass" if not blockers else "fail",
        "duplicate": "pass" if (not dup or diff >= g["duplicate_min_differentiation"]) else "fail",
    }
    reasons = {
        "evidence": f"{gi['n_sources']} source(s) on {gi['n_platforms']} platform(s); need {g['min_sources']}+ on {g['min_platforms']}+",
        "feasibility": f"build effort {gi['estimated_build_hours']}h vs {hours_available}h available"
        + (f" (gap {gi['estimated_build_hours'] - hours_available}h)" if gates["feasibility"] == "fail" else ""),
        "risk": ("blocker(s): " + "; ".join(blockers)) if blockers else "no blocker named",
        "duplicate": f"existing product: {dup}" if dup else "no same-user clone found",
    }
    missing: dict[str, Any] = {}
    if gates["evidence"] == "fail":
        missing = {
            "sources": {"have": gi["n_sources"], "need": g["min_sources"]},
            "platforms": {"have": gi["n_platforms"], "need": g["min_platforms"]},
        }
    return gates, reasons, missing


# ------------------------------------------------------------------ sensitivity
def sensitivity(values: dict[str, float], confidences: dict[str, float], weights: dict[str, float],
                base: str, cfg: dict) -> dict:
    """Move each weight up and down by 20% and the least confident score by one point."""
    th, sens = cfg["thresholds"], cfg["sensitivity"]
    runs, flips = 0, []
    for d in DIMENSIONS:
        for sign, label in ((-1, "down"), (1, "up")):
            runs += 1
            v = classify(values, shift_weight(weights, d, 1 + sign * sens["weight_delta"]), th)
            if v != base:
                flips.append({"change": f"{d} weight {label} {int(sens['weight_delta'] * 100)}%", "verdict": v})
    least = min(DIMENSIONS, key=lambda d: (confidences[d], DIMENSIONS.index(d)))
    for sign, label in ((-1, "down"), (1, "up")):
        runs += 1
        moved = dict(values)
        moved[least] = min(5.0, max(0.0, values[least] + sign * sens["score_delta"]))
        v = classify(moved, weights, th)
        if v != base:
            flips.append({"change": f"{least} score {label} {sens['score_delta']:g} (least confident)", "verdict": v})
    return {"runs": runs, "flipped": len(flips), "flips": flips}


def _stability(sens: dict) -> str:
    return "BORDERLINE" if sens["flipped"] else "STABLE"


# ----------------------------------------------------------- what would make GO
def what_would_make_go(values: dict[str, float], confidences: dict[str, float], weights: dict[str, float],
                       cfg: dict, step: float = 0.5, limit: int = 3) -> list[dict]:
    """Smallest single-dimension increase per dimension that gives a stable GO."""
    th = cfg["thresholds"]
    found = []
    for d in DIMENSIONS:
        delta = step
        while values[d] + delta <= 5.0 + 1e-9:
            moved = dict(values)
            moved[d] = round(values[d] + delta, 6)
            if classify(moved, weights, th) == GO:
                s = sensitivity(moved, confidences, weights, GO, cfg)
                if s["flipped"] == 0:
                    found.append({
                        "dimension": d, "from": values[d], "to": moved[d], "delta": round(delta, 6),
                        "change": f"Raise {d} from {values[d]:g} to {moved[d]:g}",
                        "new_score": weighted_score(moved, weights), "new_verdict": GO, "stability": "STABLE",
                    })
                    break
            delta += step
    found.sort(key=lambda c: (c["delta"], DIMENSIONS.index(c["dimension"])))
    return found[:limit]


# ----------------------------------------------------------------------- decide
def decide(req: dict, cfg: dict) -> dict:
    validate_config(cfg)
    scores, profile, gi = _validate_request(req, cfg)
    th = cfg["thresholds"]
    weights = dict(cfg["weight_presets"][profile["goal"]])
    values = {d: float(scores[d]["score"]) for d in DIMENSIONS}
    confs = {d: float(scores[d]["confidence"]) for d in DIMENSIONS}
    weakest = min(DIMENSIONS, key=lambda d: (values[d], DIMENSIONS.index(d)))

    gates, gate_reasons, missing = check_gates(scores, profile, gi, cfg)
    confidence = overall_confidence(confs, int(gi["n_sources"]))
    failing = [g for g in GATE_ORDER if gates[g] == "fail"]

    out: dict[str, Any] = {
        "idea_id": req.get("idea_id"), "version": req.get("version", 1), "run_id": req.get("run_id"),
        "verdict": None, "stability": None, "score": None, "confidence": confidence,
        "gates": gates, "gate_reasons": gate_reasons, "missing": missing,
        "weights": weights, "thresholds": {k: th[k] for k in ("T_go", "T_no", "floor")},
        "scores": [{"dimension": d, **scores[d]} for d in DIMENSIONS],
        "weakest_dimension": weakest, "what_would_make_go": [],
        "sensitivity": None, "reasons": [],
        "versions": {"engine": ENGINE_VERSION, "rubrics": req.get("rubric_version"),
                     "profile_weights": cfg.get("config_version")},
    }

    if failing:  # a failed gate decides, whatever the score
        first = failing[0]
        out["verdict"] = INSUFFICIENT if first == "evidence" else NO_GO
        out["reasons"] = [f"{g} gate failed: {gate_reasons[g]}" for g in failing]
        return out

    out["score"] = weighted_score(values, weights)
    if confidence < th["min_confidence"]:
        out["verdict"] = INSUFFICIENT
        out["reasons"] = [f"confidence {confidence:.2f} is below {th['min_confidence']}: not enough support to decide"]
        return out

    verdict = classify(values, weights, th)
    sens = sensitivity(values, confs, weights, verdict, cfg)
    out.update(verdict=verdict, stability=_stability(sens), sensitivity=sens)
    breach = [d for d in FLOOR_DIMENSIONS if values[d] < th["floor"]]
    if verdict == GO:
        out["reasons"] = [f"score {out['score']:.1f} >= T_go {th['T_go']} and no dimension below floor"]
    elif verdict == PIVOT:
        out["reasons"] = ([f"below floor {th['floor']}: {', '.join(breach)}"] if breach
                          else [f"score {out['score']:.1f} is between T_no {th['T_no']} and T_go {th['T_go']}"])
        out["reasons"].append(f"weakest dimension: {weakest}")
    else:
        out["reasons"] = [f"score {out['score']:.1f} is below T_no {th['T_no']}"]
    if verdict != GO or out["stability"] == "BORDERLINE":
        out["what_would_make_go"] = what_would_make_go(values, confs, weights, cfg)
    return out


# ------------------------------------------------------------ what-if / challenge
def whatif(req: dict, changes: dict, cfg: dict) -> dict:
    """Apply score and/or gate-input overrides and return the next version."""
    new = deepcopy(req)
    for dim, val in (changes.get("scores") or {}).items():
        if dim not in DIMENSIONS:
            raise InputError(f"unknown dimension '{dim}'")
        new["scores"][dim]["score"] = val
    new.setdefault("gate_inputs", {}).update(changes.get("gate_inputs") or {})
    new.setdefault("profile", {}).update(changes.get("profile") or {})
    new["version"] = int(req.get("version", 1)) + 1
    return decide(new, cfg)


def apply_challenge(scores: dict, objections: list[dict], cfg: dict) -> dict:
    """Each critic-accepted objection: score -0.5 (max -1.0 per dimension), confidence -0.1."""
    c = cfg["challenge"]
    out = deepcopy(scores)
    accepted: dict[str, int] = {}
    for o in objections:
        if o.get("accepted") and o.get("dimension") in DIMENSIONS:
            accepted[o["dimension"]] = accepted.get(o["dimension"], 0) + 1
    for d, n in accepted.items():
        out[d]["score"] = round(max(0.0, out[d]["score"] - min(c["max_score_penalty"], n * c["score_penalty"])), 6)
        out[d]["confidence"] = round(max(0.0, out[d]["confidence"] - n * c["confidence_penalty"]), 6)
    return out
