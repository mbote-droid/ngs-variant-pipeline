# Clinical & population evidence (H3)

By default, prioritization is driven by **predicted functional impact** alone
(HIGH/MODERATE/LOW/MODIFIER). H3 lets you layer real evidence on top — ClinVar
clinical significance, gnomAD population frequency, and dbSNP identifiers — and
derives a transparent **ACMG-style** classification from it.

> **Research use only.** The ACMG-style class is a transparent heuristic over a
> *subset* of the ACMG/AMP 2015 criteria (Richards et al.), not a validated
> clinical determination. It must not be used for diagnosis.

## Supplying evidence tracks

All three are optional local, **bgzipped** VCFs; pass whichever you have:

```bash
nextflow run main.nf -profile docker --genome GRCh38 --input samplesheet.csv \
  --clinvar /refs/clinvar.vcf.gz \
  --gnomad  /refs/gnomad.sites.vcf.gz \
  --dbsnp   /refs/dbsnp.vcf.gz
```

`EVIDENCE_ANNOTATE` (bcftools) transfers these INFO fields onto the annotated VCF:

| Track | Field added | Source column |
|---|---|---|
| ClinVar | `CLNSIG`, `CLNSIGCONF`, `CLNREVSTAT`, `CLNDN` | ClinVar INFO |
| gnomAD | `gnomAD_AF` | gnomAD `INFO/AF` (renamed) |
| dbSNP | VCF `ID` (rsIDs) | dbSNP `ID` |

If **no** track is supplied the step is a pure pass-through — the default DAG is
unchanged. Tracks are (re)indexed in-process, so a missing `.tbi` is fine.

> gnomAD releases differ in how AF is encoded; the module maps `INFO/AF` →
> `gnomAD_AF`. If your gnomAD file uses `AF_popmax` or a joint field, adjust the
> `-c` mapping in `modules/local/evidence_annotate.nf`.

## How evidence changes the output

**Tiering** (`assign_tier`) — clinical/population evidence overrides predicted
impact:

- ClinVar **pathogenic/likely-pathogenic** → **Tier 1** regardless of impact.
- gnomAD **AF ≥ 5%** or ClinVar **benign** → **Tier 4** (unlikely causal).
- Otherwise the impact-based tier applies (unchanged).

**ACMG-style criteria** (`acmg_criteria` / `classify_acmg`) — a subset, combined
per the 2015 rules; conflicting pathogenic + benign evidence resolves to VUS:

| Code | Fires when |
|---|---|
| PVS1 | HIGH-impact predicted loss-of-function (stop/frameshift/splice/start-loss …) |
| PM2  | gnomAD AF < 0.01% (only asserted when a gnomAD track is present) |
| PP3  | MODERATE-impact (deleterious computational prediction) |
| PP5  | ClinVar reports pathogenic |
| BS1  | gnomAD AF ≥ 1% |
| BA1  | gnomAD AF ≥ 5% (stand-alone benign) |
| BP6  | ClinVar reports benign |

The report (HTML/JSON) gains `ACMG-style`, `ClinVar`, `gnomAD AF`, and `dbSNP`
columns plus an `acmg_counts` summary. The FHIR Observation for each variant
records the class in its `valueString`.

The logic is stdlib-only and unit-tested in `tests/test_acmg.py`, so you can
exercise and extend it without running the pipeline.

## Evaluating the prioritizer as a classifier (ROC / PR-AUC)

Because prioritization is fundamentally a **binary classification** problem, it
can be evaluated exactly like an ML model: treat the ranking as a *score* and
ClinVar significance as the *ground-truth label*, then measure **ROC-AUC** and
**PR-AUC**. `bin/eval_prioritizer.py` does this from the prioritized JSON:

```bash
# prioritize with a ClinVar overlay first, then evaluate
eval_prioritizer.py results/report/HG002/HG002.prioritized.json \
  --score impact --sample HG002 --json eval.json --tsv eval.tsv
plot_accuracy.py eval.json --outdir plots --prefix HG002   # -> ROC + PR-AUC SVGs
```

- **label** — ClinVar pathogenic/likely-path → 1, benign/likely-benign → 0;
  VUS / conflicting / unlabelled variants are excluded.
- **score** — `--score impact` (default) ranks by SnpEff/VEP IMPACT + gnomAD
  rarity, which **does not use ClinVar**, so this is an *independent* test of how
  well functional prediction recovers clinical pathogenicity. `--score tier` and
  `--score acmg` are also available; `acmg` folds ClinVar into the score, so its
  result is self-consistency (flagged `self_consistent: true` in the output), not
  an independent test.

AUC is computed tie-aware (Mann-Whitney U); PR-AUC is average precision. The
`plot_accuracy.py` renderer detects the eval JSON and emits an ROC curve (with the
chance diagonal) and a PR curve (with the prevalence no-skill baseline).

Illustrative example (synthetic demo data, `--score impact`, ROC-AUC 0.84 /
PR-AUC 0.87 — replace with a real ClinVar-annotated run):

![ROC curve](docs/img/accuracy/example.roc.svg)
![Precision–Recall (AUC)](docs/img/accuracy/example.pr_auc.svg)

> Research-use only: ClinVar labels vary in review status, so AUC here is a
> development signal, not a clinical validation.

Logic is unit-tested in `tests/test_eval_prioritizer.py`.
