# How It Works

The runtime execution flow, step by step, from launch to report. This describes
HOW the code runs under the hood, not what or why (see README and ARCHITECTURE).

1. You launch: `nextflow run main.nf -profile <standard|conda|docker> [params]`.
2. Nextflow reads `nextflow.config`: manifest, params, the selected profile, and the provenance reporters (timeline / report / trace).
3. Nextflow builds the workflow DAG from `main.nf` and the imported modules, wiring process inputs and outputs together as channels.
4. The samplesheet is parsed into a channel of samples (germline single-sample, or somatic tumor/normal pairs). [added in M1]
5. For each sample, Nextflow schedules processes in dependency order. Each process runs in isolation in its own task directory under the work dir.
6. For each task, Nextflow generates `.command.sh` (the tool command) and `.command.run` (the wrapper), then executes it via the selected executor (local now; cloud/HPC later), provisioning the tool via a conda env or a container.
7. Stage outputs (BAMs, VCFs, reports) flow between processes as channels; `publishDir` copies final artifacts into `results/`.
8. The cascade proceeds: QC, then alignment, then variant calling, then annotation, then prioritization. [M1 to M5]
9. The AI report stage takes the prioritized variants and generates an evidence-cited HTML/PDF report. [M6]
10. Nextflow writes provenance (`timeline.html`, `report.html`, `trace.txt`) under `results/pipeline_info/`, and exits.

Current state (M0): steps 1-3, 5-7, and 10 are exercised by the `SMOKE_TEST`
process. Steps 4, 8, and 9 arrive as modules are added.
