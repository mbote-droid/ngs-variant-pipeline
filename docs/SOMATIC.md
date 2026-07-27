# Somatic mode (M7)

Tumor/normal somatic short-variant calling with **GATK4 Mutect2**. Opt-in via
`--somatic`; the default germline path is unchanged.

## Samplesheet

Somatic calling pairs a tumor with its matched normal using two columns the
samplesheet already supports:

| Column | Meaning |
|---|---|
| `status` | `0` = normal (default), `1` = tumor |
| `patient` | pairing id; the tumor and its matched normal share one `patient` |

```csv
sample,fastq_1,fastq_2,status,patient
subjectA_normal,normal_R1.fastq.gz,normal_R2.fastq.gz,0,subjectA
subjectA_tumor,tumor_R1.fastq.gz,tumor_R2.fastq.gz,1,subjectA
```

Both columns are optional and default to germline (`status` 0, `patient` =
`sample`), so existing germline samplesheets keep working untouched. See
`assets/samplesheet_test_somatic.csv` for a runnable stub example.

## Running

```bash
nextflow run main.nf -profile docker \
  --genome GRCh38 --input samplesheet_somatic.csv --somatic \
  --pon /refs/pon.vcf.gz \
  --germline_resource /refs/af-only-gnomad.vcf.gz \
  --download_snpeff_cache
```

- `--pon` — panel of normals (bgzipped + tabixed), **optional** but recommended;
  filters recurrent technical artefacts.
- `--germline_resource` — an AF-only germline resource (e.g. gnomAD) for Mutect2,
  **optional**.
- Both must be indexed (`.tbi` alongside).

Verify the pipeline wiring offline first (no tools/network):

```bash
nextflow run main.nf -profile test -stub --somatic \
  --input assets/samplesheet_test_somatic.csv
```

## Pipeline

`CALL_VARIANTS_SOMATIC` (subworkflow):

1. **Pair** tumor + normal BAMs by `meta.patient` (tumor = status 1, normal = 0).
2. **GATK4_MUTECT2** — tumor/normal calling; `--normal-sample` is the normal
   BAM's read-group SM (set by the aligner to the normal sample id). Emits the
   unfiltered VCF, its stats, and f1r2 counts. Passes `--panel-of-normals` /
   `--germline-resource` when provided.
3. **GATK4_LEARNREADORIENTATIONMODEL** — models FFPE/oxidation orientation
   artefacts from the f1r2 counts.
4. **GATK4_FILTERMUTECTCALLS** — applies somatic filters (`--ob-priors` from the
   orientation model) → the filtered somatic VCF.

The filtered VCF flows into the **same** annotation + report path as germline
(`results/variants/somatic/<sample>/`, then annotation/report). ClinVar/gnomAD
evidence (H3) and the report layer apply unchanged.

## Scope / not yet wired

- **Contamination** (`GetPileupSummaries` + `CalculateContamination`, feeding
  `--contamination-table`) is a standard refinement not yet included; the
  orientation-model + PoN filters are in place. Add it alongside
  `GATK4_FILTERMUTECTCALLS` when needed.
- **COSMIC / actionability** annotation and tumor-only mode are future work.
- Somatic accuracy benchmarking (e.g. SEQC2) differs from the germline GIAB path
  in `ACCURACY.md`.

Outputs remain **research-use only**.
