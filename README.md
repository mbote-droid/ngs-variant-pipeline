# ngs-variant-pipeline

[![CI](https://github.com/mbote-droid/ngs-variant-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/mbote-droid/ngs-variant-pipeline/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Nextflow](https://img.shields.io/badge/nextflow-%E2%89%A524.04.0-brightgreen.svg)](https://www.nextflow.io/)

A reproducible, containerized clinical-genomics pipeline built with **Nextflow**:
from raw sequencing reads to an evidence-cited, clinician-readable report. It runs
identically on a laptop (small data) or on cloud/HPC (full data), and layers an AI
interpretation stage on top of standard best-practice genomics tooling.

> Status: **Germline + somatic + long-read, laptop-to-cloud.** reads -> QC ->
> align -> call -> annotate -> prioritize -> report, with a single MultiQC over
> every stage. Short-read germline/somatic (Mutect2)/cohort joint genotyping and
> long-read (minimap2 + Clair3 + Sniffles2) paths; HL7 FHIR output; GIAB accuracy
> benchmarking. New here? Start with the one-page
> [**project summary**](docs/PORTFOLIO.md). See `ROADMAP.md` for the build plan,
> `ARCHITECTURE.md` for the design, [`docs/QUALITY.md`](docs/QUALITY.md) for the
> testing/security strategy, and [`CITATIONS.md`](CITATIONS.md) for the tools.
> Research use only.

## Requirements
- Nextflow (>= 24.04), Java 17-21
- One tool provisioner: **conda/mamba** (primary on low-RAM hosts) or Docker/Singularity
- Python 3.9+ (stdlib only) for the samplesheet validator and its tests

## Input: samplesheet
A CSV with a header. `sample` and `fastq_1` are required; `fastq_2` (paired-end)
and `status` (0 = normal/germline, 1 = tumor; reserved for somatic mode) are
optional. A sample may span multiple rows (e.g. one FASTQ pair per lane).

```csv
sample,fastq_1,fastq_2
sample1,reads/s1_R1.fastq.gz,reads/s1_R2.fastq.gz
```

## Quick start
Run the Input + QC stage on the bundled synthetic test data:
```bash
# with conda-provisioned tools
nextflow run main.nf -profile test,conda

# or, to verify wiring with no tools/network (touches stub outputs)
nextflow run main.nf -profile test -stub
```
On your own data:
```bash
nextflow run main.nf --input samplesheet.csv -profile conda
```
For a **real genome** end-to-end (GRCh38 + evidence + GIAB accuracy benchmark) on
Ubuntu/WSL, follow the copy-paste **[WSL runbook](docs/RUNBOOK_WSL.md)**.
Outputs land under `results/`: `qc/fastqc/`, `preprocessing/fastp/`,
`multiqc/multiqc_report.html`, and provenance in `pipeline_info/`.

**Long reads:** `--long_read` swaps in a Nanopore/PacBio path — minimap2 +
Clair3 (small variants) + Sniffles2 (structural variants) — reusing the same
annotation and report layer. See **[LONGREAD.md](docs/LONGREAD.md)**.

**Any scale, no code changes:** the same workflow runs on a laptop, an HPC
cluster (`-profile slurm,singularity`), or the cloud (`-profile aws` / `google`
/ `azure`) — only the executor profile changes. See **[CLOUD.md](docs/CLOUD.md)**.
For the design + testing/security strategy, see **[QUALITY.md](docs/QUALITY.md)**.

**Multiple samples / lanes:** samples split across lanes are merged automatically;
`--joint` runs GATK cohort joint genotyping (one multi-sample callset + a report
per sample). See **[COHORT.md](docs/COHORT.md)**. Tumor/normal somatic calling is
**[SOMATIC.md](docs/SOMATIC.md)** (`--somatic`).

**Interoperable output:** each report includes an HL7 Genomics Reporting
IG-aligned **FHIR R4** bundle (`<sample>.fhir.json`) — Patient + Specimen +
genomic-report DiagnosticReport + LOINC-coded variant Observations — with an
offline structural validator (`bin/validate_fhir.py`, run in CI). See
**[FHIR.md](docs/FHIR.md)**.

## Accuracy
Calls are scored against a truth set (precision / recall / F1, split by SNP/INDEL,
plus genotype concordance) via `--benchmark` — a stdlib exact-match backend or
GA4GH hap.py against GIAB. See **[ACCURACY.md](ACCURACY.md)** for the method and
the GIAB workflow. Example charts (illustrative, on synthetic data):

![Precision–Recall curve](docs/img/accuracy/example.pr_curve.svg)
![Genotype concordance](docs/img/accuracy/example.genotype_confusion.svg)

## Tests
The Python components (samplesheet validator, prioritization + ACMG, benchmarking,
plotting, FHIR bundle, schema) have standalone pytest suites (no pipeline needed);
CI additionally runs the full DAG in stub mode plus offline verifiers for
containers, the FHIR bundle, and the parameter schema:
```bash
pytest -q
```

## Roadmap & license
Build plan in `ROADMAP.md`: the hardening track (H1–H7), somatic (M7), cloud (M8),
long-read (M9) and polish (M10) are complete. Tools cited in
[`CITATIONS.md`](CITATIONS.md). Licensed under [MIT](LICENSE) — research use only.
