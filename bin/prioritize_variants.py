#!/usr/bin/env python3
"""
Prioritize annotated variants for the clinical report.

Reads a SnpEff-annotated VCF (plain or bgzipped) and produces a ranked table of
variants with a coarse, transparent tier assignment. This is a research-use
prioritization aid - it is NOT a clinical ACMG classification and must not be
used for diagnosis.

Tiers (most to least likely to matter, PASS variants ranked above filtered):
  1  HIGH impact,     PASS
  2  MODERATE impact, PASS
  3  LOW impact,      PASS
  4  MODIFIER, or any variant that failed a hard filter

Outputs: a TSV (human-scannable) and a JSON (machine-readable, feeds the report).
Stdlib only, so it runs in any minimal tool environment and is unit-testable
without a pipeline.
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
    format="[prioritize_variants] %(levelname)s: %(message)s",
)
log = logging.getLogger("prioritize_variants")

# SnpEff ANN subfield order (VCF INFO "ANN=").
ANN_FIELDS = [
    "allele", "effect", "impact", "gene_name", "gene_id", "feature_type",
    "feature_id", "transcript_biotype", "rank", "hgvs_c", "hgvs_p",
    "cdna_pos", "cds_pos", "aa_pos", "distance", "errors",
]

IMPACT_RANK = {"HIGH": 0, "MODERATE": 1, "LOW": 2, "MODIFIER": 3}

TIER_LABEL = {
    1: "HIGH impact (research-use; not a clinical call)",
    2: "MODERATE impact (research-use)",
    3: "LOW impact (research-use)",
    4: "MODIFIER / filtered (research-use)",
}


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "rt", encoding="utf-8")


def parse_ann(info: str) -> dict[str, str]:
    """Return the most severe SnpEff annotation from an INFO string.

    SnpEff lists annotations comma-separated, ordered by severity, so the first
    entry is the most severe. Returns {} when no ANN field is present.
    """
    for field in info.split(";"):
        if field.startswith("ANN="):
            first = field[4:].split(",")[0]
            parts = first.split("|")
            ann = {name: (parts[i] if i < len(parts) else "")
                   for i, name in enumerate(ANN_FIELDS)}
            return ann
    return {}


def _genotype(fmt: str, sample: str) -> str:
    if not fmt or not sample:
        return ""
    keys = fmt.split(":")
    vals = sample.split(":")
    if "GT" not in keys:
        return ""
    gt = vals[keys.index("GT")]
    alleles = gt.replace("|", "/").split("/")
    if alleles == ["0", "1"] or alleles == ["1", "0"]:
        return "het"
    if alleles == ["1", "1"]:
        return "hom_alt"
    if alleles == ["0", "0"]:
        return "hom_ref"
    return gt


def parse_vcf(path: Path) -> list[dict]:
    variants: list[dict] = []
    with _open(path) as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8:
                continue
            chrom, pos, vid, ref, alt, qual, filt, info = cols[:8]
            fmt = cols[8] if len(cols) > 8 else ""
            sample = cols[9] if len(cols) > 9 else ""
            ann = parse_ann(info)
            variants.append({
                "chrom": chrom,
                "pos": int(pos),
                "id": vid if vid != "." else "",
                "ref": ref,
                "alt": alt,
                "qual": None if qual in (".", "") else float(qual),
                "filter": filt,
                "passed": filt in ("PASS", "."),
                "impact": ann.get("impact", ""),
                "effect": ann.get("effect", ""),
                "gene": ann.get("gene_name", ""),
                "hgvs_c": ann.get("hgvs_c", ""),
                "hgvs_p": ann.get("hgvs_p", ""),
                "genotype": _genotype(fmt, sample),
            })
    return variants


def assign_tier(variant: dict) -> int:
    impact = variant.get("impact", "").upper()
    if not variant.get("passed", False):
        return 4
    if impact == "HIGH":
        return 1
    if impact == "MODERATE":
        return 2
    if impact == "LOW":
        return 3
    return 4


def prioritize(variants: list[dict]) -> list[dict]:
    for v in variants:
        v["tier"] = assign_tier(v)
        v["tier_label"] = TIER_LABEL[v["tier"]]
    # Sort by tier, then impact severity, then genomic position (stable, deterministic).
    variants.sort(key=lambda v: (
        v["tier"],
        IMPACT_RANK.get(v.get("impact", "").upper(), 4),
        v["chrom"],
        v["pos"],
    ))
    return variants


def write_tsv(variants: list[dict], out: Path) -> None:
    cols = ["tier", "chrom", "pos", "ref", "alt", "gene", "impact", "effect",
            "hgvs_p", "genotype", "filter"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(cols) + "\n")
        for v in variants:
            handle.write("\t".join(str(v.get(c, "")) for c in cols) + "\n")


def write_json(variants: list[dict], out: Path, sample: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "sample": sample,
        "total_variants": len(variants),
        "tier_counts": {str(t): sum(1 for v in variants if v["tier"] == t)
                        for t in (1, 2, 3, 4)},
        "disclaimer": ("Research-use only. Tiers reflect predicted functional "
                       "impact, not a clinical ACMG classification."),
        "variants": variants,
    }
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prioritize annotated variants.")
    p.add_argument("vcf", type=Path, help="SnpEff-annotated VCF (.vcf or .vcf.gz)")
    p.add_argument("--sample", default="sample", help="Sample id for the outputs")
    p.add_argument("--tsv", type=Path, required=True, help="Output TSV path")
    p.add_argument("--json", type=Path, required=True, help="Output JSON path")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.vcf.is_file():
        log.error("VCF not found: %s", args.vcf)
        return 1
    variants = prioritize(parse_vcf(args.vcf))
    write_tsv(variants, args.tsv)
    write_json(variants, args.json, args.sample)
    counts = {t: sum(1 for v in variants if v["tier"] == t) for t in (1, 2, 3, 4)}
    log.info("prioritized %d variant(s); tier counts %s", len(variants), counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
