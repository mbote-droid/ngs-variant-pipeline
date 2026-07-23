# Long-read mode (M9): Nanopore / PacBio

Opt-in long-read variant calling with **minimap2** (alignment), **Clair3**
(small variants) and **Sniffles2** (structural variants), instead of the
short-read Illumina path. Enable with `--long_read`; the short-read
germline/somatic/joint paths are unchanged.

## Why a separate path

Long reads (Oxford Nanopore, PacBio HiFi) have a different error profile and
enable calls short reads can't make, so the tooling differs:

| Stage | Short-read (Illumina) | Long-read (`--long_read`) |
|---|---|---|
| Trim/QC | fastp | *(skipped — long reads aren't adapter-trimmed the same way)* |
| Align | BWA-MEM2 | **minimap2** (`map-ont` / `map-hifi`) |
| Dedup / BQSR | MarkDuplicates + BQSR | *(skipped — Illumina-specific)* |
| Small variants | GATK HaplotypeCaller | **Clair3** (deep-learning caller) |
| Structural variants | — | **Sniffles2** (INS/DEL/DUP/INV/BND) |

Clair3's small-variant VCF flows into the **same** annotation + report path
(SnpEff/VEP → prioritize → HTML/JSON/FHIR), so the report layer is identical.
The Sniffles2 SV VCF is emitted separately (structural variants use different
annotation than the small-variant report).

## Samplesheet

Long reads are single-file (no R1/R2) — leave `fastq_2` empty:

```csv
sample,fastq_1,fastq_2
subjectA,subjectA.ont.fastq.gz,
```

See `assets/samplesheet_test_longread.csv` for a runnable stub example.

## Running

```bash
nextflow run main.nf -profile docker \
  --genome GRCh38 --input longreads.csv \
  --long_read --long_read_platform ont \
  --clair3_model /models/r1041_e82_400bps_sup_v500 \
  --download_snpeff_cache
```

- `--long_read_platform` — `ont` (Nanopore, default → minimap2 `map-ont`,
  Clair3 `--platform ont`) or `pacbio` (HiFi → `map-hifi`, Clair3 `--platform
  hifi`).
- `--clair3_model` — **required for a real run**: the platform/chemistry-matched
  Clair3 model directory (download from the
  [Clair3 model zoo](https://github.com/HKU-BAL/Clair3#pre-trained-models); ONT
  models also ship with `rerio`). Pick the model that matches your basecaller
  and chemistry — the wrong model degrades accuracy.

Verify the wiring offline first (no tools/network, no model needed):

```bash
nextflow run main.nf -profile test -stub \
  --long_read --input assets/samplesheet_test_longread.csv
```

## Outputs

```
results/
├── alignment/<sample>/<sample>.sorted.bam        # minimap2
├── variants/<sample>/<sample>.clair3.vcf.gz       # Clair3 small variants
├── variants/<sample>/sv/<sample>.sniffles.vcf     # Sniffles2 structural variants
├── annotation/<sample>/…                          # same annotation as short-read
└── report/<sample>/…                              # HTML + JSON + FHIR
```

## Scope / not yet wired

- **Phasing** (WhatsHap) and **methylation** (from ONT modified-basecalling) are
  natural long-read add-ons not yet included.
- **SV annotation / merging** (e.g. AnnotSV, or multi-sample SV merging with
  Jasmine) is future work; Sniffles2 output is currently emitted raw.
- **Long-read somatic** (e.g. ClairS) and long-read joint genotyping are out of
  scope for this iteration — long-read mode is single-sample germline.
- **Accuracy benchmarking** for long reads uses the same `--benchmark` machinery
  against a matched truth set, but is validated on the short-read path.

Outputs remain **research use only**.
