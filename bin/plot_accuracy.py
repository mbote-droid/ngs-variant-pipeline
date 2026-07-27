#!/usr/bin/env python3
"""
Render accuracy plots from a benchmark JSON (H4 showcase).

Produces three self-contained SVG charts - no matplotlib, no JS, no external
assets - from the JSON emitted by benchmark_vcf.py / parse_happy.py:

  <prefix>.pr_curve.svg            precision vs recall as QUAL sweeps
  <prefix>.f1_by_type.svg          precision/recall/F1 grouped by ALL/SNP/INDEL
  <prefix>.genotype_confusion.svg  truth-vs-called genotype heatmap

Colours use a validated, colourblind-safe categorical palette (blue/orange/aqua)
and a single-hue blue sequential ramp for the heatmap. Charts render on a light
card so they read consistently wherever they are embedded (README, ACCURACY.md).

Stdlib only; unit-tested without a plotting library.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr, level=logging.INFO,
    format="[plot_accuracy] %(levelname)s: %(message)s",
)
log = logging.getLogger("plot_accuracy")

# Validated categorical palette (colourblind-safe first three slots).
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE, BORDER = "#e1e0d9", "#c3c2b7", "#fcfcfb", "rgba(11,11,11,0.12)"
FONT = 'system-ui,-apple-system,"Segoe UI",sans-serif'

W, H = 560, 380
PAD_L, PAD_R, PAD_T, PAD_B = 64, 24, 52, 56


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _card(title: str, subtitle: str = "") -> list[str]:
    """Open an SVG with a titled light card background."""
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family=\'{FONT}\' role="img" '
        f'aria-label="{_esc(title)}">',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" '
        f'fill="{SURFACE}" stroke="{BORDER}"/>',
        f'<text x="{PAD_L}" y="26" font-size="15" font-weight="600" '
        f'fill="{INK}">{_esc(title)}</text>',
    ]
    if subtitle:
        s.append(f'<text x="{PAD_L}" y="43" font-size="11.5" '
                 f'fill="{MUTED}">{_esc(subtitle)}</text>')
    return s


def _px(recall: float, x0: int, x1: int) -> float:
    return x0 + recall * (x1 - x0)


def _py(val: float, y0: int, y1: int) -> float:
    return y1 - val * (y1 - y0)   # y1 = bottom (val 0), y0 = top (val 1)


def _axes01(x0, x1, y0, y1, xlabel, ylabel) -> list[str]:
    """A 0..1 x 0..1 plotting box with gridlines and tick labels."""
    s = []
    for i in range(5):
        v = i / 4
        gy = _py(v, y0, y1)
        gx = _px(v, x0, x1)
        s.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        s.append(f'<text x="{x0-8}" y="{gy+3:.1f}" font-size="10.5" '
                 f'text-anchor="end" fill="{MUTED}">{v:.2f}</text>')
        s.append(f'<text x="{gx:.1f}" y="{y1+16}" font-size="10.5" '
                 f'text-anchor="middle" fill="{MUTED}">{v:.2f}</text>')
    s.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" '
             f'stroke="{AXIS}" stroke-width="1.5"/>')
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" '
             f'stroke="{AXIS}" stroke-width="1.5"/>')
    s.append(f'<text x="{(x0+x1)/2:.0f}" y="{H-14}" font-size="12" '
             f'text-anchor="middle" fill="{INK2}">{_esc(xlabel)}</text>')
    s.append(f'<text x="18" y="{(y0+y1)/2:.0f}" font-size="12" '
             f'text-anchor="middle" fill="{INK2}" '
             f'transform="rotate(-90 18 {(y0+y1)/2:.0f})">{_esc(ylabel)}</text>')
    return s


def pr_curve_svg(result: dict) -> str:
    pts = sorted(result.get("pr_curve", []), key=lambda p: p["recall"])
    x0, x1, y0, y1 = PAD_L, W - PAD_R, PAD_T, H - PAD_B
    best = max(pts, key=lambda p: (2 * p["precision"] * p["recall"]
               / (p["precision"] + p["recall"])) if (p["precision"] + p["recall"]) else 0,
               default=None)
    s = _card("Precision–Recall (QUAL sweep)",
              f"{result.get('sample', '')} · {result.get('tool', '')} · "
              f"{len(pts)} threshold(s)")
    s += _axes01(x0, x1, y0, y1, "Recall", "Precision")
    if len(pts) >= 2:
        d = " ".join(f"{_px(p['recall'], x0, x1):.1f},{_py(p['precision'], y0, y1):.1f}"
                     for p in pts)
        s.append(f'<polyline points="{d}" fill="none" stroke="{C_BLUE}" '
                 f'stroke-width="2" stroke-linejoin="round"/>')
    for p in pts:
        cx, cy = _px(p["recall"], x0, x1), _py(p["precision"], y0, y1)
        s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{C_BLUE}" '
                 f'stroke="{SURFACE}" stroke-width="1.5"/>')
    if best is not None:
        cx, cy = _px(best["recall"], x0, x1), _py(best["precision"], y0, y1)
        s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="none" '
                 f'stroke="{C_ORANGE}" stroke-width="2"/>')
        lx = min(cx + 10, x1 - 96)
        s.append(f'<text x="{lx:.1f}" y="{cy-9:.1f}" font-size="10.5" '
                 f'fill="{INK2}">P {best["precision"]:.3f} · R {best["recall"]:.3f}</text>')
    s.append("</svg>")
    return "\n".join(s)


def f1_by_type_svg(result: dict) -> str:
    metrics = result.get("metrics", {})
    classes = [c for c in ("ALL", "SNP", "INDEL") if c in metrics]
    series = [("precision", C_BLUE), ("recall", C_ORANGE), ("f1", C_AQUA)]
    x0, x1, y0, y1 = PAD_L, W - PAD_R, PAD_T, H - PAD_B
    s = _card("Precision / Recall / F1 by variant type", result.get("sample", ""))
    # y grid 0..1
    for i in range(5):
        v = i / 4
        gy = _py(v, y0, y1)
        s.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        s.append(f'<text x="{x0-8}" y="{gy+3:.1f}" font-size="10.5" '
                 f'text-anchor="end" fill="{MUTED}">{v:.2f}</text>')
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" '
             f'stroke="{AXIS}" stroke-width="1.5"/>')
    n_groups = max(len(classes), 1)
    gw = (x1 - x0) / n_groups
    bw = min(26, gw / (len(series) + 1))
    for gi, cls in enumerate(classes):
        gx = x0 + gi * gw
        for si, (key, colour) in enumerate(series):
            v = float(metrics[cls].get(key, 0.0))
            bx = gx + gw / 2 - (len(series) * bw + (len(series) - 1) * 2) / 2 + si * (bw + 2)
            bh = v * (y1 - y0)
            by = y1 - bh
            s.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" '
                     f'height="{max(bh,0):.1f}" rx="2" fill="{colour}"/>')
            s.append(f'<text x="{bx+bw/2:.1f}" y="{by-4:.1f}" font-size="9" '
                     f'text-anchor="middle" fill="{INK2}">{v:.2f}</text>')
        s.append(f'<text x="{gx+gw/2:.1f}" y="{y1+18}" font-size="11.5" '
                 f'text-anchor="middle" fill="{INK}">{_esc(cls)}</text>')
    # legend
    lx = x0
    for key, colour in series:
        s.append(f'<rect x="{lx}" y="{H-20}" width="11" height="11" rx="2" fill="{colour}"/>')
        s.append(f'<text x="{lx+15}" y="{H-11}" font-size="10.5" '
                 f'fill="{INK2}">{key}</text>')
        lx += 24 + len(key) * 7
    s.append("</svg>")
    return "\n".join(s)


def _ramp(frac: float) -> str:
    """Blue sequential ramp, near-white (0) -> dark blue (1)."""
    frac = max(0.0, min(1.0, frac))
    lo, hi = (0xe8, 0xf1, 0xfc), (0x18, 0x4f, 0x95)
    rgb = tuple(round(lo[i] + (hi[i] - lo[i]) * frac) for i in range(3))
    return "#%02x%02x%02x" % rgb


def genotype_confusion_svg(result: dict) -> str:
    gt = result.get("genotype", {})
    labels = gt.get("labels", ["het", "hom_alt", "hom_ref"])
    matrix = gt.get("matrix", {})
    n = len(labels)
    cell = 74
    grid_x, grid_y = PAD_L + 40, PAD_T + 6
    mx = max((matrix.get(t, {}).get(q, 0) for t in labels for q in labels), default=0) or 1
    s = _card("Genotype concordance (truth vs called)",
              f"{result.get('sample', '')} · concordance "
              f"{gt.get('concordance', 0):.3f} over {gt.get('matched', 0)} matched")
    for r, t in enumerate(labels):
        for c, q in enumerate(labels):
            cnt = matrix.get(t, {}).get(q, 0)
            frac = cnt / mx
            cx, cy = grid_x + c * cell, grid_y + r * cell
            tcol = "#ffffff" if frac > 0.55 else INK
            s.append(f'<rect x="{cx}" y="{cy}" width="{cell-3}" height="{cell-3}" '
                     f'rx="3" fill="{_ramp(frac)}" stroke="{BORDER}"/>')
            s.append(f'<text x="{cx+(cell-3)/2:.0f}" y="{cy+(cell-3)/2+5:.0f}" '
                     f'font-size="16" font-weight="600" text-anchor="middle" '
                     f'fill="{tcol}">{cnt}</text>')
        s.append(f'<text x="{grid_x-8}" y="{grid_y+r*cell+(cell-3)/2+4:.0f}" '
                 f'font-size="11" text-anchor="end" fill="{INK}">{_esc(t)}</text>')
    for c, q in enumerate(labels):
        s.append(f'<text x="{grid_x+c*cell+(cell-3)/2:.0f}" y="{grid_y+n*cell+14}" '
                 f'font-size="11" text-anchor="middle" fill="{INK}">{_esc(q)}</text>')
    s.append(f'<text x="{grid_x+n*cell/2:.0f}" y="{grid_y+n*cell+34}" '
             f'font-size="12" text-anchor="middle" fill="{INK2}">Called genotype</text>')
    s.append(f'<text x="20" y="{grid_y+n*cell/2:.0f}" font-size="12" '
             f'text-anchor="middle" fill="{INK2}" '
             f'transform="rotate(-90 20 {grid_y+n*cell/2:.0f})">Truth genotype</text>')
    s.append("</svg>")
    return "\n".join(s)


def roc_svg(result: dict) -> str:
    """ROC curve for the classifier eval (eval_prioritizer.py JSON)."""
    pts = result.get("roc_curve", [])
    x0, x1, y0, y1 = PAD_L, W - PAD_R, PAD_T, H - PAD_B
    auc = result.get("roc_auc")
    note = " · self-consistent (uses ClinVar)" if result.get("self_consistent") else ""
    s = _card("ROC — prioritizer vs ClinVar",
              f"{result.get('sample', '')} · score={result.get('score_field', '')} · "
              f"AUC {auc if auc is not None else 'n/a'}{note}")
    s += _axes01(x0, x1, y0, y1, "False positive rate", "True positive rate")
    # chance diagonal
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y0}" stroke="{MUTED}" '
             f'stroke-width="1" stroke-dasharray="4 4"/>')
    if len(pts) >= 2:
        d = " ".join(f"{_px(p['fpr'], x0, x1):.1f},{_py(p['tpr'], y0, y1):.1f}" for p in pts)
        s.append(f'<polyline points="{d}" fill="none" stroke="{C_BLUE}" '
                 f'stroke-width="2" stroke-linejoin="round"/>')
    s.append("</svg>")
    return "\n".join(s)


def pr_auc_svg(result: dict) -> str:
    """Precision-recall curve for the classifier eval (with prevalence baseline)."""
    pts = result.get("pr_curve", [])
    x0, x1, y0, y1 = PAD_L, W - PAD_R, PAD_T, H - PAD_B
    ap = result.get("pr_auc")
    prev = result.get("prevalence")
    s = _card("Precision–Recall — prioritizer vs ClinVar",
              f"{result.get('sample', '')} · score={result.get('score_field', '')} · "
              f"AP {ap if ap is not None else 'n/a'}")
    s += _axes01(x0, x1, y0, y1, "Recall", "Precision")
    if prev is not None:                       # no-skill baseline = prevalence
        by = _py(float(prev), y0, y1)
        s.append(f'<line x1="{x0}" y1="{by:.1f}" x2="{x1}" y2="{by:.1f}" stroke="{MUTED}" '
                 f'stroke-width="1" stroke-dasharray="4 4"/>')
    if len(pts) >= 2:
        d = " ".join(f"{_px(p['recall'], x0, x1):.1f},{_py(p['precision'], y0, y1):.1f}"
                     for p in pts)
        s.append(f'<polyline points="{d}" fill="none" stroke="{C_ORANGE}" '
                 f'stroke-width="2" stroke-linejoin="round"/>')
    s.append("</svg>")
    return "\n".join(s)


BENCHMARK_PLOTS = {
    "pr_curve": pr_curve_svg,
    "f1_by_type": f1_by_type_svg,
    "genotype_confusion": genotype_confusion_svg,
}
CLASSIFIER_PLOTS = {
    "roc": roc_svg,
    "pr_auc": pr_auc_svg,
}


def write_plots(result: dict, outdir: Path, prefix: str) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    plots = CLASSIFIER_PLOTS if result.get("kind") == "classifier" else BENCHMARK_PLOTS
    written = []
    for name, fn in plots.items():
        out = outdir / f"{prefix}.{name}.svg"
        out.write_text(fn(result), encoding="utf-8")
        written.append(out)
    return written


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render accuracy plots (SVG) from a benchmark JSON.")
    p.add_argument("benchmark", type=Path, help="benchmark JSON (benchmark_vcf.py / parse_happy.py)")
    p.add_argument("--outdir", type=Path, required=True, help="output directory for SVGs")
    p.add_argument("--prefix", default="accuracy", help="output filename prefix")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.benchmark.is_file():
        log.error("benchmark JSON not found: %s", args.benchmark)
        return 1
    result = json.loads(args.benchmark.read_text(encoding="utf-8"))
    written = write_plots(result, args.outdir, args.prefix)
    log.info("wrote %d plot(s): %s", len(written), ", ".join(p.name for p in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
