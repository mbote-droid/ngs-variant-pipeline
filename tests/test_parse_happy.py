"""
Unit tests for bin/parse_happy.py (H4). Offline; no hap.py needed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "parse_happy.py"
_spec = importlib.util.spec_from_file_location("parse_happy", _BIN)
ph = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(ph)

# A minimal hap.py-style summary.csv (PASS + ALL rows for SNP and INDEL).
_SUMMARY = (
    "Type,Filter,TRUTH.TOTAL,TRUTH.TP,TRUTH.FN,QUERY.TOTAL,QUERY.FP,QUERY.UNK,"
    "METRIC.Recall,METRIC.Precision,METRIC.F1_Score\n"
    "INDEL,ALL,50,45,5,60,10,5,0.9,0.8,0.847\n"
    "INDEL,PASS,50,40,10,55,8,5,0.8,0.833333,0.816327\n"
    "SNP,ALL,100,95,5,110,7,3,0.95,0.93,0.94\n"
    "SNP,PASS,100,90,10,105,5,3,0.9,0.947368,0.923077\n"
)


def _write(tmp_path):
    p = tmp_path / "happy.summary.csv"
    p.write_text(_SUMMARY, encoding="utf-8")
    return p


def test_parse_pass_rows(tmp_path):
    metrics = ph.parse_summary(_write(tmp_path), "PASS")
    assert metrics["SNP"]["tp"] == 90 and metrics["SNP"]["fn"] == 10
    assert metrics["SNP"]["fp"] == 5
    # Prefers hap.py's own precision column.
    assert abs(metrics["SNP"]["precision"] - 0.947368) < 1e-5
    assert metrics["INDEL"]["tp"] == 40


def test_all_is_combined(tmp_path):
    metrics = ph.parse_summary(_write(tmp_path), "PASS")
    allm = metrics["ALL"]
    assert allm["tp"] == 130          # 90 + 40
    assert allm["fp"] == 13           # 5 + 8
    assert allm["fn"] == 20           # 10 + 10
    assert abs(allm["precision"] - 130 / 143) < 1e-6
    assert abs(allm["recall"] - 130 / 150) < 1e-6


def test_filter_level_switch(tmp_path):
    all_level = ph.parse_summary(_write(tmp_path), "ALL")
    assert all_level["SNP"]["tp"] == 95   # the ALL row, not PASS


def test_fallback_computes_when_metric_missing(tmp_path):
    csv_text = (
        "Type,Filter,TRUTH.TP,TRUTH.FN,QUERY.FP\n"
        "SNP,PASS,90,10,10\n"
    )
    p = tmp_path / "s.csv"
    p.write_text(csv_text)
    m = ph.parse_summary(p, "PASS")["SNP"]
    assert m["precision"] == 0.9 and m["recall"] == 0.9  # 90/100 both


def test_main_cli(tmp_path):
    src = _write(tmp_path)
    js, ts = tmp_path / "o.json", tmp_path / "o.tsv"
    assert ph.main([str(src), "--json", str(js), "--tsv", str(ts)]) == 0
    data = json.loads(js.read_text())
    assert data["tool"] == "hap.py"
    assert data["metrics"]["ALL"]["tp"] == 130
    assert ts.read_text().splitlines()[0].startswith("class\t")
    assert ph.main([str(tmp_path / "no.csv"), "--json", str(js), "--tsv", str(ts)]) == 1
