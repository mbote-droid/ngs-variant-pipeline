#!/usr/bin/env python3
"""
Samplesheet validator for the ngs-variant-pipeline.

Reads an nf-core-style input CSV, validates it, and writes a normalized CSV that
downstream Nextflow processes consume. Keeping this logic in a small, dependency
-free (stdlib only) script makes it fast to provision inside a conda/container
task and easy to unit-test without a running pipeline.

Input columns
-------------
  sample    (required)  Sample identifier. A sample may span multiple rows
                        (e.g. one FASTQ pair per sequencing lane).
  fastq_1   (required)  Path/URI to R1 reads (.fastq[.gz] or .fq[.gz]).
  fastq_2   (optional)  Path/URI to R2 reads. Empty => single-end.
  status    (optional)  0 = normal/germline (default), 1 = tumor. Reserved for
                        the somatic mode added in a later module; validated now
                        so germline samplesheets stay forward-compatible.

Output columns (normalized)
---------------------------
  sample,single_end,fastq_1,fastq_2,status

Rules enforced
--------------
  * Header must contain at least `sample` and `fastq_1`.
  * `sample` is non-empty and contains no whitespace.
  * `fastq_1` (and `fastq_2` when present) end with a recognized FASTQ suffix.
  * A single-end row leaves `fastq_2` empty; a paired-end row fills both.
  * All rows for the same sample agree on single- vs paired-end.
  * `status`, when present, is 0 or 1.
  * `--check-exists` additionally requires every FASTQ path to exist on disk
    (off by default so the format check runs anywhere).

Exit codes: 0 = valid, 1 = validation error, 2 = usage error.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[check_samplesheet] %(levelname)s: %(message)s",
)
log = logging.getLogger("check_samplesheet")

REQUIRED_COLUMNS = ("sample", "fastq_1")
OPTIONAL_COLUMNS = ("fastq_2", "status")
FASTQ_SUFFIXES = (".fastq.gz", ".fq.gz", ".fastq", ".fq")
OUTPUT_HEADER = ("sample", "single_end", "fastq_1", "fastq_2", "status")


class SamplesheetError(Exception):
    """Raised when the samplesheet is structurally or semantically invalid.

    `line` is the 1-based row number in the source file (header = line 1), or
    None for whole-file problems such as a missing header column.
    """

    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        prefix = f"line {line}: " if line is not None else ""
        super().__init__(prefix + message)


def _has_fastq_suffix(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in FASTQ_SUFFIXES)


def _read_rows(path: Path) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Return (header, rows) where each row is (source_line_number, field map).

    Blank lines are skipped and do not consume a row number that a user would
    see, but the reported line numbers still track the physical file so error
    messages point at the right place.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a UTF-8 BOM
    except FileNotFoundError as exc:
        raise SamplesheetError(f"samplesheet not found: {path}") from exc

    lines = text.splitlines()
    if not lines:
        raise SamplesheetError("samplesheet is empty")

    reader = csv.reader(lines)
    header = [col.strip() for col in next(reader)]

    rows: list[tuple[int, dict[str, str]]] = []
    for offset, fields in enumerate(reader, start=2):  # data starts at line 2
        if not any(cell.strip() for cell in fields):
            continue  # wholly blank line
        if len(fields) != len(header):
            raise SamplesheetError(
                f"expected {len(header)} columns but found {len(fields)}",
                line=offset,
            )
        record = {col: fields[idx].strip() for idx, col in enumerate(header)}
        rows.append((offset, record))
    return header, rows


def _validate_header(header: list[str]) -> None:
    for column in REQUIRED_COLUMNS:
        if column not in header:
            raise SamplesheetError(f"missing required column '{column}' in header")
    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    unknown = [c for c in header if c and c not in known]
    if unknown:
        raise SamplesheetError(
            "unknown column(s) in header: " + ", ".join(unknown)
        )
    if len(set(header)) != len(header):
        raise SamplesheetError("duplicate column names in header")


def _validate_row(
    line: int, record: dict[str, str], check_exists: bool
) -> dict[str, str]:
    sample = record.get("sample", "")
    if not sample:
        raise SamplesheetError("'sample' is empty", line=line)
    if any(ch.isspace() for ch in sample):
        raise SamplesheetError(
            f"'sample' contains whitespace: {sample!r}", line=line
        )

    fastq_1 = record.get("fastq_1", "")
    fastq_2 = record.get("fastq_2", "")

    if not fastq_1:
        raise SamplesheetError("'fastq_1' is empty", line=line)
    if not _has_fastq_suffix(fastq_1):
        raise SamplesheetError(
            f"'fastq_1' must end with one of {FASTQ_SUFFIXES}: {fastq_1}",
            line=line,
        )
    if fastq_2 and not _has_fastq_suffix(fastq_2):
        raise SamplesheetError(
            f"'fastq_2' must end with one of {FASTQ_SUFFIXES}: {fastq_2}",
            line=line,
        )
    if fastq_2 and fastq_1 == fastq_2:
        raise SamplesheetError(
            "'fastq_1' and 'fastq_2' point at the same file", line=line
        )

    status = record.get("status", "0") or "0"
    if status not in ("0", "1"):
        raise SamplesheetError(
            f"'status' must be 0 or 1, got {status!r}", line=line
        )

    if check_exists:
        for field, value in (("fastq_1", fastq_1), ("fastq_2", fastq_2)):
            if value and not Path(value).is_file():
                raise SamplesheetError(
                    f"{field} file does not exist: {value}", line=line
                )

    single_end = fastq_2 == ""
    return {
        "sample": sample,
        "single_end": "true" if single_end else "false",
        "fastq_1": fastq_1,
        "fastq_2": fastq_2,
        "status": status,
    }


def validate_samplesheet(path: Path, check_exists: bool = False) -> list[dict[str, str]]:
    """Parse and validate a samplesheet, returning normalized rows.

    Raises SamplesheetError on the first problem found.
    """
    header, raw_rows = _read_rows(path)
    _validate_header(header)
    if not raw_rows:
        raise SamplesheetError("samplesheet has a header but no data rows")

    normalized: list[dict[str, str]] = []
    endedness: dict[str, str] = {}  # sample -> single_end flag seen first
    for line, record in raw_rows:
        row = _validate_row(line, record, check_exists)
        sample = row["sample"]
        if sample in endedness and endedness[sample] != row["single_end"]:
            raise SamplesheetError(
                f"sample {sample!r} mixes single-end and paired-end rows",
                line=line,
            )
        endedness[sample] = row["single_end"]
        normalized.append(row)
    return normalized


def write_normalized(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_HEADER))
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and normalize a samplesheet.")
    parser.add_argument("input", type=Path, help="Input samplesheet CSV")
    parser.add_argument("output", type=Path, help="Normalized samplesheet CSV to write")
    parser.add_argument(
        "--check-exists",
        action="store_true",
        help="Also verify that each FASTQ path exists on disk.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = validate_samplesheet(args.input, check_exists=args.check_exists)
    except SamplesheetError as exc:
        log.error(str(exc))
        return 1
    write_normalized(rows, args.output)
    n_samples = len({r["sample"] for r in rows})
    log.info(
        "validated %d row(s) across %d sample(s) -> %s",
        len(rows),
        n_samples,
        args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
