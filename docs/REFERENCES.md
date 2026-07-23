# References & annotation caches (H2)

The pipeline defaults to a **fully offline synthetic** reference (the `test`
profile). H2 adds a real-genome path: select a genome by key, and choose how the
functional-annotation cache is provisioned.

## Selecting a reference: `--genome`

`conf/genomes.config` maps a genome key to its reference assets. `--genome GRCh38`
resolves `--fasta` and `--known_sites` (dbSNP for BQSR) for you:

```bash
nextflow run main.nf -profile docker \
  --input samplesheet.csv --genome GRCh38
```

Explicit params always override the map, so `--fasta my.fa` wins over `--genome`.
The bundled `GRCh38` / `GRCh37` entries point at public Broad/GATK resource-bundle
URLs on Google public genomics data; Nextflow stages them over https. Reference
**indices** (`.fai`, `.dict`, BWA-MEM2) are built once by `PREPARE_GENOME` from the
FASTA — correct for any genome, just slower for a full human reference (prebuilt
igenomes-style index staging is a future optimisation).

## Annotation cache: SnpEff or VEP (`--annotator`)

The synthetic default builds a tiny SnpEff DB from the reference + GFF3, offline.
For a real genome you have three choices:

| Command | What happens |
|---|---|
| *(default)* | Build a SnpEff DB offline from `--fasta` + `--gff` (synthetic-safe) |
| `--download_snpeff_cache` | `snpEff download` a prebuilt DB (`snpeff_db`, e.g. `GRCh38.105`) |
| `--annotator vep --vep_cache <dir>` | Annotate with a local Ensembl VEP cache |
| `--annotator vep --download_vep_cache` | Download the VEP cache first (`vep_install`) |

`prioritize_variants.py` reads **either** SnpEff `ANN` or VEP `CSQ`, so the report
works whichever annotator you pick.

## Running on Ubuntu (WSL)

- **Engine:** enable Docker Desktop's WSL integration and run `-profile docker`,
  or use `-profile conda` (micromamba) if you'd rather not run Docker.
- **Disk:** a full GRCh38 reference + VEP/SnpEff human cache is tens of GB. Keep
  the reference, work dir, and caches on the **Linux filesystem** (e.g.
  `~/refs`, `~/work`), *not* under `/mnt/c` — the Windows-drive mount is far
  slower and can break file locking. Set `-work-dir ~/work` accordingly.
- **First run is slow:** indexing a human FASTA and downloading a cache each take
  a while; both are cached and reused on later runs.
- **Verify container tags first:** `bin/verify_containers.sh` pull-checks every
  image before a long run (see docs/CONTAINERS.md).

> The reference URLs and cache versions are pinned in `conf/genomes.config`;
> bump them there rather than in process code.
