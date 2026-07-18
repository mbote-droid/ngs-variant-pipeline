"""
Unit tests for bin/check_samplesheet.py.

Runs fully offline with no pipeline, tools, or network. Exercises the happy path
plus the validation edge cases the pipeline must reject before wasting compute.

Run:  pytest -q   (from the repo root)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the script from bin/ as a module (it has no package/__init__).
_BIN = Path(__file__).resolve().parents[1] / "bin" / "check_samplesheet.py"
_spec = importlib.util.spec_from_file_location("check_samplesheet", _BIN)
cs = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(cs)


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "samplesheet.csv"
    p.write_text(text, encoding="utf-8")
    return p


PAIRED = (
    "sample,fastq_1,fastq_2\n"
    "s1,/data/s1_R1.fastq.gz,/data/s1_R2.fastq.gz\n"
)
SINGLE = "sample,fastq_1,fastq_2\ns1,/data/s1_R1.fastq.gz,\n"


# --- happy paths -----------------------------------------------------------

def test_paired_end_valid(tmp_path):
    rows = cs.validate_samplesheet(_write(tmp_path, PAIRED))
    assert len(rows) == 1
    assert rows[0]["single_end"] == "false"
    assert rows[0]["status"] == "0"
    assert rows[0]["fastq_2"].endswith("s1_R2.fastq.gz")


def test_single_end_valid(tmp_path):
    rows = cs.validate_samplesheet(_write(tmp_path, SINGLE))
    assert rows[0]["single_end"] == "true"
    assert rows[0]["fastq_2"] == ""


def test_fastq_2_column_absent_is_single_end(tmp_path):
    sheet = "sample,fastq_1\ns1,/data/s1_R1.fq\n"
    rows = cs.validate_samplesheet(_write(tmp_path, sheet))
    assert rows[0]["single_end"] == "true"


def test_multiple_lanes_same_sample_ok(tmp_path):
    sheet = (
        "sample,fastq_1,fastq_2\n"
        "s1,/d/s1_L1_R1.fastq.gz,/d/s1_L1_R2.fastq.gz\n"
        "s1,/d/s1_L2_R1.fastq.gz,/d/s1_L2_R2.fastq.gz\n"
    )
    rows = cs.validate_samplesheet(_write(tmp_path, sheet))
    assert len(rows) == 2
    assert {r["sample"] for r in rows} == {"s1"}


def test_status_column_tumor_normal(tmp_path):
    sheet = (
        "sample,fastq_1,fastq_2,status\n"
        "normal,/d/n_R1.fastq.gz,/d/n_R2.fastq.gz,0\n"
        "tumor,/d/t_R1.fastq.gz,/d/t_R2.fastq.gz,1\n"
    )
    rows = cs.validate_samplesheet(_write(tmp_path, sheet))
    assert [r["status"] for r in rows] == ["0", "1"]


def test_bom_and_blank_lines_tolerated(tmp_path):
    sheet = "﻿sample,fastq_1,fastq_2\n\ns1,/d/s1_R1.fastq.gz,\n\n"
    rows = cs.validate_samplesheet(_write(tmp_path, sheet))
    assert len(rows) == 1


def test_all_fastq_suffixes_accepted(tmp_path):
    for suffix in (".fastq.gz", ".fq.gz", ".fastq", ".fq"):
        sheet = f"sample,fastq_1\ns1,/d/reads{suffix}\n"
        rows = cs.validate_samplesheet(_write(tmp_path, sheet))
        assert rows[0]["fastq_1"].endswith(suffix)


# --- rejections ------------------------------------------------------------

def test_missing_required_column(tmp_path):
    sheet = "sample,fastq_2\ns1,/d/s1_R2.fastq.gz\n"
    with pytest.raises(cs.SamplesheetError, match="missing required column 'fastq_1'"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_unknown_column_rejected(tmp_path):
    sheet = "sample,fastq_1,genome\ns1,/d/s1_R1.fastq.gz,GRCh38\n"
    with pytest.raises(cs.SamplesheetError, match="unknown column"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_empty_sample_rejected(tmp_path):
    sheet = "sample,fastq_1\n,/d/s1_R1.fastq.gz\n"
    with pytest.raises(cs.SamplesheetError, match="'sample' is empty"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_whitespace_in_sample_rejected(tmp_path):
    sheet = "sample,fastq_1\nmy sample,/d/s1_R1.fastq.gz\n"
    with pytest.raises(cs.SamplesheetError, match="whitespace"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_bad_fastq_extension_rejected(tmp_path):
    sheet = "sample,fastq_1\ns1,/d/s1_R1.bam\n"
    with pytest.raises(cs.SamplesheetError, match="must end with"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_fastq_1_equals_fastq_2_rejected(tmp_path):
    sheet = "sample,fastq_1,fastq_2\ns1,/d/x.fastq.gz,/d/x.fastq.gz\n"
    with pytest.raises(cs.SamplesheetError, match="same file"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_mixed_endedness_same_sample_rejected(tmp_path):
    sheet = (
        "sample,fastq_1,fastq_2\n"
        "s1,/d/s1_R1.fastq.gz,/d/s1_R2.fastq.gz\n"
        "s1,/d/s1b_R1.fastq.gz,\n"
    )
    with pytest.raises(cs.SamplesheetError, match="mixes single-end and paired-end"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_bad_status_value_rejected(tmp_path):
    sheet = "sample,fastq_1,status\ns1,/d/s1_R1.fastq.gz,2\n"
    with pytest.raises(cs.SamplesheetError, match="'status' must be 0 or 1"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_column_count_mismatch_rejected(tmp_path):
    sheet = "sample,fastq_1,fastq_2\ns1,/d/s1_R1.fastq.gz\n"
    with pytest.raises(cs.SamplesheetError, match="expected 3 columns"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_header_only_no_rows_rejected(tmp_path):
    sheet = "sample,fastq_1,fastq_2\n"
    with pytest.raises(cs.SamplesheetError, match="no data rows"):
        cs.validate_samplesheet(_write(tmp_path, sheet))


def test_missing_file_raises(tmp_path):
    with pytest.raises(cs.SamplesheetError, match="not found"):
        cs.validate_samplesheet(tmp_path / "nope.csv")


# --- existence check + IO round trip --------------------------------------

def test_check_exists_flag(tmp_path):
    r1 = tmp_path / "r1.fastq.gz"
    r1.write_text("x")
    sheet = _write(tmp_path, f"sample,fastq_1\ns1,{r1}\n")
    # Exists -> ok
    cs.validate_samplesheet(sheet, check_exists=True)
    # Missing -> error
    sheet2 = tmp_path / "sheet2.csv"
    sheet2.write_text("sample,fastq_1\ns1,/no/such/reads.fastq.gz\n")
    with pytest.raises(cs.SamplesheetError, match="does not exist"):
        cs.validate_samplesheet(sheet2, check_exists=True)


def test_write_normalized_round_trip(tmp_path):
    rows = cs.validate_samplesheet(_write(tmp_path, PAIRED))
    out = tmp_path / "norm.csv"
    cs.write_normalized(rows, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "sample,single_end,fastq_1,fastq_2,status"
    assert lines[1].startswith("s1,false,")


def test_main_cli_success_and_failure(tmp_path):
    good = _write(tmp_path, PAIRED)
    out = tmp_path / "out.csv"
    assert cs.main([str(good), str(out)]) == 0
    assert out.is_file()

    bad = tmp_path / "bad.csv"
    bad.write_text("sample,fastq_1\ns1,/d/x.bam\n")
    assert cs.main([str(bad), str(tmp_path / "out2.csv")]) == 1
