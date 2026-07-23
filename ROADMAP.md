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

## Hardening track (production-readiness)

The modules above are *built and tested on synthetic data*. This separate track
turns "works on my laptop" into "runs a real genome and cites real evidence".
These are depth/robustness items, distinct from the breadth items (M7, M9) above.

- [x] **H1  Containers** - every process pins a `container` (biocontainers, plus a
      mulled image for the multi-tool `bwa-mem2 | samtools` step) alongside its
      `conda` env. `bin/check_containers.py` enforces the "every process is
      containerized" invariant offline in CI (`tests/test_containers.py`);
      `bin/verify_containers.sh` pull-verifies every tag on a Docker/Singularity
      host. See `docs/CONTAINERS.md`. (Registry pull-verification must be run on a
      container-capable host - CI here and the dev environment have no engine and
      block the registries.)
- [ ] **H2  Real reference + cache path** - wire and test real GRCh38 plus a
      downloaded VEP/SnpEff cache (the current offline SnpEff DB is synthetic-only);
      a `--download_cache`/igenomes-style reference handling.
- [ ] **H3  Clinical + population evidence** - annotate against ClinVar, gnomAD,
      dbSNP (and COSMIC for somatic) so prioritization is evidence-cited, not just
      functional-impact; formal ACMG-style criteria.
- [ ] **H4  Accuracy benchmarking** - validate calls against a gold standard
      (GIAB HG001/HG002 + high-confidence regions) with hap.py/vcfeval; publish
      precision / recall / F1 per variant type. (See ACCURACY.md.)
- [ ] **H5  Multi-sample scale** - lane merging (cat_fastq), cohort joint
      genotyping, per-sample and per-cohort reporting.
- [ ] **H6  Real AI interpretation** - wire an actual LLM (offline/served) into the
      report's narrative hook, with strict JSON guardrails and graceful fallback.
- [ ] **H7  Full FHIR conformance** - align the Bundle with the HL7 Genomics
      Reporting IG.

Intentional scope (not defects): outputs are **research-use-only** and are not a
clinical/ACMG diagnostic. That labelling stays until real clinical validation.
