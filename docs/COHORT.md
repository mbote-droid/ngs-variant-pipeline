# Multi-sample scale (H5): lanes + cohort joint genotyping

Two independent multi-sample features, both opt-in and both leaving the
single-sample default path byte-for-byte unchanged (so CI is unaffected):

1. **Lane merging** — a sample split across sequencing lanes is concatenated
   into one FASTQ per read end before QC/alignment. Automatic; no flag.
2. **Cohort joint genotyping** — per-sample GVCFs are combined and genotyped
   together (GATK best practice), giving one multi-sample callset plus a report
   per sample. Opt-in via `--joint`.

## 1. Lane merging (`CAT_FASTQ`)

List one row per lane, repeating the `sample` id. Rows are grouped by sample;
a sample with a single lane passes straight through, a sample with >1 lane is
merged by `CAT_FASTQ`:

```csv
sample,fastq_1,fastq_2
sample1,sample1_L001_R1.fastq.gz,sample1_L001_R2.fastq.gz
sample1,sample1_L002_R1.fastq.gz,sample1_L002_R2.fastq.gz
```

Concatenated gzip streams are themselves valid gzip, so a plain `cat` is
correct for `.gz`/bgzipped FASTQs. Merged FASTQs are intermediates (not
published). All lanes of a sample must agree on single- vs paired-end (enforced
by the samplesheet validator). See `assets/samplesheet_test_multilane.csv`.

## 2. Cohort joint genotyping (`--joint`)

```bash
nextflow run main.nf -profile docker \
  --genome GRCh38 --input cohort.csv --joint \
  --cohort_id family1 --download_snpeff_cache
```

`JOINT_GENOTYPING` (subworkflow):

1. **GATK4_HAPLOTYPECALLER** per sample in GVCF mode (`-ERC GVCF`).
2. **GATK4_COMBINEGVCFS** — merge every sample's GVCF into one cohort GVCF.
   (`GenomicsDBImport` is the alternative at very large *N*; swap in later.)
3. **GATK4_GENOTYPEGVCFS** — joint-genotype the whole cohort at once, so a
   variant seen in any sample is genotyped (incl. hom-ref) in all of them.
4. **GATK4_VARIANTFILTRATION** — hard-filter labelling → one multi-sample VCF
   (`results/variants/<cohort_id>/`), plus `bcftools stats` for MultiQC.

`--cohort_id` (default `cohort`) names the combined callset.

### Reporting

The cohort VCF is annotated once, then fanned out to reports:

- **one report per sample** — the prioritizer selects each sample's genotype
  column with `--sample <id>` (the VCF parser is sample-aware), so
  `results/report/<sample>/` reflects that sample's own genotypes.
- **one whole-cohort report** — `results/report/<cohort_id>/`, the aggregate
  variant list across the cohort.

Verify the wiring offline first (no tools/network):

```bash
nextflow run main.nf -profile test -stub --joint \
  --input assets/samplesheet_test_cohort.csv
```

## Scope / not yet wired

- **GenomicsDBImport / interval scatter** for large cohorts — `CombineGVCFs` is
  fine to low hundreds of samples; beyond that, scatter by interval and import
  into a GenomicsDB workspace.
- **VQSR** (variant recalibration) — the current hard-filter labelling is the
  small-cohort-friendly choice; VQSR needs a large truth-annotated callset.
- **Pedigree / de novo** analysis (trio calling with a PED file) is future work.

Outputs remain **research-use only**.
