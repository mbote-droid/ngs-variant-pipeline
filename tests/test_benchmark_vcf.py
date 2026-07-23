"""
Unit tests for bin/benchmark_vcf.py (H4). Fully offline; no pipeline or tools.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "benchmark_vcf.py"
_spec = importlib.util.spec_from_file_location("benchmark_vcf", _BIN)
bm = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(bm)

_HEADER = (
    "##fileformat=VCFv4.2\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
)


def _vcf(tmp_path, rows, name="v.vcf", gz=False):
    text = _HEADER + "".join(rows)
    p = tmp_path / (name + (".gz" if gz else ""))
    if gz:
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        p.write_text(text, encoding="utf-8")
    return p


def _row(chrom, pos, ref, alt, filt="PASS"):
    return f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\t{filt}\t.\n"


# --- exact concordance -----------------------------------------------------

def test_perfect_match(tmp_path):
    rows = [_row("chr1", 100, "A", "T"), _row("chr1", 200, "C", "G")]
    t = _vcf(tmp_path, rows, "t.vcf")
    q = _vcf(tmp_path, rows, "q.vcf")
    r = bm.run(t, q, None, "s")
    assert r["metrics"]["ALL"] == {"tp": 2, "fp": 0, "fn": 0,
                                   "precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_fp_and_fn(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),
                            _row("chr1", 200, "C", "G")], "t.vcf")
    query = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),        # TP
                            _row("chr1", 300, "G", "A")], "q.vcf")  # FP; 200 is FN
    m = bm.run(truth, query, None, "s")["metrics"]["ALL"]
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5


# --- SNP vs INDEL ----------------------------------------------------------

def test_snp_indel_split(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),         # SNP
                            _row("chr1", 200, "C", "CAT")], "t.vcf")  # INDEL (ins)
    query = _vcf(tmp_path, [_row("chr1", 100, "A", "T")], "q.vcf")    # only SNP
    m = bm.run(truth, query, None, "s")["metrics"]
    assert m["SNP"] == {"tp": 1, "fp": 0, "fn": 0,
                        "precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert m["INDEL"]["fn"] == 1 and m["INDEL"]["recall"] == 0.0


def test_is_snp():
    assert bm.is_snp("A", "T")
    assert not bm.is_snp("A", "AT")
    assert not bm.is_snp("AC", "A")


# --- chrom normalisation & multiallelic ------------------------------------

def test_chrom_naming_normalised(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T")], "t.vcf")
    query = _vcf(tmp_path, [_row("1", 100, "A", "T")], "q.vcf")  # '1' vs 'chr1'
    assert bm.run(truth, query, None, "s")["metrics"]["ALL"]["tp"] == 1


def test_multiallelic_split(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),
                            _row("chr1", 100, "A", "C")], "t.vcf")
    query = _vcf(tmp_path, [_row("chr1", 100, "A", "T,C")], "q.vcf")
    assert bm.run(truth, query, None, "s")["metrics"]["ALL"]["tp"] == 2


# --- PASS filtering & regions ----------------------------------------------

def test_non_pass_query_excluded(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T")], "t.vcf")
    query = _vcf(tmp_path, [_row("chr1", 100, "A", "T", filt="LowQual")], "q.vcf")
    # default pass_only -> the LowQual call is dropped -> FN
    assert bm.run(truth, query, None, "s")["metrics"]["ALL"] == {
        "tp": 0, "fp": 0, "fn": 1, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    # with all filters -> counts as TP
    assert bm.run(truth, query, None, "s", pass_only=False)["metrics"]["ALL"]["tp"] == 1


def test_bed_restricts_to_regions(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),
                            _row("chr1", 5000, "C", "G")], "t.vcf")
    query = _vcf(tmp_path, [_row("chr1", 100, "A", "T"),
                            _row("chr1", 5000, "C", "G")], "q.vcf")
    bed = tmp_path / "conf.bed"
    bed.write_text("chr1\t50\t150\n")   # covers pos 100, excludes 5000
    m = bm.run(truth, query, bed, "s")["metrics"]["ALL"]
    assert (m["tp"], m["fp"], m["fn"]) == (1, 0, 0)


def test_in_regions_boundaries():
    regions = {"1": [(50, 150)]}          # 0-based half-open -> 1-based 51..150
    assert not bm.in_regions(regions, "1", 50)
    assert bm.in_regions(regions, "1", 51)
    assert bm.in_regions(regions, "1", 150)
    assert not bm.in_regions(regions, "1", 151)
    assert bm.in_regions({}, "1", 999)    # no regions -> everything passes


# --- IO / CLI --------------------------------------------------------------

def test_gzip_inputs(tmp_path):
    rows = [_row("chr1", 100, "A", "T")]
    t = _vcf(tmp_path, rows, "t.vcf", gz=True)
    q = _vcf(tmp_path, rows, "q.vcf", gz=True)
    assert bm.run(t, q, None, "s")["metrics"]["ALL"]["tp"] == 1


def test_main_writes_outputs(tmp_path):
    rows = [_row("chr1", 100, "A", "T")]
    t = _vcf(tmp_path, rows, "t.vcf")
    q = _vcf(tmp_path, rows, "q.vcf")
    js, ts = tmp_path / "o.json", tmp_path / "o.tsv"
    assert bm.main([str(q), str(t), "--json", str(js), "--tsv", str(ts)]) == 0
    data = json.loads(js.read_text())
    assert data["metrics"]["ALL"]["f1"] == 1.0
    lines = ts.read_text().splitlines()
    assert lines[0].split("\t") == ["class", "tp", "fp", "fn", "precision", "recall", "f1"]
    assert lines[1].startswith("ALL")
    assert bm.main([str(tmp_path / "missing.vcf"), str(t),
                    "--json", str(js), "--tsv", str(ts)]) == 1


def test_empty_query_no_crash(tmp_path):
    truth = _vcf(tmp_path, [_row("chr1", 100, "A", "T")], "t.vcf")
    query = _vcf(tmp_path, [], "q.vcf")
    m = bm.run(truth, query, None, "s")["metrics"]["ALL"]
    assert (m["tp"], m["fp"], m["fn"]) == (0, 0, 1)
    assert m["precision"] == 0.0 and m["f1"] == 0.0
