# Containers (H1)

Every process in this pipeline is pinned to **both** a conda environment and a
container image. Provisioning is chosen at runtime by profile, with no change to
the process code:

| Profile       | Provisioning                                  | Best for                    |
|---------------|-----------------------------------------------|-----------------------------|
| `conda`       | micromamba builds each `conda` env            | low-RAM dev hosts, no Docker |
| `docker`      | pulls each `container` image                  | portable cloud/CI default    |
| `singularity` | converts each `container` image via `docker://` | HPC without a Docker daemon |

```bash
nextflow run main.nf -profile test,docker
nextflow run main.nf -profile test,singularity
nextflow run main.nf -profile test,conda
```

## Image strategy

- **Single-tool processes** use the tool's [biocontainers](https://biocontainers.pro/)
  image, pinned to the same version as the `conda` directive
  (e.g. `biocontainers/fastqc:0.12.1--hdfd78af_0`).
- **Pure-Python, stdlib-only** helpers (`SAMPLESHEET_CHECK`,
  `PRIORITIZE_VARIANTS`, `GENERATE_REPORT`) use the official `python:3.11-slim`
  image — no third-party packages are needed.
- **The one multi-tool step**, `BWAMEM2_MEM` (`bwa-mem2 | samtools`), needs a
  single image carrying both tools, so it uses a pinned **mulled** biocontainer.
  That image bundles `samtools 1.16.1` while the `conda` pin is `1.19.2`; only
  `samtools sort`/`index` are used here, so the two are output-equivalent, and
  `versions.yml` records whatever actually ran. To regenerate a version-matched
  image, use [Seqera Wave](https://seqera.io/wave/) on a connected host:

  ```bash
  wave --conda-package bwa-mem2=2.2.1 --conda-package samtools=1.19.2
  ```

## Verification — two halves

Container correctness is verified in two complementary steps.

### 1. Offline (runs in CI)

`bin/check_containers.py` asserts that every process module declares both a
`conda` and a `container` directive, that the container string is well-formed,
and (as a warning) that the tag version lines up with the conda pin. It needs no
container engine or network, so it runs in the existing pytest job and is
covered by `tests/test_containers.py`.

```bash
python3 bin/check_containers.py          # or: pytest -q tests/test_containers.py
```

This is the regression guard that would have caught the previously
un-containerized `BWAMEM2_MEM` step.

### 2. On a Docker/Singularity host (manual, one-off)

Offline checks cannot confirm a tag actually **exists in the registry**. Run the
pull-verifier once on a container-capable host to prove every pinned image
resolves and pulls:

```bash
bin/verify_containers.sh                     # docker pull each image
ENGINE=singularity bin/verify_containers.sh  # or pull via docker:// into .sif
```

> This step is intentionally **not** in CI: the CI runner here has no container
> engine, and this project's dev/agent environment blocks the container
> registries (`quay.io`, `depot.galaxyproject.org`) at the network policy. Run
> it wherever you actually execute the `docker`/`singularity` profiles.
