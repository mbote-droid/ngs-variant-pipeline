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
