#!/usr/bin/env python3
"""
Prioritize annotated variants for the clinical report.

Reads an annotated VCF (SnpEff ANN or Ensembl VEP CSQ; plain or bgzipped) and
produces a ranked table of variants with a transparent tier assignment and,
when clinical/population evidence is present (H3), an ACMG-style classification
with the criteria that fired.

IMPORTANT - research-use labelling
  This is a research-use prioritization aid. The "ACMG-style" classification is
  a transparent heuristic over a *subset* of ACMG/AMP 2015 criteria (Richards et
  al.), not a validated clinical determination. It must not be used for
  diagnosis.

Tiers (most to least likely to matter; PASS variants rank above filtered):
  1  ClinVar pathogenic, or HIGH impact          (PASS)
  2  MODERATE impact                             (PASS)
  3  LOW impact                                  (PASS)
  4  MODIFIER, common (gnomAD AF >= 5%), ClinVar benign, or any filtered variant

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
    1: "Pathogenic/HIGH impact (research-use; not a clinical call)",
    2: "MODERATE impact (research-use)",
    3: "LOW impact (research-use)",
    4: "MODIFIER / common / benign / filtered (research-use)",
}

# Predicted loss-of-function effects (used for the PVS1 criterion). Substring
# match covers both SnpEff and VEP effect vocabularies.
LOF_EFFECTS = (
    "stop_gained", "frameshift", "splice_acceptor", "splice_donor",
    "start_lost", "stop_lost", "transcript_ablation", "exon_loss",
)

# gnomAD allele-frequency thresholds.
AF_BENIGN_STANDALONE = 0.05   # BA1
AF_BENIGN_STRONG     = 0.01   # BS1
AF_RARE              = 1e-4   # PM2 (absent / ultra-rare)


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


def csq_format(header_lines: list[str]) -> list[str]:
    """Extract the VEP CSQ subfield order from the VCF header (or [])."""
    for line in header_lines:
        if line.startswith("##INFO=<ID=CSQ") and "Format:" in line:
            fmt = line.split("Format:", 1)[1]
            fmt = fmt.strip().rstrip('">').strip()
            return [f.strip() for f in fmt.split("|")]
    return []


def parse_csq(info: str, fmt: list[str]) -> dict[str, str]:
    """Return the first VEP CSQ annotation mapped to the ANN-style keys."""
    if not fmt:
        return {}
    for field in info.split(";"):
        if field.startswith("CSQ="):
            first = field[4:].split(",")[0]
            parts = first.split("|")
            raw = {name: (parts[i] if i < len(parts) else "")
                   for i, name in enumerate(fmt)}
            return {
                "effect": raw.get("Consequence", ""),
                "impact": raw.get("IMPACT", ""),
                "gene_name": raw.get("SYMBOL", ""),
                "hgvs_c": raw.get("HGVSc", ""),
                "hgvs_p": raw.get("HGVSp", ""),
            }
    return {}


def info_dict(info: str) -> dict[str, str]:
    """Parse an INFO string into a {key: value} dict (flags map to '')."""
    out: dict[str, str] = {}
    for field in info.split(";"):
        if not field:
            continue
        if "=" in field:
            k, v = field.split("=", 1)
            out[k] = v
        else:
            out[field] = ""
    return out


def _parse_af(val: str) -> float | None:
    """Parse a (possibly multi-allelic, comma-separated) AF INFO value -> max."""
    if val in (None, "", "."):
        return None
    afs = []
    for tok in str(val).split(","):
        tok = tok.strip()
        if tok in ("", "."):
            continue
        try:
            afs.append(float(tok))
        except ValueError:
            continue
    return max(afs) if afs else None


def extract_evidence(info: dict[str, str], vid: str) -> dict:
    """Pull ClinVar / gnomAD / dbSNP evidence out of the INFO dict."""
    clnsig = info.get("CLNSIG", "").replace("_", " ").strip()
    gnomad_af = _parse_af(info.get("gnomAD_AF"))
    rsid = vid if vid.startswith("rs") else ""
    return {
        "clinvar_sig": clnsig,
        "gnomad_af": gnomad_af,
        "rsid": rsid,
    }


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
    header: list[str] = []
    with _open(path) as handle:
        for line in handle:
            if line.startswith("#"):
                header.append(line.rstrip("\n"))
                continue
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8:
                continue
            chrom, pos, vid, ref, alt, qual, filt, info = cols[:8]
            fmt = cols[8] if len(cols) > 8 else ""
            sample = cols[9] if len(cols) > 9 else ""
            ann = parse_ann(info)
            if not ann:
                ann = parse_csq(info, csq_format(header))
            evidence = extract_evidence(info_dict(info), vid if vid != "." else "")
            variant = {
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
            }
            variant.update(evidence)
            variants.append(variant)
    return variants


def assign_tier(variant: dict) -> int:
    impact = variant.get("impact", "").upper()
    if not variant.get("passed", False):
        return 4
    sig = (variant.get("clinvar_sig") or "").lower()
    af = variant.get("gnomad_af")
    # Population evidence: a common variant is unlikely to be causal.
    if af is not None and af >= AF_BENIGN_STANDALONE:
        return 4
    # Clinical evidence overrides predicted impact.
    if "pathogenic" in sig and "conflicting" not in sig:
        return 1
    if "benign" in sig:
        return 4
    if impact == "HIGH":
        return 1
    if impact == "MODERATE":
        return 2
    if impact == "LOW":
        return 3
    return 4


def acmg_criteria(variant: dict) -> list[dict]:
    """Return the ACMG-style criteria (subset) that fire for a variant.

    Transparent heuristic over a subset of ACMG/AMP 2015 criteria - NOT a
    validated clinical determination. Each entry is {code, reason}.
    """
    crits: list[dict] = []
    impact = (variant.get("impact") or "").upper()
    effect = (variant.get("effect") or "").lower()
    af = variant.get("gnomad_af")
    sig = (variant.get("clinvar_sig") or "").lower()

    if impact == "HIGH" and any(t in effect for t in LOF_EFFECTS):
        crits.append({"code": "PVS1", "reason": "predicted loss-of-function"})

    if af is not None:
        if af >= AF_BENIGN_STANDALONE:
            crits.append({"code": "BA1", "reason": f"gnomAD AF {af:.3g} >= 5%"})
        elif af >= AF_BENIGN_STRONG:
            crits.append({"code": "BS1", "reason": f"gnomAD AF {af:.3g} >= 1%"})
        elif af < AF_RARE:
            crits.append({"code": "PM2", "reason": f"gnomAD AF {af:.3g} < 0.01%"})
    # If no gnomAD track is present (af is None) PM2 is not asserted, to avoid
    # over-calling rarity we cannot confirm.

    if impact == "MODERATE":
        crits.append({"code": "PP3", "reason": "deleterious computational impact"})

    if "pathogenic" in sig and "conflicting" not in sig:
        crits.append({"code": "PP5", "reason": "ClinVar reports pathogenic"})
    if "benign" in sig:
        crits.append({"code": "BP6", "reason": "ClinVar reports benign"})

    return crits


def classify_acmg(crits: list[dict]) -> str:
    """Combine criteria into a 5-tier class using the ACMG/AMP 2015 rules.

    Conflicting pathogenic and benign evidence resolves to Uncertain
    significance, per the guideline.
    """
    codes = [c["code"] for c in crits]
    pvs = sum(c == "PVS1" for c in codes)
    ps = sum(c.startswith("PS") for c in codes)
    pm = sum(c.startswith("PM") for c in codes)
    pp = sum(c.startswith("PP") for c in codes)
    ba = sum(c == "BA1" for c in codes)
    bs = sum(c.startswith("BS") for c in codes)
    bp = sum(c.startswith("BP") for c in codes)

    pathogenic = (
        (pvs >= 1 and (ps >= 1 or pm >= 2 or (pm >= 1 and pp >= 1) or pp >= 2))
        or (ps >= 2)
        or (ps >= 1 and (pm >= 3 or (pm >= 2 and pp >= 2) or (pm >= 1 and pp >= 4)))
    )
    likely_pathogenic = (
        (pvs >= 1 and pm == 1)
        or (ps >= 1 and 1 <= pm <= 2)
        or (ps >= 1 and pp >= 2)
        or (pm >= 3)
        or (pm >= 2 and pp >= 2)
        or (pm >= 1 and pp >= 4)
    )
    benign = (ba >= 1 or bs >= 2)
    likely_benign = ((bs >= 1 and bp >= 1) or bp >= 2)

    path_side = pathogenic or likely_pathogenic
    benign_side = benign or likely_benign
    if path_side and benign_side:
        return "Uncertain significance"
    if pathogenic:
        return "Pathogenic"
    if likely_pathogenic:
        return "Likely pathogenic"
    if benign:
        return "Benign"
    if likely_benign:
        return "Likely benign"
    return "Uncertain significance"


def prioritize(variants: list[dict]) -> list[dict]:
    for v in variants:
        v["tier"] = assign_tier(v)
        v["tier_label"] = TIER_LABEL[v["tier"]]
        crits = acmg_criteria(v)
        v["acmg_criteria"] = crits
        v["acmg_classification"] = classify_acmg(crits)
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
            "hgvs_p", "genotype", "filter", "rsid", "gnomad_af", "clinvar_sig",
            "acmg_classification"]
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
        "acmg_counts": _acmg_counts(variants),
        "disclaimer": ("Research-use only. Tiers reflect predicted functional "
                       "impact and evidence overlays; the ACMG-style class is a "
                       "transparent heuristic over a subset of ACMG/AMP 2015 "
                       "criteria, not a clinical ACMG classification."),
        "variants": variants,
    }
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _acmg_counts(variants: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in variants:
        cls = v.get("acmg_classification", "Uncertain significance")
        counts[cls] = counts.get(cls, 0) + 1
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prioritize annotated variants.")
    p.add_argument("vcf", type=Path, help="Annotated VCF (SnpEff ANN or VEP CSQ; .vcf/.vcf.gz)")
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
    log.info("prioritized %d variant(s); tier counts %s; ACMG %s",
             len(variants), counts, _acmg_counts(variants))
    return 0


if __name__ == "__main__":
    sys.exit(main())
