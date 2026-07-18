# Roadmap

Build order. Each module is a working, tested slice that plugs into the growing
whole. Germline short-read Illumina first, then somatic, then long-read.
Reference genome: GRCh38. Germline caller: GATK HaplotypeCaller.

- [x] **M0  Scaffold** - repo, Nextflow DSL2 skeleton, config + profiles, tiny smoke test, docs. (Nextflow + local execution verified.)
- [x] **M1  Input + QC** - samplesheet validation (stdlib Python + 21 pytest tests), FastQC, fastp, MultiQC; nf-core-style modules/subworkflows; every process has a `stub` so the whole DAG runs offline. (Wiring verified end-to-end via `-stub`.)
- [ ] **M2  Alignment** - BWA-MEM2, mark duplicates, BQSR, coverage QC
- [ ] **M3  Germline variant calling** - GATK HaplotypeCaller, filtering, stats
- [ ] **M4  Annotation** - VEP/SnpEff + ClinVar/gnomAD
- [ ] **M5  Prioritization** - impact filtering + ACMG-style tiers
- [ ] **M6  AI report layer** - RAG/LLM to HTML/PDF  ← a complete germline genome-to-report pipeline
- [ ] **M7  Somatic mode** - Mutect2 tumor/normal + panel of normals + COSMIC/actionability
- [ ] **M8  Integration + cloud profile** - demonstrate "same pipeline, any scale"
- [ ] **M9  Long-read add-on** - minimap2, Clair3, Sniffles2 structural variants
- [ ] **M10 Polish** - nf-core lint, provenance, README, demo data, portfolio writeup

Tool provisioning: `conda` is primary on this dev host; the `docker` profile is
retained for portability.
