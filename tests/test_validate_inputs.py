"""
Unit tests for bin/validate_inputs.py (H8 input-hardening gate). Fully offline.
"""

from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "validate_inputs.py"
_spec = importlib.util.spec_from_file_location("validate_inputs", _BIN)
vi = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(vi)


_GOOD = "@r1\nACGTACGT\n+\nIIIIIIII\n@r2\nNNNNACGT\n+\n!!!!IIII\n"


def _write(tmp_path, text, name="in.fastq", gz=False):
    p = tmp_path / (name + (".gz" if gz else ""))
    if gz:
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        p.write_text(text, encoding="utf-8")
    return p


# --- happy path ------------------------------------------------------------

def test_valid_plain_fastq(tmp_path):
    stats = vi.validate_file(_write(tmp_path, _GOOD), 200.0, 1000.0, 1000)
    assert stats["gzipped"] is False
    assert stats["decompressed_bytes"] > 0


def test_valid_gzipped_fastq(tmp_path):
    stats = vi.validate_file(_write(tmp_path, _GOOD, gz=True), 200.0, 1000.0, 1000)
    assert stats["gzipped"] is True


# --- structural failures ---------------------------------------------------

def test_empty_file_rejected(tmp_path):
    p = tmp_path / "e.fastq"
    p.write_text("", encoding="utf-8")
    with pytest.raises(vi.InputError, match="empty"):
        vi.validate_file(p, 200.0, 1000.0, 1000)


def test_bad_header_rejected(tmp_path):
    p = _write(tmp_path, "r1\nACGT\n+\nIIII\n")
    with pytest.raises(vi.InputError, match="header"):
        vi.validate_file(p, 200.0, 1000.0, 1000)


def test_seq_qual_length_mismatch_rejected(tmp_path):
    p = _write(tmp_path, "@r1\nACGTACGT\n+\nIIII\n")
    with pytest.raises(vi.InputError, match="length mismatch"):
        vi.validate_file(p, 200.0, 1000.0, 1000)


def test_non_dna_sequence_rejected(tmp_path):
    p = _write(tmp_path, "@r1\nACGTXZ\n+\nIIIIII\n")
    with pytest.raises(vi.InputError, match="non-DNA"):
        vi.validate_file(p, 200.0, 1000.0, 1000)


def test_truncated_record_rejected(tmp_path):
    p = _write(tmp_path, "@r1\nACGT\n+\n")   # missing quality line
    with pytest.raises(vi.InputError, match="truncated"):
        vi.validate_file(p, 200.0, 1000.0, 1000)


def test_corrupt_gzip_rejected(tmp_path):
    p = tmp_path / "bad.fastq.gz"
    p.write_bytes(b"\x1f\x8b\x08\x00garbagegarbage")   # gzip magic, junk body
    with pytest.raises(vi.InputError):
        vi.validate_file(p, 200.0, 1000.0, 1000)


# --- size / decompression-bomb guards --------------------------------------

def test_size_cap_rejects_oversized(tmp_path):
    # 1 MiB of records, cap at ~1 KB -> exceeds decompressed cap.
    big = _GOOD * 40000
    p = _write(tmp_path, big)
    with pytest.raises(vi.InputError, match="exceeds cap"):
        vi.validate_file(p, max_gb=1e-6, max_ratio=1e9, sample_records=1000)


def test_decompression_bomb_ratio_rejected(tmp_path):
    # Highly compressible payload -> tiny gz, huge ratio.
    bomb = "@r\n" + "A" * 500000 + "\n+\n" + "I" * 500000 + "\n"
    p = _write(tmp_path, bomb, gz=True)
    with pytest.raises(vi.InputError, match="bomb|ratio"):
        vi.validate_file(p, max_gb=200.0, max_ratio=50.0, sample_records=10)


# --- CLI -------------------------------------------------------------------

def test_cli_ok_and_report(tmp_path):
    good = _write(tmp_path, _GOOD)
    report = tmp_path / "r.txt"
    assert vi.main([str(good), "--report", str(report)]) == 0
    assert "OK" in report.read_text()


def test_cli_fails_on_bad_input(tmp_path):
    good = _write(tmp_path, _GOOD, name="good.fastq")
    bad = _write(tmp_path, "@r1\nACGT\n+\n", name="bad.fastq")   # truncated
    assert vi.main([str(good), str(bad)]) == 1
