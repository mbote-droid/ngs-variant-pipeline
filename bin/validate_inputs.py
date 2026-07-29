#!/usr/bin/env python3
"""
Pre-flight validation gate for input FASTQ files (H8: input hardening).

Runs BEFORE any heavy C/C++ tool (fastp, BWA-MEM2, minimap2) touches the data,
so a truncated, malformed, or hostile upload is rejected early rather than
crashing a downstream parser or exhausting the host. Fully offline, stdlib-only,
unit-testable.

Checks per FASTQ (plain or gzipped):
  * exists, non-empty, and (for .gz) a valid gzip magic header;
  * FASTQ record structure on a sampled prefix - 4-line records, '@' header,
    '+' separator, sequence/quality equal length, sequence over a DNA alphabet;
  * SIZE GUARD - the (decompressed) stream does not exceed --max-gb;
  * DECOMPRESSION-BOMB GUARD - the decompressed/compressed ratio does not exceed
    --max-ratio (a small gzip that explodes into gigabytes is rejected without
    ever being fully expanded).

Exit codes: 0 = all inputs valid, 1 = one or more failed, 2 = usage error.
"""
from __future__ import annotations

import argparse
import gzip
import sys
import zlib
from pathlib import Path

_GZIP_MAGIC = b"\x1f\x8b"
_DNA = set("ACGTNacgtn.-")
_CHUNK = 1 << 20  # 1 MiB streaming window


class InputError(Exception):
    """A single input file failed validation."""


def _is_gzip(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(2) == _GZIP_MAGIC


def _bounded_decompressed_size(path: Path, gzipped: bool, max_bytes: int) -> int:
    """Return the (decompressed) byte length, aborting past max_bytes.

    Streams in bounded chunks so a decompression bomb is caught without being
    fully expanded in memory. Raises InputError if the cap is exceeded.
    """
    total = 0
    opener = (lambda: gzip.open(path, "rb")) if gzipped else (lambda: open(path, "rb"))
    with opener() as fh:
        while True:
            try:
                chunk = fh.read(_CHUNK)
            except (OSError, EOFError, gzip.BadGzipFile, zlib.error) as exc:
                raise InputError(f"corrupt/truncated stream: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise InputError(
                    f"decompressed size exceeds cap ({max_bytes} bytes); "
                    f"possible decompression bomb or oversized input"
                )
    return total


def _check_fastq_structure(path: Path, gzipped: bool, sample_records: int) -> None:
    """Validate the first `sample_records` FASTQ records (structure + alphabet)."""
    opener = (lambda: gzip.open(path, "rt", encoding="utf-8", errors="replace")) \
        if gzipped else (lambda: open(path, "rt", encoding="utf-8", errors="replace"))
    with opener() as fh:
        rec = 0
        while rec < sample_records:
            header = fh.readline()
            if header == "":
                break  # clean EOF on a record boundary
            seq = fh.readline()
            plus = fh.readline()
            qual = fh.readline()
            if not (seq and plus and qual):
                raise InputError(f"truncated FASTQ record #{rec + 1}")
            if not header.startswith("@"):
                raise InputError(f"record #{rec + 1}: header must start with '@'")
            if not plus.startswith("+"):
                raise InputError(f"record #{rec + 1}: 3rd line must start with '+'")
            seq_s, qual_s = seq.rstrip("\n"), qual.rstrip("\n")
            if len(seq_s) != len(qual_s):
                raise InputError(
                    f"record #{rec + 1}: sequence/quality length mismatch "
                    f"({len(seq_s)} vs {len(qual_s)})"
                )
            bad = set(seq_s) - _DNA
            if bad:
                raise InputError(
                    f"record #{rec + 1}: non-DNA character(s) in sequence: "
                    f"{''.join(sorted(bad))!r}"
                )
            rec += 1
        if rec == 0:
            raise InputError("no FASTQ records found")


def validate_file(path: Path, max_gb: float, max_ratio: float,
                  sample_records: int) -> dict:
    """Validate one FASTQ; return a stats dict or raise InputError."""
    if not path.is_file():
        raise InputError("file not found")
    comp_size = path.stat().st_size
    if comp_size == 0:
        raise InputError("file is empty")

    gzipped = _is_gzip(path)
    max_bytes = int(max_gb * (1024 ** 3))

    decomp_size = _bounded_decompressed_size(path, gzipped, max_bytes)
    if decomp_size == 0:
        raise InputError("decompressed stream is empty")

    ratio = decomp_size / comp_size if comp_size else float("inf")
    if gzipped and ratio > max_ratio:
        raise InputError(
            f"compression ratio {ratio:.1f}x exceeds cap {max_ratio:.0f}x; "
            f"possible decompression bomb"
        )

    _check_fastq_structure(path, gzipped, sample_records)
    return {
        "gzipped": gzipped,
        "compressed_bytes": comp_size,
        "decompressed_bytes": decomp_size,
        "ratio": round(ratio, 2),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate input FASTQ files (H8 gate).")
    p.add_argument("fastqs", nargs="+", type=Path, help="FASTQ file(s) to validate")
    p.add_argument("--max-gb", type=float, default=200.0,
                   help="Max decompressed size per file, in GB (default 200)")
    p.add_argument("--max-ratio", type=float, default=1000.0,
                   help="Max decompressed/compressed ratio (default 1000)")
    p.add_argument("--sample-records", type=int, default=1000,
                   help="How many leading records to structurally check (default 1000)")
    p.add_argument("--report", type=Path, help="Optional path to write a text report")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    lines: list[str] = []
    failures = 0
    for path in args.fastqs:
        try:
            stats = validate_file(path, args.max_gb, args.max_ratio, args.sample_records)
            lines.append(
                f"OK    {path.name}  "
                f"({'gz' if stats['gzipped'] else 'plain'}, "
                f"{stats['decompressed_bytes']} B, ratio {stats['ratio']})"
            )
        except InputError as exc:
            lines.append(f"FAIL  {path.name}: {exc}")
            failures += 1

    report_text = "\n".join(lines) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_text, encoding="utf-8")
    sys.stdout.write(report_text)

    if failures:
        sys.stderr.write(f"[validate_inputs] {failures} input(s) failed validation.\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
