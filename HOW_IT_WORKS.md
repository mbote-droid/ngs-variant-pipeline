# How It Works

The runtime execution flow, step by step, from launch to report. This describes
HOW the code runs under the hood, not what or why (see README and ARCHITECTURE).

1. You launch: `nextflow run main.nf -profile <standard|conda|docker> [params]`.
2. Nextflow reads `nextflow.config`: manifest, params, the selected profile, and the provenance reporters (timeline / report / trace).
3. Nextflow builds the workflow DAG from `main.nf` and the imported modules, wiring process inputs and outputs together as channels.
4. The samplesheet is parsed and validated. `INPUT_CHECK` runs `bin/check_samplesheet.py` (stdlib-only Python, on Nextflow's PATH) which enforces the format, normalizes the rows, and writes `*.valid.csv`. Nextflow then `splitCsv`s that file into a channel of `[ meta, [fastqs] ]`, where `meta` carries `id`, `single_end`, and `status`. [M1]
   - QC (`FASTQ_QC`): each sample goes through `FASTQC` (raw-read quality) and `FASTP` (adapter/quality trimming, emitting trimmed FASTQs for M2). Their reports feed `MULTIQC`, which aggregates one HTML report. Every process also emits a `versions.yml`; these are collated into `pipeline_info/software_versions.yml`. [M1]
5. For each sample, Nextflow schedules processes in dependency order. Each process runs in isolation in its own task directory under the work dir.
6. For each task, Nextflow generates `.command.sh` (the tool command) and `.command.run` (the wrapper), then executes it via the selected executor (local now; cloud/HPC later), provisioning the tool via a conda env or a container.
7. Stage outputs (BAMs, VCFs, reports) flow between processes as channels; `publishDir` copies final artifacts into `results/`.
8. The cascade proceeds: QC, then alignment, then variant calling, then annotation, then prioritization. [M1 to M5]
9. The AI report stage takes the prioritized variants and generates an evidence-cited HTML/PDF report. [M6]
10. Nextflow writes provenance (`timeline.html`, `report.html`, `trace.txt`) under `results/pipeline_info/`, and exits.

Current state (M1): steps 1-7 and 10 run for real via the Input + QC stage
(`INPUT_CHECK` -> `FASTQ_QC`). Every process ships a `stub` block, so
`nextflow run main.nf -profile test -stub` exercises the whole DAG offline with
no tools or network. Steps 8 (alignment onward) and 9 (AI report) arrive as
later modules are added.
