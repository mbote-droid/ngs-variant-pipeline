# How It Works

The runtime execution flow, step by step, from launch to report. This describes
HOW the code runs under the hood, not what or why (see README and ARCHITECTURE).

1. You launch: `nextflow run main.nf -profile <standard|conda|docker> [params]`.
2. Nextflow reads `nextflow.config`: manifest, params, the selected profile, and the provenance reporters (timeline / report / trace).
3. Nextflow builds the workflow DAG from `main.nf` and the imported modules, wiring process inputs and outputs together as channels.
4. The reference is indexed once (`PREPARE_GENOME`): `samtools faidx` (.fai), GATK `CreateSequenceDictionary` (.dict), `bwa-mem2 index`, and a bgzipped+tabixed known-sites VCF for BQSR. These are value channels, reused across every sample. [M2]
5. The samplesheet is parsed and validated. `INPUT_CHECK` runs `bin/check_samplesheet.py` (stdlib-only Python, on Nextflow's PATH) which enforces the format, normalizes the rows, and writes `*.valid.csv`. Nextflow then `splitCsv`s that file into a channel of `[ meta, [fastqs] ]`, where `meta` carries `id`, `single_end`, and `status`. [M1]
   - **QC** (`FASTQ_QC`): each sample goes through `FASTQC` (raw-read quality) and `FASTP` (adapter/quality trimming, emitting trimmed FASTQs). [M1]
   - **Align** (`ALIGN`): `BWAMEM2_MEM` aligns the trimmed reads and pipes to `samtools sort`; `GATK4_MARKDUPLICATES` marks duplicates; optionally `GATK4_BASERECALIBRATOR` + `GATK4_APPLYBQSR` recalibrate base qualities; `SAMTOOLS_FLAGSTAT` and `MOSDEPTH` produce alignment QC. [M2]
   - **Call** (`CALL_VARIANTS`): `GATK4_HAPLOTYPECALLER` (GVCF) -> `GATK4_GENOTYPEGVCFS` -> `GATK4_VARIANTFILTRATION` (hard-filter labelling); `BCFTOOLS_STATS` for QC. [M3]
   - **Annotate** (`ANNOTATE`): `SNPEFF_BUILD` builds a database from the reference + GFF3 offline, then `SNPEFF_ANN` annotates the VCF and writes a CSV stats file. [M4]
   - **Report** (`REPORT`): `PRIORITIZE_VARIANTS` (`bin/prioritize_variants.py`) tiers variants by predicted impact; `GENERATE_REPORT` (`bin/generate_report.py`) writes an HTML + JSON + minimal FHIR R4 report. Both are stdlib-only and run offline; an LLM narrative is optional. [M5, M6]
   - Every process emits a `versions.yml`; these are collated into `pipeline_info/software_versions.yml`, and QC files from every stage feed a single top-level `MULTIQC` report.
6. For each sample, Nextflow schedules processes in dependency order. Each process runs in isolation in its own task directory under the work dir.
7. For each task, Nextflow generates `.command.sh` (the tool command) and `.command.run` (the wrapper), then executes it via the selected executor (local now; cloud/HPC later), provisioning the tool via a conda env or a container.
8. Stage outputs (BAMs, VCFs, reports) flow between processes as channels; `publishDir` copies final artifacts into `results/`.
9. Nextflow writes provenance (`timeline.html`, `report.html`, `trace.txt`) under `results/pipeline_info/`, and exits.

Current state: the full germline cascade (M1-M6) is implemented and wired.
Every process ships a `stub` block, so `nextflow run main.nf -profile test -stub`
exercises the whole DAG offline with no tools or network. Stages can be skipped
with `--skip_bqsr`, `--skip_annotation`, and `--skip_report`. Somatic mode,
long-read support, and the cloud profile are the next modules (see ROADMAP.md).
