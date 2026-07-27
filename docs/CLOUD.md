# Cloud & HPC execution (M8): same pipeline, any scale

The pipeline is a single Nextflow workflow; **where** it runs is chosen entirely
by profile. The same `main.nf` runs on your 8 GB laptop, an HPC cluster, or a
cloud batch service with **no code changes** — only the executor and resource
ceilings differ.

```
-profile conda                 # local, conda-provisioned tools (dev/laptop)
-profile docker                # local, containers
-profile test -stub            # offline smoke test (CI)
-profile slurm,singularity     # HPC cluster
-profile aws                   # AWS Batch
-profile google                # Google Cloud Batch
-profile azure                 # Azure Batch
```

Cloud/HPC profiles pull in `conf/cloud.config`, which raises the per-process
CPU/RAM/time from the dev-host caps (`conf/base.config`) to WGS/WES scale and
retries with more memory on transient/preemption failures. The default and
`test` paths are untouched, so local runs and CI behave exactly as before.

## HPC (SLURM)

On a shared cluster, submit through the scheduler and provision tools with
Singularity (no root/daemon needed):

```bash
nextflow run main.nf -profile slurm,singularity \
  --genome GRCh38 --input samplesheet.csv \
  --outdir /scratch/$USER/results -work-dir /scratch/$USER/work
```

`executor.queueSize = 50` caps concurrent jobs; tune to your allocation. Adjust
`conf/cloud.config` resource labels to your partition's limits.

## AWS Batch

Prerequisites (one-time, in your AWS account): a Batch **compute environment** +
**job queue**, and an S3 bucket for the work directory. Then:

```bash
nextflow run main.nf -profile aws \
  --genome GRCh38 --input s3://my-bucket/samplesheet.csv \
  --awsqueue my-batch-queue --awsregion us-east-1 \
  --outdir s3://my-bucket/results \
  -work-dir s3://my-bucket/work
```

- `--awsqueue` is required (the Batch job queue name).
- The work dir **must** be an `s3://` path; AWS Batch provides Docker, so no
  extra container flag is needed.
- Credentials come from the standard AWS chain (env vars, `~/.aws`, or the
  instance role).

## Google Cloud Batch

Prerequisites: a GCP project with the Batch API enabled and a GCS bucket.

```bash
nextflow run main.nf -profile google \
  --genome GRCh38 --input gs://my-bucket/samplesheet.csv \
  --google_project my-gcp-project --google_location us-central1 \
  --outdir gs://my-bucket/results \
  -work-dir gs://my-bucket/work
```

Authenticate with `gcloud auth application-default login` (or a service account).

## Azure Batch

Prerequisites: an Azure Batch account and a Storage account.

```bash
nextflow run main.nf -profile azure \
  --genome GRCh38 --input az://my-container/samplesheet.csv \
  --azure_batch_account mybatch --azure_storage_account mystorage \
  --outdir az://my-container/results \
  -work-dir az://my-container/work
```

Set `AZURE_BATCH_KEY` and `AZURE_STORAGE_KEY` (or use managed identity) per the
[Nextflow Azure docs](https://www.nextflow.io/docs/latest/azure.html).

## Verifying the wiring offline first

You cannot run a real cloud job without an account, but you can confirm the DAG
and stub outputs locally before spending anything:

```bash
nextflow run main.nf -profile test -stub
```

Cloud config **syntax** is checked in CI by `nextflow config -profile <name>`
(see `.github/workflows/ci.yml`), so a broken profile fails fast without needing
cloud credentials.

## Notes

- **Reproducibility carries over:** the same pinned containers (H1) run
  everywhere, so a cloud run and a laptop run use identical tool versions.
- **Provenance:** Nextflow's `timeline`/`report`/`trace` (already enabled) record
  per-process CPU/RAM/time — your performance/scale evidence, no extra tooling.
- **Cost control:** prefer spot/preemptible instances; the retry-with-more-memory
  strategy in `conf/cloud.config` absorbs the resulting transient failures.

Outputs remain **research use only**.
