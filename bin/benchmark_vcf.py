#!/usr/bin/env python3
"""
Benchmark a query VCF against a truth/gold-standard VCF (H4).

A lightweight, stdlib-only concordance benchmark: it matches variants by
(chrom, pos, ref, alt) and reports true positives / false positives / false
negatives with precision, recall and F1, split by SNP vs INDEL, optionally
restricted to high-confidence regions (BED).

This is the offline, always-available benchmark used on the bundled synthetic
truth set and in unit tests. For a rigorous, publication-grade evaluation on a
real gold standard (GIAB) use hap.py / vcfeval - see bin/parse_happy.py and
ACCURACY.md - which handle complex representation (left-alignment, phasing,
block substitutions) this simple matcher does not.

Outputs a metrics JSON and a MultiQC-friendly TSV.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[benchmark_vcf] %(levelname)s: %(message)s",
)
log = logging.getLogger("benchmark_vcf")


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "rt", encoding="utf-8")


def _norm_chrom(chrom: str) -> str:
    """Normalise contig names so 'chr1' and '1' compare equal."""
    return chrom[3:] if chrom.startswith("chr") else chrom


def is_snp(ref: str, alt: str) -> bool:
    return len(ref) == 1 and len(alt) == 1 and ref != "-" and alt != "-"


def load_bed(path: Path) -> dict[str, list[tuple[int, int]]]:
    """Load a BED into {chrom: [(start0, end)]}; intervals are 0-based half-open."""
    regions: dict[str, list[tuple[int, int]]] = {}
    with _open(path) as handle:
        for line in handle:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            f = line.split("\t")
            if len(f) < 3:
                continue
            chrom = _norm_chrom(f[0])
            regions.setdefault(chrom, []).append((int(f[1]), int(f[2])))
    for chrom in regions:
        regions[chrom].sort()
    return regions


def in_regions(regions: dict[str, list[tuple[int, int]]], chrom: str, pos: int) -> bool:
    """Is 1-based `pos` inside any BED interval on `chrom`? (No regions -> all pass.)"""
    if not regions:
        return True
    for start, end in regions.get(chrom, ()):
        if start < pos <= end:   # BED 0-based half-open vs 1-based VCF pos
            return True
    return False


def _genotype(fmt: str, sample: str) -> str:
    """Normalise a GT to het / hom_alt / hom_ref (or '' when unavailable)."""
    if not fmt or not sample:
        return ""
    keys = fmt.split(":")
    if "GT" not in keys:
        return ""
    gt = sample.split(":")[keys.index("GT")]
    alleles = gt.replace("|", "/").split("/")
    if alleles in (["0", "1"], ["1", "0"]):
        return "het"
    if alleles == ["1", "1"]:
        return "hom_alt"
    if alleles == ["0", "0"]:
        return "hom_ref"
    return gt


def load_records(path: Path, regions=None) -> dict[tuple, dict]:
    """Return {variant_key: {qual, gt, filter}} for every ALT allele in a VCF.

    Multi-allelic records split into one key per ALT allele (sharing the record's
    QUAL/GT/FILTER). Confident-region filtering is applied here; PASS filtering is
    NOT (callers thresholding is applied later, so the PR sweep sees every call).
    """
    recs: dict[tuple, dict] = {}
    with _open(path) as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            chrom, pos, ref, alt = _norm_chrom(cols[0]), int(cols[1]), cols[3], cols[4]
            qual = cols[5] if len(cols) > 5 else "."
            filt = cols[6] if len(cols) > 6 else "."
            fmt = cols[8] if len(cols) > 8 else ""
            sample = cols[9] if len(cols) > 9 else ""
            if not in_regions(regions or {}, chrom, pos):
                continue
            q = None if qual in (".", "") else float(qual)
            gt = _genotype(fmt, sample)
            for a in alt.split(","):
                if a in (".", ""):
                    continue
                recs[(chrom, pos, ref.upper(), a.upper())] = {
                    "qual": q, "gt": gt, "filter": filt}
    return recs


def load_variants(path: Path, regions=None, pass_only=True) -> set[tuple]:
    """Return the set of variant keys (chrom, pos, ref, alt) in a VCF.

    Multi-allelic records are split into one key per ALT allele. Optionally
    filtered to PASS and to confident regions.
    """
    return {k for k, r in load_records(path, regions).items()
            if not pass_only or r["filter"] in ("PASS", ".")}


def _metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6)}


def _split(keys: set[tuple], want_snp: bool) -> set[tuple]:
    return {k for k in keys if is_snp(k[2], k[3]) == want_snp}


def compare(truth: set[tuple], query: set[tuple]) -> dict:
    """Compute concordance metrics for ALL, SNP and INDEL variant classes."""
    out = {}
    for label, subset in (
        ("ALL", None),
        ("SNP", True),
        ("INDEL", False),
    ):
        t = truth if subset is None else _split(truth, subset)
        q = query if subset is None else _split(query, subset)
        tp = len(t & q)
        out[label] = _metrics(tp, len(q - t), len(t - q))
    return out


GT_LABELS = ("het", "hom_alt", "hom_ref")


def pr_curve(truth: set[tuple], query_recs: dict[tuple, dict]) -> list[dict]:
    """Precision/recall as the QUAL threshold sweeps (the classic ML PR curve).

    At each candidate threshold, query variants with QUAL >= t are "called";
    TP/FP/FN are recomputed against the truth set. Variants with no QUAL are
    treated as QUAL 0 (always called).
    """
    quals = sorted({r["qual"] for r in query_recs.values() if r["qual"] is not None})
    thresholds = [0.0] + quals
    points: list[dict] = []
    for t in thresholds:
        called = {k for k, r in query_recs.items()
                  if (r["qual"] if r["qual"] is not None else 0.0) >= t}
        tp, fp, fn = len(called & truth), len(called - truth), len(truth - called)
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        points.append({"threshold": round(t, 4),
                       "precision": round(precision, 6),
                       "recall": round(recall, 6),
                       "tp": tp, "fp": fp, "fn": fn})
    return points


def genotype_confusion(truth_recs: dict[tuple, dict],
                       query_recs: dict[tuple, dict]) -> dict:
    """Confusion matrix of truth vs query genotype over matched (TP) variants."""
    matrix = {t: {q: 0 for q in GT_LABELS} for t in GT_LABELS}
    matched = concordant = 0
    for key, tr in truth_recs.items():
        qr = query_recs.get(key)
        if qr is None:
            continue
        tg, qg = tr.get("gt", ""), qr.get("gt", "")
        if tg in GT_LABELS and qg in GT_LABELS:
            matrix[tg][qg] += 1
            matched += 1
            if tg == qg:
                concordant += 1
    concordance = round(concordant / matched, 6) if matched else 0.0
    return {"labels": list(GT_LABELS), "matrix": matrix,
            "matched": matched, "concordant": concordant,
            "concordance": concordance}


def write_json(result: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")


def write_tsv(result: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    metric_cols = ("tp", "fp", "fn", "precision", "recall", "f1")
    with out.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(("class",) + metric_cols) + "\n")
        for label in ("ALL", "SNP", "INDEL"):
            m = result["metrics"][label]
            row = [label] + [str(m[c]) for c in metric_cols]
            handle.write("\t".join(row) + "\n")


def run(truth_path: Path, query_path: Path, bed_path: Path | None,
        sample: str, pass_only: bool = True) -> dict:
    regions = load_bed(bed_path) if bed_path else {}
    truth_recs = load_records(truth_path, regions)   # truth is all-confident
    query_recs = load_records(query_path, regions)
    truth = set(truth_recs)
    query = {k for k, r in query_recs.items()
             if not pass_only or r["filter"] in ("PASS", ".")}
    metrics = compare(truth, query)
    return {
        "sample": sample,
        "truth": str(truth_path),
        "query": str(query_path),
        "regions": str(bed_path) if bed_path else None,
        "truth_variants": len(truth),
        "query_variants": len(query),
        "metrics": metrics,
        "pr_curve": pr_curve(truth, query_recs),
        "genotype": genotype_confusion(truth_recs, query_recs),
        "tool": "builtin",
        "disclaimer": ("Lightweight exact-match concordance. For a rigorous "
                       "evaluation use hap.py/vcfeval (see ACCURACY.md)."),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark a VCF against a truth set.")
    p.add_argument("query", type=Path, help="Query VCF (.vcf/.vcf.gz)")
    p.add_argument("truth", type=Path, help="Truth VCF (.vcf/.vcf.gz)")
    p.add_argument("--bed", type=Path, default=None, help="High-confidence regions BED")
    p.add_argument("--sample", default="sample", help="Sample id")
    p.add_argument("--json", type=Path, required=True, help="Output metrics JSON")
    p.add_argument("--tsv", type=Path, required=True, help="Output metrics TSV")
    p.add_argument("--all-filters", action="store_true",
                   help="Count non-PASS query variants too (default: PASS only)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for pth in (args.query, args.truth):
        if not pth.is_file():
            log.error("file not found: %s", pth)
            return 1
    if args.bed and not args.bed.is_file():
        log.error("BED not found: %s", args.bed)
        return 1
    result = run(args.truth, args.query, args.bed, args.sample,
                 pass_only=not args.all_filters)
    write_json(result, args.json)
    write_tsv(result, args.tsv)
    m = result["metrics"]["ALL"]
    log.info("ALL: TP=%d FP=%d FN=%d precision=%.4f recall=%.4f F1=%.4f",
             m["tp"], m["fp"], m["fn"], m["precision"], m["recall"], m["f1"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
