# Citations

`ngs-variant-pipeline` is built on the following open-source tools and resources.
If you use it, please cite the relevant tools below.

## Pipeline framework

- **Nextflow** — Di Tommaso P, et al. *Nextflow enables reproducible computational
  workflows.* Nat Biotechnol. 2017. doi:10.1038/nbt.3820
- Pipeline structure and conventions follow the **nf-core** community standards —
  Ewels PA, et al. *The nf-core framework for community-curated bioinformatics
  pipelines.* Nat Biotechnol. 2020. doi:10.1038/s41587-020-0439-x

## Read QC & preprocessing

- **FastQC** — Andrews S. FastQC: a quality control tool for high throughput
  sequence data. 2010.
- **fastp** — Chen S, et al. *fastp: an ultra-fast all-in-one FASTQ preprocessor.*
  Bioinformatics. 2018. doi:10.1093/bioinformatics/bty560

## Alignment & BAM processing

- **BWA-MEM2** — Vasimuddin M, et al. *Efficient architecture-aware acceleration
  of BWA-MEM.* IEEE IPDPS. 2019.
- **minimap2** (long-read) — Li H. *Minimap2: pairwise alignment for nucleotide
  sequences.* Bioinformatics. 2018. doi:10.1093/bioinformatics/bty191
- **SAMtools** — Danecek P, et al. *Twelve years of SAMtools and BCFtools.*
  GigaScience. 2021. doi:10.1093/gigascience/giab008
- **mosdepth** — Pedersen BS, Quinlan AR. *Mosdepth: quick coverage calculation.*
  Bioinformatics. 2018. doi:10.1093/bioinformatics/btx699

## Variant calling

- **GATK4** (HaplotypeCaller, GenotypeGVCFs, CombineGVCFs, Mutect2, BQSR) —
  McKenna A, et al. *The Genome Analysis Toolkit.* Genome Res. 2010; and
  Poplin R, et al. *Scaling accurate genetic variant discovery to tens of
  thousands of samples.* bioRxiv. 2018. doi:10.1101/201178
- **Clair3** (long-read small variants) — Zheng Z, et al. *Symphonizing pileup
  and full-alignment for deep learning-based long-read variant calling.* Nat
  Comput Sci. 2022. doi:10.1038/s43588-022-00387-x
- **Sniffles2** (long-read structural variants) — Smolka M, et al. *Detection of
  mosaic and population-level structural variants with Sniffles2.* Nat
  Biotechnol. 2024. doi:10.1038/s41587-023-02024-y
- **BCFtools** — Danecek P, et al. GigaScience. 2021 (as above).

## Annotation & evidence

- **SnpEff** — Cingolani P, et al. *A program for annotating and predicting the
  effects of single nucleotide polymorphisms, SnpEff.* Fly. 2012.
  doi:10.4161/fly.19695
- **Ensembl VEP** — McLaren W, et al. *The Ensembl Variant Effect Predictor.*
  Genome Biol. 2016. doi:10.1186/s13059-016-0974-4
- **ClinVar** — Landrum MJ, et al. Nucleic Acids Res. 2018. doi:10.1093/nar/gkx1153
- **gnomAD** — Karczewski KJ, et al. Nature. 2020. doi:10.1038/s41586-020-2308-7
- **dbSNP** — Sherry ST, et al. Nucleic Acids Res. 2001. doi:10.1093/nar/29.1.308

## Interpretation standards

- **ACMG/AMP variant classification** — Richards S, et al. *Standards and
  guidelines for the interpretation of sequence variants.* Genet Med. 2015.
  doi:10.1038/gim.2015.30 (The pipeline implements a transparent **research-use**
  heuristic over a subset of these criteria; it is not a clinical determination.)
- **HL7 FHIR Genomics Reporting IG** — HL7 International.
  http://hl7.org/fhir/uv/genomics-reporting
- **Sequence Ontology** — Eilbeck K, et al. Genome Biol. 2005.

## Benchmarking

- **GA4GH Benchmarking / hap.py** — Krusche P, et al. *Best practices for
  benchmarking germline small-variant calls.* Nat Biotechnol. 2019.
  doi:10.1038/s41587-019-0054-x
- **Genome in a Bottle (GIAB)** — Zook JM, et al. Sci Data. 2016.
  doi:10.1038/sdata.2016.25

## Reporting & aggregation

- **MultiQC** — Ewels P, et al. *MultiQC: summarize analysis results for multiple
  tools and samples in a single report.* Bioinformatics. 2016.
  doi:10.1093/bioinformatics/btw354

## AI narrative (optional)

- The optional report narrative uses Anthropic's **Claude** via the official
  Anthropic SDK. It is off by default, sees only a de-identified digest, and is
  guardrailed (structured output + gene-grounding) with graceful fallback to a
  deterministic template. See `docs/AI_REPORT.md`.
