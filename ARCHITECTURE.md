# Architecture

A reproducible Nextflow workflow that takes raw sequencing reads to an
evidence-cited clinical report. The same pipeline runs on a laptop with small
test data or on cloud/HPC with full data, selected by a profile, with no code
change. Research use only.

## The cascade
1. Input + samplesheet (nf-core style; germline single-sample or somatic tumor/normal)
2. Read QC + trimming (FastQC, fastp, MultiQC)
3. Alignment (BWA-MEM2, sort, mark duplicates, GATK BQSR)
4. Alignment QC (samtools flagstat, mosdepth)
5. Variant calling: germline = GATK HaplotypeCaller; somatic = GATK Mutect2 (tumor/normal + panel of normals)
6. Filtering + variant QC (hard-filter/VQSR, bcftools stats)
7. Annotation (VEP or SnpEff/SnpSift + ClinVar, gnomAD, dbSNP; COSMIC for somatic)
8. Prioritization (ACMG-style tiers for germline, actionability tiers for somatic)
9. AI interpretation + report (RAG/LLM to HTML/PDF, JSON, FHIR)
10. Outputs + MultiQC aggregate

## Language roles (authentic, not forced)
- **Nextflow (DSL2):** orchestration of the whole cascade.
- **Python:** the AI/report layer, prioritization logic, and tests.
- **Perl:** one genuine text-processing step (VCF/annotation munging or BioPerl parsing).

## Infrastructure
- `nextflow.config` profiles: `standard` (local), `conda`, `docker`, `test`, and (later) cloud/HPC.
- One tool per process, provisioned by a conda env or a container.
- Provenance on every run: Nextflow `timeline`, `report`, `trace`.
- CI on push; nf-core conventions.

## Design principles
- Reproducible and portable: same pipeline, any scale.
- Modular: each stage is an independent, tested module.
- Honest and research-use-only; standard tools (GATK, VEP), not reinvented.
- Runs on constrained hardware (8 GB) with tiny test data; scales to cloud for full runs.

## Tool provisioning note
Docker is the intended portable default, but on constrained or unstable Docker
hosts the `conda` profile provisions the same tools without Docker. Both profiles
ship, so the pipeline is portable across environments.
