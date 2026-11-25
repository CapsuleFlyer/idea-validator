"""Unit tests for M11. Run from services/verdict:  python -m pytest -q   (or python -m unittest)."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from src import engine as e

CFG = json.loads((Path(__file__).resolve().parents[3] / "config" / "verdict.json").read_text())


def make_request(values=None, confs=None, goal="portfolio", n_sources=5, n_platforms=3,
                 build_hours=100, hours_per_week=10, weeks=12, blockers=None, duplicate=None):
    values = values or {d: 3.0 for d in e.DIMENSIONS}
    confs = confs or {d: 0.8 for d in e.DIMENSIONS}
    return {
        "idea_id": "idea_t", "version": 1, "run_id": "run_t",
        "scores": {d: {"score": values[d], "confidence": confs[d], "evidence_ids": [f"card_x#{i}"]}
                   for i, d in enumerate(e.DIMENSIONS)},
        "profile": {"goal": goal, "hours_per_week": hours_per_week, "weeks_available": weeks},
        "gate_inputs": {"n_sources": n_sources, "n_platforms": n_platforms,
                        "estimated_build_hours": build_hours, "risk_blockers": blockers or [],
                        "duplicate_product": duplicate},
    }


def uniform(x):
    return {d: x for d in e.DIMENSIONS}


# The worked example from the project description (section 5.4).
EXAMPLE_VALUES = {"demand_pain": 3.5, "competition": 2.0, "differentiation": 3.0,
                  "feasibility": 4.0, "risk": 3.5, "learning": 4.5}
EXAMPLE_CONFS = {"demand_pain": 0.7, "competition": 0.6, "differentiation": 0.7,
                 "feasibility": 0.8, "risk": 0.8, "learning": 0.8}


class WorkedExample(unittest.TestCase):
    def setUp(self):
        self.req = make_request(EXAMPLE_VALUES, EXAMPLE_CONFS)

    def test_weighted_score_is_70_5(self):
        w = CFG["weight_presets"]["portfolio"]
        self.assertEqual(e.weighted_score(EXAMPLE_VALUES, w), 70.5)

    def test_first_result_is_go_but_borderline(self):
        out = e.decide(self.req, CFG)
        self.assertEqual(out["verdict"], e.GO)
        self.assertEqual(out["score"], 70.5)
        self.assertEqual(out["stability"], "BORDERLINE")
        self.assertEqual(out["sensitivity"]["runs"], 14)

    def test_feasibility_weight_down_20_percent_flips_to_pivot(self):
        w = e.shift_weight(CFG["weight_presets"]["portfolio"], "feasibility", 0.8)
        self.assertAlmostEqual(w["feasibility"], 20.0)
        self.assertAlmostEqual(sum(w.values()), 100.0)
        self.assertAlmostEqual(e.weighted_score(EXAMPLE_VALUES, w), 69.87, places=2)
        flips = e.decide(self.req, CFG)["sensitivity"]["flips"]
        self.assertTrue(any("feasibility weight down" in f["change"] and f["verdict"] == e.PIVOT for f in flips))

    def test_competition_3_gives_73_5_stable_go(self):
        out = e.whatif(self.req, {"scores": {"competition": 3.0}}, CFG)
        self.assertEqual(out["score"], 73.5)
        self.assertEqual(out["verdict"], e.GO)
        self.assertEqual(out["stability"], "STABLE")
        self.assertEqual(out["version"], 2)

    def test_what_would_make_go_suggestions_are_stable_go(self):
        out = e.decide(self.req, CFG)
        self.assertTrue(out["what_would_make_go"])
        for c in out["what_would_make_go"]:
            applied = e.whatif(self.req, {"scores": {c["dimension"]: c["to"]}}, CFG)
            self.assertEqual((applied["verdict"], applied["stability"]), (e.GO, "STABLE"))


class Gates(unittest.TestCase):
    def test_evidence_gate_needs_sources_and_platforms(self):
        for n_src, n_plat in ((2, 2), (5, 1)):
            out = e.decide(make_request(uniform(5), n_sources=n_src, n_platforms=n_plat), CFG)
            self.assertEqual(out["verdict"], e.INSUFFICIENT)
            self.assertEqual(out["gates"]["evidence"], "fail")
            self.assertIsNone(out["score"])  # not scored, does not guess
            self.assertTrue(out["missing"])

    def test_evidence_gate_edge_passes(self):
        out = e.decide(make_request(uniform(5), n_sources=3, n_platforms=2), CFG)
        self.assertEqual(out["gates"]["evidence"], "pass")

    def test_feasibility_gate_edge(self):
        ok = e.decide(make_request(uniform(5), build_hours=120, hours_per_week=10, weeks=12), CFG)
        self.assertEqual(ok["gates"]["feasibility"], "pass")
        bad = e.decide(make_request(uniform(5), build_hours=121, hours_per_week=10, weeks=12), CFG)
        self.assertEqual(bad["verdict"], e.NO_GO)
        self.assertIn("gap 1h", bad["gate_reasons"]["feasibility"])

    def test_risk_gate_names_blocker(self):
        out = e.decide(make_request(uniform(5), blockers=["stores health data"]), CFG)
        self.assertEqual(out["verdict"], e.NO_GO)
        self.assertIn("stores health data", out["reasons"][0])

    def test_duplicate_gate_fails_unless_differentiation_3(self):
        v = uniform(4.0)
        v["differentiation"] = 2.5
        out = e.decide(make_request(v, duplicate="Acme"), CFG)
        self.assertEqual(out["verdict"], e.NO_GO)
        self.assertIn("Acme", out["reasons"][0])
        v["differentiation"] = 3.0
        out = e.decide(make_request(v, duplicate="Acme"), CFG)
        self.assertEqual(out["gates"]["duplicate"], "pass")

    def test_evidence_gate_beats_other_failures(self):
        out = e.decide(make_request(uniform(5), n_sources=1, build_hours=9999, blockers=["x"]), CFG)
        self.assertEqual(out["verdict"], e.INSUFFICIENT)
        self.assertEqual(len(out["reasons"]), 3)

    def test_failed_gate_decides_whatever_the_score(self):
        out = e.decide(make_request(uniform(5), blockers=["illegal"]), CFG)
        self.assertEqual(out["verdict"], e.NO_GO)


class Thresholds(unittest.TestCase):
    def verdict(self, x, **kw):
        return e.decide(make_request(uniform(x), **kw), CFG)["verdict"]

    def test_exactly_t_go_is_go(self):
        self.assertEqual(self.verdict(3.5), e.GO)  # 70.0

    def test_just_below_t_go_is_pivot(self):
        self.assertEqual(self.verdict(3.49), e.PIVOT)

    def test_exactly_t_no_is_pivot(self):
        self.assertEqual(self.verdict(2.5), e.PIVOT)  # 50.0

    def test_just_below_t_no_is_no_go(self):
        self.assertEqual(self.verdict(2.49), e.NO_GO)

    def test_floor_breach_gives_pivot_and_names_weakest(self):
        v = uniform(4.5)
        v["competition"] = 1.4
        out = e.decide(make_request(v), CFG)
        self.assertGreaterEqual(out["score"], 70)
        self.assertEqual(out["verdict"], e.PIVOT)
        self.assertEqual(out["weakest_dimension"], "competition")

    def test_floor_does_not_apply_to_learning(self):
        v = uniform(4.5)
        v["learning"] = 0.0
        out = e.decide(make_request(v, goal="startup"), CFG)  # learning weight is only 5
        self.assertEqual(out["verdict"], e.GO)

    def test_floor_value_exactly_is_not_a_breach(self):
        v = uniform(4.5)
        v["risk"] = 1.5
        self.assertEqual(e.decide(make_request(v), CFG)["verdict"], e.GO)


class Confidence(unittest.TestCase):
    def test_formula(self):
        confs = uniform(0.6)
        self.assertAlmostEqual(e.overall_confidence(confs, 2), 0.7 * 0.6 + 0.3 * 0.4)
        self.assertAlmostEqual(e.overall_confidence(confs, 50), 0.7 * 0.6 + 0.3)

    def test_low_confidence_abstains(self):
        out = e.decide(make_request(uniform(5), confs=uniform(0.1), n_sources=3), CFG)
        self.assertLess(out["confidence"], 0.5)
        self.assertEqual(out["verdict"], e.INSUFFICIENT)
        self.assertIsNone(out["stability"])


class Sensitivity(unittest.TestCase):
    def test_clear_go_is_stable(self):
        out = e.decide(make_request(uniform(4.8)), CFG)
        self.assertEqual((out["verdict"], out["stability"]), (e.GO, "STABLE"))
        self.assertEqual(out["sensitivity"]["flipped"], 0)

    def test_shift_weight_keeps_total_100(self):
        w = e.shift_weight(CFG["weight_presets"]["startup"], "demand_pain", 1.2)
        self.assertAlmostEqual(sum(w.values()), 100.0)
        self.assertAlmostEqual(w["demand_pain"], 30.0)

    def test_least_confident_score_moves_by_one_point(self):
        confs = uniform(0.9)
        confs["learning"] = 0.4
        out = e.decide(make_request(uniform(3.6), confs=confs), CFG)  # 72.0, one point = 4 pts for learning
        self.assertTrue(any("learning score down" in f["change"] for f in out["sensitivity"]["flips"]))


class WhatIfAndChallenge(unittest.TestCase):
    def test_whatif_bumps_version_and_does_not_mutate_input(self):
        req = make_request(EXAMPLE_VALUES, EXAMPLE_CONFS)
        before = deepcopy(req)
        out = e.whatif(req, {"scores": {"competition": 4.0}}, CFG)
        self.assertEqual(out["version"], 2)
        self.assertEqual(req, before)

    def test_whatif_can_change_gate_inputs(self):
        req = make_request(uniform(4), build_hours=500)
        self.assertEqual(e.decide(req, CFG)["verdict"], e.NO_GO)
        out = e.whatif(req, {"gate_inputs": {"estimated_build_hours": 80}}, CFG)
        self.assertEqual(out["verdict"], e.GO)

    def test_challenge_penalties_and_cap(self):
        scores = make_request()["scores"]
        out = e.apply_challenge(scores, [{"dimension": "risk", "accepted": True}] * 3
                                + [{"dimension": "demand_pain", "accepted": False}], CFG)
        self.assertEqual(out["risk"]["score"], 2.0)        # capped at -1.0
        self.assertAlmostEqual(out["risk"]["confidence"], 0.5)  # 3 x 0.1
        self.assertEqual(out["demand_pain"]["score"], 3.0)  # unsupported objection discarded


class Determinism(unittest.TestCase):
    def test_same_input_same_output(self):
        req = make_request(EXAMPLE_VALUES, EXAMPLE_CONFS)
        self.assertEqual(json.dumps(e.decide(req, CFG), sort_keys=True),
                         json.dumps(e.decide(deepcopy(req), CFG), sort_keys=True))

    def test_profile_changes_verdict(self):
        solo = make_request(uniform(4), build_hours=100, hours_per_week=2, weeks=10)    # 20 h
        team = make_request(uniform(4), build_hours=100, hours_per_week=20, weeks=10)   # 200 h
        self.assertEqual(e.decide(solo, CFG)["verdict"], e.NO_GO)
        self.assertEqual(e.decide(team, CFG)["verdict"], e.GO)


class Validation(unittest.TestCase):
    def test_missing_dimension(self):
        req = make_request()
        del req["scores"]["risk"]
        with self.assertRaises(e.InputError):
            e.decide(req, CFG)

    def test_out_of_range_score(self):
        req = make_request()
        req["scores"]["risk"]["score"] = 6
        with self.assertRaises(e.InputError):
            e.decide(req, CFG)

    def test_score_without_evidence_ids_is_rejected(self):
        req = make_request()
        req["scores"]["demand_pain"]["evidence_ids"] = []
        with self.assertRaises(e.InputError):
            e.decide(req, CFG)

    def test_unknown_goal(self):
        with self.assertRaises(e.InputError):
            e.decide(make_request(goal="fame"), CFG)

    def test_config_weights_must_add_to_100(self):
        bad = deepcopy(CFG)
        bad["weight_presets"]["startup"]["risk"] = 50
        with self.assertRaises(e.ConfigError):
            e.validate_config(bad)

    def test_config_thresholds_ordered(self):
        bad = deepcopy(CFG)
        bad["thresholds"]["T_no"] = 80
        with self.assertRaises(e.ConfigError):
            e.validate_config(bad)


if __name__ == "__main__":
    unittest.main()
