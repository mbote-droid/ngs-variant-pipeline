# Real-data runbook (Ubuntu / WSL)

A copy-paste guide to run the pipeline on a **real genome** with **real evidence**
and a **GIAB accuracy benchmark**, on Ubuntu under WSL2. The bundled `test`
profile proves wiring offline; this proves it on real data.

> Everything the sandbox/CI could not run — real GRCh38, cache downloads, hap.py,
> container pulls — happens here. Commands are exact; verify large-file URLs are
> current before a long download.

---

## 0. Prerequisites (once)

**Tools.** Either is fine; Docker is the portable default.

```bash
# Option A - Docker Desktop with WSL integration (Settings > Resources > WSL)
docker run --rm hello-world           # must succeed inside WSL

# Option B - no Docker: micromamba (the pipeline's conda profile)
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)

# Nextflow + Java 17+
curl -s https://get.nextflow.io | bash && sudo mv nextflow /usr/local/bin/
nextflow -version
```

**Disk & filesystem — important.** Real references + caches are tens of GB. Keep
**everything on the Linux filesystem**, never under `/mnt/c` (the Windows mount is
slow and breaks file locking):

```bash
mkdir -p ~/ngs/{refs,cache,evidence,giab,work,results}
cd ~/ngs
git clone https://github.com/mbote-droid/ngs-variant-pipeline.git
cd ngs-variant-pipeline
```

Point Nextflow's work dir at the Linux fs and cap resources to your box:

```bash
export NXF_WORK=~/ngs/work
# add --max_cpus / --max_memory to runs, e.g. --max_cpus 8 --max_memory 28.GB
```

**Verify container images pull** before any long run (the H1 check):

```bash
bin/verify_containers.sh                 # docker pull every pinned image
# ENGINE=singularity bin/verify_containers.sh
```

---

## 1. Smoke test on real tools (small, fast)

Confirm the whole toolchain works end-to-end on the bundled synthetic data with
**real** tools (not stubs):

```bash
nextflow run main.nf -profile test,docker -work-dir ~/ngs/work
# or:  -profile test,conda
```

Expect `results/report/sample1/sample1.report.html` and a green run. If this
fails, fix it before touching real data.

---

## 2. Real GRCh38 + annotation cache (H2)

`--genome GRCh38` resolves the reference + dbSNP from `conf/genomes.config`
(staged over https). Pick **one** annotation path:

```bash
# 2a. SnpEff with a downloaded prebuilt human DB
nextflow run main.nf -profile docker \
  --genome GRCh38 --input samplesheet.csv \
  --download_snpeff_cache \
  --max_cpus 8 --max_memory 28.GB -work-dir ~/ngs/work

# 2b. Ensembl VEP instead (downloads the VEP cache)
nextflow run main.nf -profile docker \
  --genome GRCh38 --input samplesheet.csv \
  --annotator vep --download_vep_cache \
  --vep_genome GRCh38 --vep_species homo_sapiens --vep_cache_version 111 \
  --max_cpus 8 --max_memory 28.GB -work-dir ~/ngs/work
```

`samplesheet.csv` is `sample,fastq_1,fastq_2` (see `assets/samplesheet_test.csv`);
leave `fastq_2` empty for single-end.

> First run downloads the reference indices + cache (slow, once). Reference
> indexing of a full human FASTA is CPU/RAM heavy — use a machine with ≥ 8 cores
> and ≥ 28 GB if you can; otherwise expect it to take a while.

---

## 3. Clinical + population evidence (H3)

Download the evidence tracks (bgzipped VCFs), then pass them in. Confirm current
URLs/filenames at the sources before downloading.

```bash
cd ~/ngs/evidence
# ClinVar (GRCh38)
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi
# gnomAD genomes sites (large; a chromosome subset is fine for a region run)
#   https://gnomad.broadinstitute.org/downloads
# dbSNP (GRCh38)
#   https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/
cd ~/ngs/ngs-variant-pipeline
```

```bash
nextflow run main.nf -profile docker \
  --genome GRCh38 --input samplesheet.csv --download_snpeff_cache \
  --clinvar ~/ngs/evidence/clinvar.vcf.gz \
  --gnomad  ~/ngs/evidence/gnomad.sites.vcf.gz \
  --dbsnp   ~/ngs/evidence/dbsnp.vcf.gz \
  --max_cpus 8 --max_memory 28.GB -work-dir ~/ngs/work
```

