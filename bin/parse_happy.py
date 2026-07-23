#!/usr/bin/env python3
"""
Parse a hap.py summary into the pipeline's benchmark metrics shape (H4).

hap.py (the GA4GH benchmarking tool) writes a `*.summary.csv` with per-type
rows (SNP, INDEL) x filter (ALL, PASS). This converts the PASS rows into the
same JSON/TSV structure that bin/benchmark_vcf.py emits, so the rigorous
gold-standard evaluation and the lightweight built-in one are interchangeable
downstream (report / MultiQC).

Stdlib only; unit-testable without hap.py installed.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[parse_happy] %(levelname)s: %(message)s",
)
log = logging.getLogger("parse_happy")


def _num(val: str) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _int(val: str) -> int:
    return int(round(_num(val)))


def _metrics_from_row(row: dict) -> dict:
    tp = _int(row.get("TRUTH.TP", 0))
    fn = _int(row.get("TRUTH.FN", 0))
    fp = _int(row.get("QUERY.FP", 0))
    # Prefer hap.py's own metric columns; fall back to computing them.
    prec = row.get("METRIC.Precision", "")
    rec = row.get("METRIC.Recall", "")
    f1 = row.get("METRIC.F1_Score", "")
    precision = _num(prec) if prec not in ("", "nan") else (tp / (tp + fp) if tp + fp else 0.0)
    recall = _num(rec) if rec not in ("", "nan") else (tp / (tp + fn) if tp + fn else 0.0)
    if f1 not in ("", "nan"):
        f1v = _num(f1)
    else:
        f1v = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1v, 6)}


def parse_summary(path: Path, filter_level: str = "PASS") -> dict:
    """Parse a hap.py summary.csv into {SNP, INDEL, ALL} metrics."""
    by_type: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("Filter") != filter_level:
                continue
            vtype = row.get("Type", "").upper()
            if vtype in ("SNP", "INDEL"):
                by_type[vtype] = _metrics_from_row(row)

    snp = by_type.get("SNP", {"tp": 0, "fp": 0, "fn": 0,
                              "precision": 0.0, "recall": 0.0, "f1": 0.0})
    indel = by_type.get("INDEL", {"tp": 0, "fp": 0, "fn": 0,
                                  "precision": 0.0, "recall": 0.0, "f1": 0.0})
    # hap.py has no combined row; sum counts and recompute for ALL.
    tp, fp, fn = (snp["tp"] + indel["tp"], snp["fp"] + indel["fp"],
                  snp["fn"] + indel["fn"])
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    all_m = {"tp": tp, "fp": fp, "fn": fn,
             "precision": round(precision, 6),
             "recall": round(recall, 6),
             "f1": round(f1, 6)}
    return {"ALL": all_m, "SNP": snp, "INDEL": indel}


def write_json(metrics: dict, out: Path, sample: str, source: Path,
               filter_level: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "sample": sample,
        "source": str(source),
        "filter": filter_level,
        "metrics": metrics,
        "tool": "hap.py",
    }, indent=2), encoding="utf-8")


def write_tsv(metrics: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    metric_cols = ("tp", "fp", "fn", "precision", "recall", "f1")
    with out.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(("class",) + metric_cols) + "\n")
        for label in ("ALL", "SNP", "INDEL"):
            m = metrics[label]
            handle.write("\t".join([label] + [str(m[c]) for c in metric_cols]) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parse a hap.py summary.csv.")
    p.add_argument("summary", type=Path, help="hap.py *.summary.csv")
    p.add_argument("--sample", default="sample", help="Sample id")
    p.add_argument("--filter", default="PASS", choices=["PASS", "ALL"],
                   help="Which hap.py filter level to report (default: PASS)")
    p.add_argument("--json", type=Path, required=True, help="Output metrics JSON")
    p.add_argument("--tsv", type=Path, required=True, help="Output metrics TSV")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.summary.is_file():
        log.error("summary not found: %s", args.summary)
        return 1
    metrics = parse_summary(args.summary, args.filter)
    write_json(metrics, args.json, args.sample, args.summary, args.filter)
    write_tsv(metrics, args.tsv)
    m = metrics["ALL"]
    log.info("hap.py ALL (%s): precision=%.4f recall=%.4f F1=%.4f",
             args.filter, m["precision"], m["recall"], m["f1"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
