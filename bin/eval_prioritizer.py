#!/usr/bin/env python3
"""
Evaluate the variant prioritizer as a binary classifier (H3/H4 showcase).

Treats the prioritizer's ranking as a *classifier score* and ClinVar clinical
significance as the *ground-truth label*, then reports the standard ML metrics -
**ROC-AUC** and **PR-AUC (average precision)** - with the full curve points. This
is the most direct "how good is the model" number in the whole pipeline.

Score vs. label - and why it isn't circular:
  * label  = ClinVar (pathogenic/likely-path -> 1, benign/likely-benign -> 0;
             VUS / no ClinVar -> unlabelled, excluded).
  * score  = a functional-prediction ranking that does NOT use ClinVar:
             --score impact (default) ranks by SnpEff/VEP IMPACT + gnomAD rarity.
             So we measure how well *functional prediction* recovers *clinical*
             pathogenicity. (--score tier / --score acmg are also available;
             note `acmg` folds ClinVar into the score, so it is self-consistency,
             not an independent test - flagged in the output.)

Input: the prioritized JSON from prioritize_variants.py (needs `clinvar_sig`, so
run with a ClinVar overlay - see docs/EVIDENCE.md). Stdlib only; unit-tested.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr, level=logging.INFO,
    format="[eval_prioritizer] %(levelname)s: %(message)s",
)
log = logging.getLogger("eval_prioritizer")

IMPACT_SCORE = {"HIGH": 3.0, "MODERATE": 2.0, "LOW": 1.0, "MODIFIER": 0.0}
ACMG_SCORE = {"Pathogenic": 4.0, "Likely pathogenic": 3.0,
              "Uncertain significance": 2.0, "Likely benign": 1.0, "Benign": 0.0}
SELF_CONSISTENT = {"acmg"}   # score modes that use ClinVar -> not an independent test


def label_of(v: dict):
    """1 = ClinVar pathogenic, 0 = benign, None = unlabelled (VUS / conflicting / none)."""
    sig = (v.get("clinvar_sig") or "").lower()
    if not sig or "conflicting" in sig:
        return None
    if "pathogenic" in sig:
        return 1
    if "benign" in sig:
        return 0
    return None


def score_of(v: dict, field: str) -> float:
    if field == "impact":
        base = IMPACT_SCORE.get((v.get("impact") or "").upper(), 0.0)
        af = v.get("gnomad_af")
        if af is not None:                     # rarer -> slightly higher (tie-break)
            base += max(0.0, 1.0 - min(float(af), 1.0))
        return base
    if field == "tier":
        return 5.0 - float(v.get("tier", 4))
    if field == "acmg":
        return ACMG_SCORE.get(v.get("acmg_classification", "Uncertain significance"), 2.0)
    raise ValueError(f"unknown score field: {field}")


def extract(variants: list[dict], field: str) -> list[tuple]:
    """(score, label) pairs for ClinVar-labelled variants only."""
    out = []
    for v in variants:
        lab = label_of(v)
        if lab is None:
            continue
        out.append((score_of(v, field), lab))
    return out


def _avg_ranks(values: list[float]) -> list[float]:
    """Average (tie-corrected) ranks, 1-based, aligned to input order."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1        # positions i..j (0-based) -> average 1-based rank
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def roc_auc(scored: list[tuple]):
    """Tie-aware ROC-AUC via the Mann-Whitney U statistic. None if a class is empty."""
    n_pos = sum(l for _, l in scored)
    n_neg = len(scored) - n_pos
    if not n_pos or not n_neg:
        return None
    ranks = _avg_ranks([s for s, _ in scored])
    sum_pos = sum(r for (_, l), r in zip(scored, ranks) if l == 1)
    return (sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def curves(scored: list[tuple]):
    """ROC and PR curve points by sweeping the score threshold (descending)."""
    n_pos = sum(l for _, l in scored)
    n_neg = len(scored) - n_pos
    order = sorted(scored, key=lambda x: -x[0])
    thresholds = sorted({s for s, _ in scored}, reverse=True)
    roc = [{"fpr": 0.0, "tpr": 0.0, "threshold": None}]
    pr = []
    tp = fp = idx = 0
    for t in thresholds:
        while idx < len(order) and order[idx][0] >= t:
            tp += order[idx][1]
            fp += 1 - order[idx][1]
            idx += 1
        tpr = tp / n_pos if n_pos else 0.0
        fpr = fp / n_neg if n_neg else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        roc.append({"fpr": round(fpr, 6), "tpr": round(tpr, 6), "threshold": round(t, 6)})
        pr.append({"recall": round(tpr, 6), "precision": round(precision, 6),
                   "threshold": round(t, 6)})
    roc.append({"fpr": 1.0, "tpr": 1.0, "threshold": None})
    return roc, pr


def average_precision(pr: list[dict]) -> float:
    """PR-AUC as average precision: sum (R_i - R_{i-1}) * P_i over the curve."""
    ap = 0.0
    prev_recall = 0.0
    for p in pr:            # pr is threshold-descending == recall-increasing
        ap += (p["recall"] - prev_recall) * p["precision"]
        prev_recall = p["recall"]
    return ap


def evaluate(variants: list[dict], field: str, sample: str) -> dict:
    scored = extract(variants, field)
    n_pos = sum(l for _, l in scored)
    n_neg = len(scored) - n_pos
    auc = roc_auc(scored)
    roc, pr = curves(scored) if scored else ([], [])
    return {
        "sample": sample,
        "score_field": field,
        "self_consistent": field in SELF_CONSISTENT,
        "n_labelled": len(scored),
        "n_pathogenic": n_pos,
        "n_benign": n_neg,
        "roc_auc": None if auc is None else round(auc, 6),
        "pr_auc": round(average_precision(pr), 6) if pr else None,
        "prevalence": round(n_pos / len(scored), 6) if scored else None,
        "roc_curve": roc,
        "pr_curve": pr,
        "kind": "classifier",
        "disclaimer": ("Research-use only. ClinVar labels vary in review status; "
                       "AUC here is a development signal, not a clinical validation."),
    }


def write_tsv(result: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("score_field", result["score_field"]),
        ("n_labelled", result["n_labelled"]),
        ("n_pathogenic", result["n_pathogenic"]),
        ("n_benign", result["n_benign"]),
        ("roc_auc", result["roc_auc"]),
        ("pr_auc", result["pr_auc"]),
        ("prevalence", result["prevalence"]),
    ]
    with out.open("w", encoding="utf-8") as fh:
        fh.write("metric\tvalue\n")
        for k, v in rows:
            fh.write(f"{k}\t{v}\n")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate the prioritizer as a classifier vs ClinVar.")
    p.add_argument("prioritized", type=Path, help="prioritized JSON (prioritize_variants.py)")
    p.add_argument("--score", default="impact", choices=["impact", "tier", "acmg"],
                   help="ranking used as the classifier score (default: impact)")
    p.add_argument("--sample", default="sample", help="sample id")
    p.add_argument("--json", type=Path, required=True, help="output eval JSON")
    p.add_argument("--tsv", type=Path, required=True, help="output eval TSV")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.prioritized.is_file():
        log.error("prioritized JSON not found: %s", args.prioritized)
        return 1
    data = json.loads(args.prioritized.read_text(encoding="utf-8"))
    variants = data.get("variants", [])
    result = evaluate(variants, args.score, args.sample)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_tsv(result, args.tsv)
    if result["n_labelled"] == 0:
        log.warning("no ClinVar-labelled variants found; ROC/PR-AUC undefined. "
                    "Run prioritization with a ClinVar overlay (see docs/EVIDENCE.md).")
    else:
        log.info("%s: ROC-AUC=%s PR-AUC=%s over %d labelled (%d path / %d benign)",
                 args.score, result["roc_auc"], result["pr_auc"],
                 result["n_labelled"], result["n_pathogenic"], result["n_benign"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