The report (`results/report/<sample>/`) now carries ClinVar significance, gnomAD
AF, dbSNP IDs, and the ACMG-style class. See `docs/EVIDENCE.md`. If gnomAD encodes
AF differently than `INFO/AF`, adjust the `-c` mapping in
`modules/local/evidence_annotate.nf`.

---

## 4. Accuracy benchmark against GIAB (H4)

The credible, publication-comparable number: run on a **GIAB** sample and score
with **hap.py**. HG002 (Ashkenazi son) is the usual reference.

**4a. Get the truth set + confident regions (GRCh38, v4.2.1):**

```bash
cd ~/ngs/giab
BASE=https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38
wget $BASE/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
wget $BASE/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi
wget $BASE/HG002_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed
cd ~/ngs/ngs-variant-pipeline
```

**4b. Reads.** You need HG002 Illumina reads in your samplesheet. Full 30× WGS is
huge — for a laptop, use a **chr20 subset**: obtain HG002 reads from the GIAB FTP
(`.../HG002_NA24385_son/`) and, if needed, subset the aligned BAM to chr20 and
re-extract FASTQ, or start from a chr20 read set. (A full-genome run needs a
capable machine; a single-chromosome run is laptop-feasible.)

**4c. Run with benchmarking on:**

```bash
nextflow run main.nf -profile docker \
  --genome GRCh38 --input samplesheet_hg002.csv --download_snpeff_cache \
  --benchmark --benchmark_tool happy \
  --truth     ~/ngs/giab/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz \
  --truth_bed ~/ngs/giab/HG002_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed \
  --max_cpus 8 --max_memory 28.GB -work-dir ~/ngs/work
```

**Outputs** land in `results/benchmark/<sample>/`:

```
<sample>.benchmark.json        precision / recall / F1 (ALL, SNP, INDEL)
<sample>.benchmark.tsv         same, MultiQC-friendly
<sample>.pr_curve.svg          precision–recall curve
<sample>.f1_by_type.svg        F1 by variant type
<sample>.genotype_confusion.svg
```

`--benchmark_tool builtin` uses the offline stdlib matcher instead (good for the
synthetic truth set / a quick check); `happy` is the rigorous GA4GH engine and is
what makes your numbers comparable to DeepVariant / GATK / nf-core-sarek papers.

---

## 5. Prioritizer accuracy — ROC / PR-AUC (needs ClinVar from step 3)

Evaluate prioritization as a classifier against ClinVar labels:

```bash
eval_prioritizer.py results/report/<sample>/<sample>.prioritized.json \
  --score impact --sample <sample> \
  --json results/benchmark/<sample>/<sample>.eval.json \
  --tsv  results/benchmark/<sample>/<sample>.eval.tsv

plot_accuracy.py results/benchmark/<sample>/<sample>.eval.json \
  --outdir results/benchmark/<sample> --prefix <sample>
# -> <sample>.roc.svg  and  <sample>.pr_auc.svg
```

`--score impact` is the independent test (functional impact vs ClinVar);
`--score acmg` reports self-consistency. See `docs/EVIDENCE.md`.

---

## 6. Publish the numbers

Drop the real `results/benchmark/<sample>/*.svg` into `docs/img/accuracy/` and
update `ACCURACY.md` / the README to point at them, replacing the illustrative
synthetic examples. Those charts + the hap.py precision/recall/F1 are the
showcase.

---

## Troubleshooting (WSL-specific)

- **`no space left on device`** — you're probably on `/mnt/c` or the WSL disk is
  full. Keep refs/cache/work on the Linux fs; grow the WSL2 vdisk if needed.
- **Docker not found in WSL** — enable *Settings → Resources → WSL integration* in
  Docker Desktop for your distro, reopen the shell.
- **Reference indexing OOM/slow** — raise `--max_memory`, or run on a bigger
  machine for the one-time index build; indices are cached under the work dir.
- **`hap.py` errors** — run it via the container (`-profile docker`/`singularity`);
  it is Python-2-era and painful to install natively.
