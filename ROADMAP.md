# Roadmap

Build order. Each module is a working, tested slice that plugs into the growing
whole. Germline short-read Illumina first, then somatic, then long-read.
Reference genome: GRCh38. Germline caller: GATK HaplotypeCaller.

- [x] **M0  Scaffold** - repo, Nextflow DSL2 skeleton, config + profiles, tiny smoke test, docs. (Nextflow + local execution verified.)
- [x] **M1  Input + QC** - samplesheet validation (stdlib Python + 21 pytest tests), FastQC, fastp, MultiQC; nf-core-style modules/subworkflows; every process has a `stub` so the whole DAG runs offline. (Wiring verified end-to-end via `-stub`.)
- [x] **M2  Alignment** - reference indexing (faidx, dict, BWA-MEM2), BWA-MEM2 align + sort, GATK MarkDuplicates, GATK BQSR (skippable), coverage QC (samtools flagstat, mosdepth).
- [x] **M3  Germline variant calling** - GATK HaplotypeCaller (GVCF) -> GenotypeGVCFs -> hard-filter labelling; bcftools stats.
- [x] **M4  Annotation** - SnpEff with a database built offline from the reference + GFF3 (no multi-GB cache download); CSV stats to MultiQC. (VEP is the intended cloud/full-scale alternative.)
- [x] **M5  Prioritization** - impact/ACMG-style tiering (stdlib Python + pytest); research-use labelled.
- [x] **M6  Report layer** - deterministic HTML + JSON + minimal FHIR R4 report (stdlib Python + pytest); works fully offline, optional LLM narrative enrichment. ← a complete germline reads-to-report pipeline
- [ ] **M7  Somatic mode** - Mutect2 tumor/normal + panel of normals + COSMIC/actionability
- [ ] **M8  Integration + cloud profile** - demonstrate "same pipeline, any scale"
- [ ] **M9  Long-read add-on** - minimap2, Clair3, Sniffles2 structural variants
- [ ] **M10 Polish** - nf-core lint, provenance, README, demo data, portfolio writeup

Tool provisioning: `conda` is primary on this dev host; the `docker` profile is
retained for portability.
