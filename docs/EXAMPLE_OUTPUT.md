# Example output

A real run of the bundled test profile (`nextflow run main.nf -profile test,conda`)
on the synthetic dataset. Outputs themselves are not committed (they are
reproducible and, on real data, contain patient information); this page is a
curated snapshot so reviewers can see what the pipeline produces without running
it. Reproduced on an 8 GB laptop, fully offline once the tool environments are
cached.

## Results tree

```
results/
├── qc/fastqc/                     raw-read FastQC (R1, R2)
├── preprocessing/fastp/sample1/   trimmed reads + fastp report
├── alignment/sample1/             analysis-ready BAM (recalibrated) + dup metrics
├── qc/alignment/sample1/          samtools flagstat, mosdepth coverage
├── variants/sample1/              filtered VCF (+ index)
├── qc/variants/sample1/           bcftools stats
├── annotation/sample1/            SnpEff-annotated VCF + CSV stats
├── report/sample1/                prioritized.tsv/json, report.html/json, fhir.json
├── multiqc/                       one report aggregating every stage
└── pipeline_info/                 software_versions.yml, timeline/report/trace
```

## Alignment QC (real numbers)

```
4200 reads, 100.00% mapped, 100.00% properly paired   (samtools flagstat)
mean coverage 33.8x over testchr                       (mosdepth)
```

## Variant calling vs. the truth set

The test data spikes three variants into a synthetic gene. HaplotypeCaller
recovers all three with the correct genotype, and SnpEff predicts exactly the
consequence each was engineered to have:

| Tier | Locus | Change | Impact | Effect | HGVS.p | Genotype | Truth |
|:----:|-------|:------:|--------|--------|--------|----------|:-----:|
| 1 | testchr:4050 | T>A | HIGH | stop_gained | p.Tyr7* | het | 0/1 ✓ |
| 2 | testchr:4111 | G>A | MODERATE | missense_variant | p.Val28Ile | hom_alt | 1/1 ✓ |
| 3 | testchr:4230 | C>A | LOW | synonymous_variant | p.Thr67Thr | het | 0/1 ✓ |

## Report

`report.html` renders the table above with a research-use banner and a
deterministic summary:

> 3 variant(s) were reported. 1 were predicted HIGH impact. 1 were predicted
> MODERATE impact. Genes with higher-impact variants: TESTG.

`report.json` carries the structured payload; `fhir.json` is a minimal FHIR R4
Bundle (one DiagnosticReport + one Observation per variant). All are labelled
**research use only** and are not a clinical ACMG classification.
