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
- [x] **M7  Somatic mode** - GATK4 Mutect2 tumor/normal (paired via samplesheet
      `patient`/`status`), read-orientation model + FilterMutectCalls, optional
      panel-of-normals & germline-resource; opt-in `--somatic`, germline path
      unchanged. See `docs/SOMATIC.md`. (Contamination table + COSMIC/actionability
      remain follow-ups.)
- [x] **M8  Integration + cloud profile** - "same pipeline, any scale": opt-in
      `slurm` (HPC), `aws` (AWS Batch), `google` (Google Cloud Batch) and `azure`
      (Azure Batch) executor profiles, each pulling `conf/cloud.config` for
      WGS/WES-scale resources + retry-with-more-memory (the dev-host caps and the
      `test`/CI path are untouched). Cloud settings are parameterized
      (`--awsqueue`, `--google_project`, ...); CI parses every profile with
      `nextflow config` (no credentials needed). See `docs/CLOUD.md`.
- [x] **M9  Long-read add-on** - opt-in `--long_read` path: minimap2
      (`map-ont`/`map-hifi`) alignment, Clair3 small-variant calling (into the
      shared annotation+report path), and Sniffles2 structural variants (separate
      SV VCF). Skips fastp/MarkDuplicates/BQSR (Illumina-specific); the
      short-read germline/somatic/joint paths are unchanged. `--long_read_platform`
      (ont/pacbio) and `--clair3_model` parameterize it; CI stub-runs the whole
      long-read DAG. See `docs/LONGREAD.md`.
- [x] **M10 Polish** - nf-core-style `nextflow_schema.json` (all 42 params
      documented) with an offline sync-checker (`bin/check_schema.py`, unit-tested
      + in CI so schema drift fails the build); `CITATIONS.md` (every tool +
      reference); MIT `LICENSE`; a reviewer-facing one-pager (`docs/PORTFOLIO.md`);
      README badges + summary refresh; manifest bumped to 1.0.0. Provenance
      (pinned containers + timeline/report/trace + collated versions) and demo
      data (synthetic `-profile test`) were already in place.

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
- [x] **H2  Real reference + cache path** - `--genome GRCh38` resolves reference
      assets from an igenomes-style map (`conf/genomes.config`); annotation cache
      is provisioned three ways - offline SnpEff build (default), downloaded SnpEff
      cache (`--download_snpeff_cache`), or Ensembl VEP (`--annotator vep`, local or
      downloaded cache). prioritize reads SnpEff ANN or VEP CSQ. See
      docs/REFERENCES.md. (Real-genome + cache download run on a Docker/WSL host;
      the default offline synthetic path is unchanged and CI-covered.)
- [x] **H3  Clinical + population evidence** - optional ClinVar / gnomAD / dbSNP
      overlay (`--clinvar/--gnomad/--dbsnp`, bcftools) feeding evidence-aware
      tiering plus a transparent **ACMG-style** classification over a subset of the
      2015 criteria (unit-tested in `tests/test_acmg.py`). Research-use labelled;
      not a clinical determination. COSMIC/somatic deferred to M7. See
      docs/EVIDENCE.md.
- [x] **H4  Accuracy benchmarking** - `--benchmark` scores calls vs a truth set
      with two interchangeable backends: a stdlib exact-match concordance (offline,
      unit-tested) and GA4GH **hap.py** for real gold standards (GIAB HG001/HG002 +
      confident BED); precision / recall / F1 per variant type. vcfeval slots in via
      the same parse->metrics pattern. See ACCURACY.md.
- [x] **H5  Multi-sample scale** - lane merging (CAT_FASTQ concatenates a
      sample's lanes; single-lane samples pass through unchanged) and cohort
      joint genotyping (`--joint`: per-sample GVCFs -> CombineGVCFs ->
      GenotypeGVCFs over the whole cohort -> one multi-sample VCF). The cohort
      callset fans out to a report per sample (prioritizer is sample-aware,
      selecting each genotype column via `--sample`) plus a whole-cohort report.
      Both opt-in; the single-sample path is unchanged. See `docs/COHORT.md`.
- [x] **H6  Real AI interpretation** - `--report_llm` wires a real LLM into the
      report narrative (Anthropic SDK, claude-opus-4-8; `ANTHROPIC_BASE_URL` for a
      self-hosted/served gateway) with strict JSON guardrails (structured output +
      a gene-grounding anti-hallucination check) and graceful fallback to the
      deterministic template. Off by default; de-identified digest only; unit-tested
      offline with an injected fake client. See `docs/AI_REPORT.md`.
- [x] **H7  Full FHIR conformance** - the report Bundle is aligned to the HL7
      Genomics Reporting IG: a de-identified Patient + Specimen + genomic-report
      DiagnosticReport + one profiled `variant` Observation per variant, each
      carrying the IG's LOINC-coded components (gene studied, DNA/AA change,
      reference assembly, ref/alt allele, allelic state, genomic source class,
      molecular consequence [Sequence Ontology], clinical significance). Entries
      use stable urn:uuid fullUrls so references resolve inside the bundle and
      output is reproducible. `bin/validate_fhir.py` is an offline structural
      conformance gate (mandatory elements, component values, reference
      resolution) run in CI; authoritative IG profile validation on a FHIR host
      is documented. Assembly + germline/somatic source class are set per run.
      See `docs/FHIR.md`.

Intentional scope (not defects): outputs are **research-use-only** and are not a
clinical/ACMG diagnostic. That labelling stays until real clinical validation.
