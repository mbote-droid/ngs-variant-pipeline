"""
Unit tests for bin/plot_accuracy.py (accuracy showcase SVGs). Offline; no
plotting library. Asserts the SVGs are well-formed and encode the right data.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "plot_accuracy.py"
_spec = importlib.util.spec_from_file_location("plot_accuracy", _BIN)
pa = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(pa)

_RESULT = {
    "sample": "HG-demo",
    "tool": "builtin",
    "metrics": {
        "ALL": {"tp": 19, "fp": 3, "fn": 3, "precision": 0.8636, "recall": 0.8636, "f1": 0.8636},
        "SNP": {"tp": 15, "fp": 2, "fn": 2, "precision": 0.882, "recall": 0.882, "f1": 0.882},
        "INDEL": {"tp": 4, "fp": 1, "fn": 1, "precision": 0.8, "recall": 0.8, "f1": 0.8},
    },
    "pr_curve": [
        {"threshold": 0.0, "precision": 0.86, "recall": 0.86, "tp": 19, "fp": 3, "fn": 3},
        {"threshold": 30.0, "precision": 1.0, "recall": 0.64, "tp": 14, "fp": 0, "fn": 8},
        {"threshold": 200.0, "precision": 1.0, "recall": 0.1, "tp": 2, "fp": 0, "fn": 20},
    ],
    "genotype": {
        "labels": ["het", "hom_alt", "hom_ref"],
        "matrix": {"het": {"het": 15, "hom_alt": 0, "hom_ref": 0},
                   "hom_alt": {"het": 1, "hom_alt": 3, "hom_ref": 0},
                   "hom_ref": {"het": 0, "hom_alt": 0, "hom_ref": 0}},
        "matched": 19, "concordant": 18, "concordance": 0.947,
    },
}


def _wellformed(svg: str):
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # tags balance (naive but catches truncation/typos)
    assert svg.count("<svg") == svg.count("</svg>") == 1
    assert svg.count("<text") == svg.count("</text>")


def test_pr_curve_svg():
    svg = pa.pr_curve_svg(_RESULT)
    _wellformed(svg)
    assert "Precision" in svg and "Recall" in svg
    assert "<polyline" in svg            # >=2 points -> a line
    assert svg.count("<circle") >= 3     # a marker per point (+ best-point ring)


def test_pr_curve_single_point_no_line():
    one = dict(_RESULT, pr_curve=[{"threshold": 0.0, "precision": 1.0, "recall": 1.0,
                                   "tp": 3, "fp": 0, "fn": 0}])
    svg = pa.pr_curve_svg(one)
    _wellformed(svg)
    assert "<polyline" not in svg        # a single point draws no connecting line


def test_f1_by_type_svg():
    svg = pa.f1_by_type_svg(_RESULT)
    _wellformed(svg)
    for cls in ("ALL", "SNP", "INDEL"):
        assert f">{cls}<" in svg
    # three metric colours present in the legend/bars
    for colour in (pa.C_BLUE, pa.C_ORANGE, pa.C_AQUA):
        assert colour in svg
    # a bar per metric per class = 9 rects at minimum (plus card + gridless)
    assert svg.count("<rect") >= 9


def test_genotype_confusion_svg():
    svg = pa.genotype_confusion_svg(_RESULT)
    _wellformed(svg)
    assert "concordance 0.947" in svg
    assert ">15<" in svg and ">3<" in svg    # diagonal counts rendered
    assert "Truth genotype" in svg and "Called genotype" in svg


def test_ramp_endpoints_and_clamp():
    assert pa._ramp(0.0).lower() == "#e8f1fc"
    assert pa._ramp(1.0).lower() == "#184f95"
    assert pa._ramp(5.0) == pa._ramp(1.0)     # clamps above 1
    assert pa._ramp(-1.0) == pa._ramp(0.0)    # clamps below 0


def test_write_plots_and_main(tmp_path):
    import json
    src = tmp_path / "b.json"
    src.write_text(json.dumps(_RESULT))
    assert pa.main([str(src), "--outdir", str(tmp_path / "p"), "--prefix", "s1"]) == 0
    for name in ("pr_curve", "f1_by_type", "genotype_confusion"):
        f = tmp_path / "p" / f"s1.{name}.svg"
        assert f.is_file()
        assert f.read_text().startswith("<svg")
    assert pa.main([str(tmp_path / "missing.json"), "--outdir", str(tmp_path)]) == 1


def test_no_unresolved_format_placeholders():
    # Guard against stray f-string/format leftovers in any chart.
    for fn in (pa.pr_curve_svg, pa.f1_by_type_svg, pa.genotype_confusion_svg):
        svg = fn(_RESULT)
        assert "{" not in svg and "}" not in svg


# --- classifier eval charts (ROC / PR-AUC) ---------------------------------

_EVAL = {
    "sample": "demo", "score_field": "impact", "self_consistent": False,
    "roc_auc": 0.84, "pr_auc": 0.87, "prevalence": 0.45, "kind": "classifier",
    "roc_curve": [{"fpr": 0.0, "tpr": 0.0, "threshold": None},
                  {"fpr": 0.1, "tpr": 0.6, "threshold": 3.0},
                  {"fpr": 0.4, "tpr": 0.9, "threshold": 2.0},
                  {"fpr": 1.0, "tpr": 1.0, "threshold": None}],
    "pr_curve": [{"recall": 0.6, "precision": 0.9, "threshold": 3.0},
                 {"recall": 0.9, "precision": 0.75, "threshold": 2.0}],
}


def test_roc_svg():
    svg = pa.roc_svg(_EVAL)
    _wellformed(svg)
    assert "ROC" in svg and "AUC 0.84" in svg
    assert "<polyline" in svg
    assert "stroke-dasharray" in svg     # chance diagonal


def test_pr_auc_svg_has_prevalence_baseline():
    svg = pa.pr_auc_svg(_EVAL)
    _wellformed(svg)
    assert "AP 0.87" in svg
    assert "stroke-dasharray" in svg     # prevalence no-skill line


def test_write_plots_routes_by_kind(tmp_path):
    written = pa.write_plots(_EVAL, tmp_path, "s1")
    names = {p.name for p in written}
    assert names == {"s1.roc.svg", "s1.pr_auc.svg"}      # classifier set, not benchmark
    written2 = pa.write_plots(_RESULT, tmp_path, "b1")
    assert {p.name for p in written2} == {
        "b1.pr_curve.svg", "b1.f1_by_type.svg", "b1.genotype_confusion.svg"}
