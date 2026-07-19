"""
Unit tests for bin/generate_report.py. Fully offline; no LLM, no pipeline.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "generate_report.py"
_spec = importlib.util.spec_from_file_location("generate_report", _BIN)
gr = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(gr)


def _summary(variants=None):
    variants = variants if variants is not None else [
        {"tier": 1, "chrom": "testchr", "pos": 100, "ref": "C", "alt": "T",
         "gene": "TESTG", "impact": "HIGH", "effect": "stop_gained",
         "hgvs_p": "p.Arg1Ter", "genotype": "het", "filter": "PASS"},
        {"tier": 2, "chrom": "testchr", "pos": 150, "ref": "G", "alt": "A",
         "gene": "TESTG", "impact": "MODERATE", "effect": "missense_variant",
         "hgvs_p": "p.Gly2Ser", "genotype": "hom_alt", "filter": "PASS"},
    ]
    counts = {str(t): sum(1 for v in variants if v["tier"] == t) for t in (1, 2, 3, 4)}
    return {"sample": "sample1", "variants": variants, "tier_counts": counts,
            "total_variants": len(variants)}


def _write_summary(tmp_path, summary):
    p = tmp_path / "prioritized.json"
    p.write_text(json.dumps(summary), encoding="utf-8")
    return p


# --- narrative -------------------------------------------------------------

def test_narrative_mentions_counts_and_genes():
    text = gr.build_narrative(_summary())
    assert "2 variant(s)" in text
    assert "1 were predicted HIGH impact" in text
    assert "TESTG" in text


def test_narrative_empty():
    assert "No variants" in gr.build_narrative(_summary(variants=[]))


def test_llm_hook_falls_back_without_backend():
    s = _summary()
    # With --llm requested but no backend, must equal the templated narrative
    # (no fabrication).
    assert gr.maybe_llm_narrative(s, enable_llm=True) == gr.build_narrative(s)


# --- HTML ------------------------------------------------------------------

def test_html_contains_disclaimer_and_rows():
    doc = gr.render_html(_summary(), "narrative here")
    assert "RESEARCH USE ONLY" in doc
    assert "TESTG" in doc
    assert "<table" in doc
    assert "narrative here" in doc


def test_html_escapes_malicious_fields():
    bad = _summary(variants=[{
        "tier": 1, "chrom": "c", "pos": 1, "ref": "A", "alt": "T",
        "gene": "<script>alert(1)</script>", "impact": "HIGH", "effect": "x",
        "hgvs_p": "", "genotype": "het", "filter": "PASS"}])
    doc = gr.render_html(bad, "n")
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;" in doc


def test_html_empty_variants_placeholder():
    doc = gr.render_html(_summary(variants=[]), "none")
    assert "No variants reported" in doc


# --- FHIR ------------------------------------------------------------------

def test_fhir_bundle_structure():
    bundle = gr.build_fhir(_summary())
    assert bundle["resourceType"] == "Bundle"
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert types[0] == "DiagnosticReport"
    assert types.count("Observation") == 2
    report = bundle["entry"][0]["resource"]
    assert "RESEARCH USE ONLY" in report["conclusion"]
    assert len(report["result"]) == 2   # references match observation count


def test_fhir_empty_variants():
    bundle = gr.build_fhir(_summary(variants=[]))
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert types == ["DiagnosticReport"]


# --- IO / CLI --------------------------------------------------------------

def test_write_reports_creates_three_files(tmp_path):
    s = _summary()
    prefix = tmp_path / "out" / "sample1"
    gr.write_reports(s, gr.build_narrative(s), prefix)
    assert (tmp_path / "out" / "sample1.report.html").is_file()
    assert (tmp_path / "out" / "sample1.report.json").is_file()
    assert (tmp_path / "out" / "sample1.fhir.json").is_file()
    payload = json.loads((tmp_path / "out" / "sample1.report.json").read_text())
    assert payload["total_variants"] == 2


def test_main_cli_success_and_missing(tmp_path):
    s = _summary()
    src = _write_summary(tmp_path, s)
    assert gr.main([str(src), "--prefix", str(tmp_path / "r" / "sample1")]) == 0
    assert (tmp_path / "r" / "sample1.report.html").is_file()
    assert gr.main([str(tmp_path / "nope.json"), "--prefix", str(tmp_path / "x")]) == 1


def test_report_json_roundtrip_valid(tmp_path):
    s = _summary()
    gr.write_reports(s, "n", tmp_path / "s1")
    fhir = json.loads((tmp_path / "s1.fhir.json").read_text())
    # valid JSON + expected top-level shape
    assert fhir["type"] == "collection"
