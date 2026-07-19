"""
Unit tests for bin/prioritize_variants.py. Fully offline; no pipeline needed.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "prioritize_variants.py"
_spec = importlib.util.spec_from_file_location("prioritize_variants", _BIN)
pv = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(pv)


VCF_HEADER = (
    "##fileformat=VCFv4.2\n"
    "##INFO=<ID=ANN,Number=.,Type=String,Description=\"SnpEff\">\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample1\n"
)


def _ann(effect, impact, gene, hgvs_p=""):
    # allele|effect|impact|gene|gene_id|feature|feat_id|biotype|rank|c|p|...
    return (f"ANN=A|{effect}|{impact}|{gene}|g1|transcript|t1|protein_coding|1/1|"
            f"c.1A>T|{hgvs_p}|||||")


def _row(pos, ref, alt, filt, info, gt="0/1", qual="50"):
    return f"testchr\t{pos}\t.\t{ref}\t{alt}\t{qual}\t{filt}\t{info}\tGT\t{gt}\n"


def _write_vcf(tmp_path, rows, gz=False):
    text = VCF_HEADER + "".join(rows)
    if gz:
        p = tmp_path / "in.vcf.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        p = tmp_path / "in.vcf"
        p.write_text(text, encoding="utf-8")
    return p


# --- ANN parsing -----------------------------------------------------------

def test_parse_ann_extracts_most_severe():
    info = _ann("missense_variant", "MODERATE", "TESTG", "p.Arg1Ter") + ";DP=30"
    ann = pv.parse_ann(info)
    assert ann["impact"] == "MODERATE"
    assert ann["gene_name"] == "TESTG"
    assert ann["hgvs_p"] == "p.Arg1Ter"


def test_parse_ann_takes_first_of_multiple():
    info = ("ANN=A|stop_gained|HIGH|G1|g1|transcript|t1|protein_coding|1/1|c.1A>T|p.X|||||"
            ",A|intron_variant|MODIFIER|G1|g1|transcript|t2|protein_coding||||||||")
    assert pv.parse_ann(info)["impact"] == "HIGH"


def test_parse_ann_absent_returns_empty():
    assert pv.parse_ann("DP=30;MQ=60") == {}


# --- genotype --------------------------------------------------------------

def test_genotype_het_hom_ref():
    assert pv._genotype("GT:DP", "0/1:30") == "het"
    assert pv._genotype("GT", "1|1") == "hom_alt"
    assert pv._genotype("GT", "0/0") == "hom_ref"
    assert pv._genotype("", "") == ""


# --- tiering ---------------------------------------------------------------

def test_assign_tier_by_impact_and_filter():
    assert pv.assign_tier({"impact": "HIGH", "passed": True}) == 1
    assert pv.assign_tier({"impact": "MODERATE", "passed": True}) == 2
    assert pv.assign_tier({"impact": "LOW", "passed": True}) == 3
    assert pv.assign_tier({"impact": "MODIFIER", "passed": True}) == 4
    # A HIGH-impact variant that failed a filter drops to tier 4.
    assert pv.assign_tier({"impact": "HIGH", "passed": False}) == 4


def test_prioritize_sorts_high_first(tmp_path):
    rows = [
        _row(200, "A", "T", "PASS", _ann("intron_variant", "MODIFIER", "G")),
        _row(100, "C", "T", "PASS", _ann("stop_gained", "HIGH", "G")),
        _row(150, "G", "A", "PASS", _ann("missense_variant", "MODERATE", "G")),
    ]
    variants = pv.prioritize(pv.parse_vcf(_write_vcf(tmp_path, rows)))
    assert [v["tier"] for v in variants] == [1, 2, 4]
    assert variants[0]["impact"] == "HIGH"


def test_failed_filter_ranked_last(tmp_path):
    rows = [
        _row(100, "C", "T", "QD2", _ann("stop_gained", "HIGH", "G")),   # failed
        _row(150, "G", "A", "PASS", _ann("missense_variant", "MODERATE", "G")),
    ]
    variants = pv.prioritize(pv.parse_vcf(_write_vcf(tmp_path, rows)))
    assert variants[0]["tier"] == 2       # PASS moderate beats failed high
    assert variants[1]["tier"] == 4
    assert variants[1]["passed"] is False


# --- IO --------------------------------------------------------------------

def test_reads_gzipped_vcf(tmp_path):
    rows = [_row(100, "C", "T", "PASS", _ann("stop_gained", "HIGH", "G"))]
    variants = pv.parse_vcf(_write_vcf(tmp_path, rows, gz=True))
    assert len(variants) == 1
    assert variants[0]["genotype"] == "het"


def test_write_json_has_summary_and_disclaimer(tmp_path):
    rows = [
        _row(100, "C", "T", "PASS", _ann("stop_gained", "HIGH", "G")),
        _row(150, "G", "A", "PASS", _ann("missense_variant", "MODERATE", "G")),
    ]
    variants = pv.prioritize(pv.parse_vcf(_write_vcf(tmp_path, rows)))
    out = tmp_path / "p.json"
    pv.write_json(variants, out, "sample1")
    data = json.loads(out.read_text())
    assert data["total_variants"] == 2
    assert data["tier_counts"]["1"] == 1
    assert "Research-use only" in data["disclaimer"]


def test_write_tsv_header_and_rows(tmp_path):
    rows = [_row(100, "C", "T", "PASS", _ann("stop_gained", "HIGH", "TESTG", "p.X"))]
    variants = pv.prioritize(pv.parse_vcf(_write_vcf(tmp_path, rows)))
    out = tmp_path / "p.tsv"
    pv.write_tsv(variants, out)
    lines = out.read_text().splitlines()
    assert lines[0].split("\t")[0] == "tier"
    assert "TESTG" in lines[1]


def test_main_cli(tmp_path):
    rows = [_row(100, "C", "T", "PASS", _ann("stop_gained", "HIGH", "G"))]
    vcf = _write_vcf(tmp_path, rows)
    tsv, js = tmp_path / "o.tsv", tmp_path / "o.json"
    assert pv.main([str(vcf), "--sample", "s1", "--tsv", str(tsv), "--json", str(js)]) == 0
    assert tsv.is_file() and js.is_file()
    assert pv.main([str(tmp_path / "missing.vcf"), "--tsv", str(tsv), "--json", str(js)]) == 1


def test_empty_vcf_no_variants(tmp_path):
    variants = pv.prioritize(pv.parse_vcf(_write_vcf(tmp_path, [])))
    assert variants == []
