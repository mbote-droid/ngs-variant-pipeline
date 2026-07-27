"""
Unit tests for bin/eval_prioritizer.py (prioritizer-as-classifier eval). Offline.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "eval_prioritizer.py"
_spec = importlib.util.spec_from_file_location("eval_prioritizer", _BIN)
ep = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(ep)


# --- labels & scores -------------------------------------------------------

def test_label_of():
    assert ep.label_of({"clinvar_sig": "Pathogenic"}) == 1
    assert ep.label_of({"clinvar_sig": "Likely pathogenic"}) == 1
    assert ep.label_of({"clinvar_sig": "Benign"}) == 0
    assert ep.label_of({"clinvar_sig": "Uncertain significance"}) is None
    assert ep.label_of({"clinvar_sig": "Conflicting interpretations of pathogenicity"}) is None
    assert ep.label_of({}) is None


def test_score_of_modes():
    assert ep.score_of({"impact": "HIGH"}, "impact") == 3.0
    assert ep.score_of({"impact": "MODIFIER"}, "impact") == 0.0
    # rarity nudges a rare variant above a common one at the same impact
    rare = ep.score_of({"impact": "MODERATE", "gnomad_af": 1e-5}, "impact")
    common = ep.score_of({"impact": "MODERATE", "gnomad_af": 0.3}, "impact")
    assert rare > common > 2.0
    assert ep.score_of({"tier": 1}, "tier") == 4.0
    assert ep.score_of({"acmg_classification": "Pathogenic"}, "acmg") == 4.0


# --- ranking / AUC math ----------------------------------------------------

def test_avg_ranks_ties():
    assert ep._avg_ranks([10, 10, 20]) == [1.5, 1.5, 3.0]
    assert ep._avg_ranks([5, 1, 3]) == [3.0, 1.0, 2.0]


def test_roc_auc_perfect_and_reversed():
    perfect = [(1.0, 1), (1.0, 1), (0.0, 0), (0.0, 0)]
    assert ep.roc_auc(perfect) == 1.0
    reversed_ = [(0.0, 1), (0.0, 1), (1.0, 0), (1.0, 0)]
    assert ep.roc_auc(reversed_) == 0.0


def test_roc_auc_ties_are_half():
    # all identical scores -> no discrimination -> 0.5
    tied = [(1.0, 1), (1.0, 0), (1.0, 1), (1.0, 0)]
    assert ep.roc_auc(tied) == 0.5


def test_roc_auc_single_class_none():
    assert ep.roc_auc([(1.0, 1), (2.0, 1)]) is None


def test_average_precision_perfect():
    _, pr = ep.curves([(2.0, 1), (2.0, 1), (1.0, 0), (1.0, 0)])
    assert ep.average_precision(pr) == 1.0


# --- evaluate() ------------------------------------------------------------

def _variants():
    v = []
    for _ in range(6):
        v.append({"impact": "HIGH", "clinvar_sig": "Pathogenic", "gnomad_af": 1e-5})
    for _ in range(6):
        v.append({"impact": "MODIFIER", "clinvar_sig": "Benign", "gnomad_af": 0.2})
    v.append({"impact": "MODERATE", "clinvar_sig": "Uncertain significance"})  # excluded
    return v


def test_evaluate_excludes_vus_and_scores_perfect():
    r = ep.evaluate(_variants(), "impact", "s1")
    assert r["n_labelled"] == 12          # the VUS is dropped
    assert r["n_pathogenic"] == 6 and r["n_benign"] == 6
    assert r["roc_auc"] == 1.0 and r["pr_auc"] == 1.0
    assert r["kind"] == "classifier"
    assert r["self_consistent"] is False   # impact does not use ClinVar


def test_evaluate_acmg_flagged_self_consistent():
    r = ep.evaluate(_variants(), "acmg", "s1")
    assert r["self_consistent"] is True


def test_evaluate_no_labels():
    r = ep.evaluate([{"impact": "HIGH"}], "impact", "s1")
    assert r["n_labelled"] == 0
    assert r["roc_auc"] is None and r["pr_auc"] is None


# --- CLI -------------------------------------------------------------------

def test_main_cli(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps({"sample": "s1", "variants": _variants()}))
    js, ts = tmp_path / "e.json", tmp_path / "e.tsv"
    assert ep.main([str(src), "--score", "impact", "--json", str(js), "--tsv", str(ts)]) == 0
    data = json.loads(js.read_text())
    assert data["roc_auc"] == 1.0
    assert ts.read_text().splitlines()[0] == "metric\tvalue"
    # missing input
    assert ep.main([str(tmp_path / "no.json"), "--json", str(js), "--tsv", str(ts)]) == 1
    # no-label input still succeeds (AUC undefined)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"variants": [{"impact": "HIGH"}]}))
    assert ep.main([str(empty), "--json", str(js), "--tsv", str(ts)]) == 0
