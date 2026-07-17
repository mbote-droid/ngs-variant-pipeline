# Genome-to-Report Pipeline

A reproducible, containerized clinical-genomics pipeline built with **Nextflow**:
from raw sequencing reads to an evidence-cited, clinician-readable report. It runs
identically on a laptop (small data) or on cloud/HPC (full data), and layers an AI
interpretation stage on top of standard best-practice genomics tooling.

> Status: **Module 0 (scaffold).** See `ROADMAP.md` for the build plan and
> `ARCHITECTURE.md` for the full design. Research use only.

## Requirements
- Nextflow (>= 24.04), Java 17-21
- Docker (for containerized tools)

## Quick start (smoke test)
```bash
nextflow run main.nf -profile docker
```
This runs a one-step pipeline in an Ubuntu container and writes
`results/smoke_test.txt`, confirming the Nextflow + Docker toolchain is working.
Provenance reports (timeline, report, trace) are written under
`results/pipeline_info/`.

## Roadmap (short)
Germline short-read Illumina first, then somatic, then long-read. See `ROADMAP.md`.
