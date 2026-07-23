# Project summary (for reviewers)

A one-page orientation for an employer, collaborator, or investor evaluating this
repository. For the design rationale see [ARCHITECTURE.md](../ARCHITECTURE.md);
for the QA/security strategy see [QUALITY.md](QUALITY.md).

## What it is

A production-shaped **germline + somatic NGS variant-analysis pipeline** in
Nextflow: it takes raw DNA sequencing reads and produces an annotated,
prioritized, clinician-readable report plus a standards-compliant FHIR file —
the same shape of system a clinical genomics lab runs.

```
samplesheet → QC/trim → align → call variants → annotate → prioritize → report
                                                     │
                     germline · somatic (Mutect2) · cohort joint · long-read
```

## Why it's credible (not a toy)

Each capability closes a specific "but is it real?" question:

- **Reproducible** — every tool pinned to a container; the whole DAG runs offline
  in `-stub` mode; CI proves it on every push.
- **Proven accurate** — calls are benchmarked against the **GIAB** gold standard
  with GA4GH **hap.py** (precision/recall/F1, genotype concordance). Accuracy
  isn't asserted; it's measured. See [ACCURACY.md](../ACCURACY.md).
- **Clinically literate** — ClinVar/gnomAD/dbSNP evidence and a transparent
  ACMG/AMP-style classification (research-use, fully auditable).
- **Interoperable** — output includes an **HL7 FHIR Genomics Reporting IG**-aligned
  bundle, so results ingest into real EHR/LIS systems. See [FHIR.md](FHIR.md).
- **Scales without code changes** — same workflow on a laptop, HPC (`slurm`), or
  cloud (`aws`/`google`/`azure`). See [CLOUD.md](CLOUD.md).
- **Modern data types** — short-read Illumina *and* long-read Nanopore/PacBio
  (minimap2 + Clair3 + Sniffles2 SVs). See [LONGREAD.md](LONGREAD.md).
- **Responsible AI** — an optional LLM report narrative that is de-identified,
  grounded against hallucination, and degrades gracefully. See
  [AI_REPORT.md](AI_REPORT.md).

## Engineering quality signals

- **Tested**: 150+ offline unit tests over every logic-bearing script; a full
  stub-DAG integration run; offline verifiers for containers, the FHIR bundle,
  and the parameter schema — all gating CI.
- **Reproducible provenance**: pinned containers + per-run `timeline`/`report`/
  `trace` + collated tool versions.
- **Standards-aligned**: nf-core-style module/subworkflow layout, a validatable
  `nextflow_schema.json`, and [CITATIONS.md](../CITATIONS.md).
- **Honest scope**: research-use labelling throughout; known simplifications and
  the next security workstream are documented, not hidden ([QUALITY.md](QUALITY.md)).

## Try it in 30 seconds (no tools/network)

```bash
nextflow run main.nf -profile test -stub      # runs the whole DAG on synthetic data
pytest -q                                     # the unit-test suite
```

## Status

Build plan in [ROADMAP.md](../ROADMAP.md): the hardening track (H1–H7), somatic
(M7), cloud (M8), long-read (M9) and polish (M10) are complete. Outputs are
**research use only**.
