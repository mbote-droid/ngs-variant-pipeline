# ngs-variant-pipeline

[![CI](https://github.com/mbote-droid/ngs-variant-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/mbote-droid/ngs-variant-pipeline/actions/workflows/ci.yml)

A reproducible, containerized clinical-genomics pipeline built with **Nextflow**:
from raw sequencing reads to an evidence-cited, clinician-readable report. It runs
identically on a laptop (small data) or on cloud/HPC (full data), and layers an AI
interpretation stage on top of standard best-practice genomics tooling.

> Status: **Module 1 (Input + QC).** See `ROADMAP.md` for the build plan and
> `ARCHITECTURE.md` for the full design. Research use only.

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
Outputs land under `results/`: `qc/fastqc/`, `preprocessing/fastp/`,
`multiqc/multiqc_report.html`, and provenance in `pipeline_info/`.

## Tests
The samplesheet validator has a standalone pytest suite (no pipeline needed):
```bash
pytest -q
```

## Roadmap (short)
Germline short-read Illumina first, then somatic, then long-read. See `ROADMAP.md`.
