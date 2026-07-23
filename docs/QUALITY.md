# Quality, testing & security strategy

This document explains **what** the pipeline is, **why** each layer exists, and
**how** it is quality-assured — including which software-testing techniques
genuinely apply to a batch genomics pipeline and which only become relevant once
it is wrapped in a hosted clinical service. Research use only.

## What this project is

A reproducible [Nextflow](https://www.nextflow.io) pipeline that takes raw DNA
sequencing reads (FASTQ) and produces an annotated, prioritized,
clinician-readable variant report plus a standards-compliant FHIR file:

```
samplesheet → QC/trim → align → call variants → annotate → prioritize → report
                                                    │
                          (germline · somatic · cohort joint genotyping)
```

It is the same *shape* of system a clinical genomics lab runs, built to
nf-core-style conventions.

## Why each layer exists (not boilerplate)

| Layer | Credibility gap it closes |
|---|---|
| **H1** pinned containers | Reproducibility — table stakes; without it, results aren't trusted |
| **H2** real reference genome | Moves from toy synthetic data to real GRCh38 |
| **H3** ClinVar/gnomAD + ACMG-style | Clinical relevance, not just raw variant coordinates |
| **H4** GIAB accuracy benchmark | **Proof** the calls are correct against the gold standard |
| **H5** lanes + cohort joint genotyping | Scale (multi-lane, multi-sample) |
| **H6** guardrailed LLM narrative | The AI differentiator, done responsibly (de-identified, grounded) |
| **H7** HL7 Genomics Reporting FHIR | Interoperability — plugs into real hospital systems |
| **M7** somatic (Mutect2) | Cancer / tumour-normal breadth |

Each item closes a specific "but is it real?" question a reviewer would ask.

## Testing strategy — what actually applies

A batch pipeline is a **different shape** from an interactive UI or a hosted
multi-user service, so most of the enterprise/UI testing catalogue does not bite
on it yet. Below is an honest mapping.

### In place today

| Technique | Where |
|---|---|
| **Unit testing** (white-box) | `tests/` — 145 pytest cases over every logic-bearing `bin/` script |
| **Integration testing** | the `-stub` DAG run wires every stage to the next and asserts each output |
| **Regression testing** | CI runs pytest + the stub DAG on every push/PR |
| **Functional testing** | tests assert correct outputs (tiers, ACMG class, metrics, FHIR shape) |
| **Smoke / sanity testing** | `nextflow run … -profile test -stub` is a full offline smoke test |
| **Accuracy / validation testing** | H4 truth-set benchmarking (GIAB + hap.py) — in genomics this *is* acceptance |
| **Negative / edge-case testing** | empty VCF, multi-allelic sites, malicious HTML injection, dangling FHIR refs, single- vs multi-lane |
| **Structural conformance** | `bin/check_containers.py`, `bin/validate_fhir.py` (run in CI) |
| **Black-box / grey-box** | the stub run exercises the DAG without touching internals |

### Your step (needs real data / real infra)

- **System / end-to-end testing** — a real run on GRCh38 (`docs/RUNBOOK_WSL.md`).
- **Performance / scale testing** — a full-genome run on the cloud profile
  (`docs/CLOUD.md`); Nextflow's `trace`/`report`/`timeline` already capture
  per-process CPU/RAM/time on every run.

### Deliberately **not** applicable yet

These target an interactive UI or a concurrent hosted service — a batch pipeline
has no UI, no install step, and no simultaneous users, so there is nothing for
them to exercise. Adding them now would be premature:

> UI/UX · GUI · usability · A/B · localization/globalization · installation ·
> browser compatibility · load · spike · stress · endurance (soak) · volume ·
> alpha/beta · UAT

They become first-class the day this becomes a hosted clinical web app — see
"When this productizes" below.

### The QA that protects a healthcare *pipeline* (priority order)

1. Truth-set accuracy benchmarking (GIAB/hap.py) — **done**
2. Reproducibility: pinned containers + deterministic output — **done**
3. Unit tests on the logic — **done**
4. Regression CI — **done**
5. Edge-case / validation testing — **done**
6. Real-data end-to-end on your host — **your step** (runbook provided)

## Security posture

### Why the attack surface is small *today*

- **Memory-safe parsers.** Every `bin/` script is **stdlib-only Python**. Python
  is memory-safe, so the classic *buffer-overflow via a malformed input file*
  vector does not exist in our own code. There is no `eval`, no shell string
  built from file contents, no deserialization of untrusted pickles.
- **Containerized tools.** The C/C++/Java tools (GATK, BWA-MEM2, samtools/htslib,
  SnpEff) *are* the historical vector for malformed-BAM/VCF crashes — but each
  runs **inside a pinned container**, so a crash or exploit is contained in the
  task sandbox, not on the host. Versions are pinned (H1) so known CVEs are
  trackable and patchable.
- **No secrets, no PII, no network service.** It's an offline batch job: no web
  server, no auth, no database, no stored credentials. The FHIR `Patient` is
  de-identified; the optional LLM sees only a de-identified digest.
- **Input structure validation.** `check_samplesheet.py` rejects malformed
  samplesheets early (bad paths, wrong FASTQ suffixes, inconsistent endedness).

### "Can malware be hidden in a DNA file?" — the honest answer

DNA *sequence* is just text (A/C/G/T); it cannot execute. The real risk is a
**malformed container format** (a crafted BAM binary structure or VCF header)
that triggers a bug in a C parser — the same class as the 2017 research that
encoded an exploit in synthesized DNA to attack a *deliberately vulnerable* C
program with a known overflow. Our mitigations: our own parsers are memory-safe,
and the vulnerable-by-nature tools are isolated in containers with pinned,
patchable versions. So we are **meaningfully hardened, but not exhaustively**.

### What is **not** yet done (the next security workstream)

Tracked honestly so it isn't mistaken for complete:

- **Input resource limits** — no max input-size / decompression-bomb guard; a
  hostile giant or highly-compressible input could exhaust disk/RAM (a DoS, not
  code execution).
- **Deep malformed-file rejection** — beyond the samplesheet, we don't pre-flight
  BAM/VCF integrity (e.g. `samtools quickcheck`, `bcftools view` validation,
  index/EOF checks) before handing files to the heavy tools.
- **Guaranteed non-root execution** — the `docker` profile already runs as the
  calling UID; this should be enforced across every container profile.
- **Dependency/CVE scanning** — no automated scan of container images or the
  (single, optional) Python dependency for published CVEs.
- **Input provenance / checksums** — no required checksum on reference or input
  files.

None of these change the *outputs* or accuracy; they are defense-in-depth for a
future where the pipeline ingests untrusted third-party uploads. A good next
hardening item ("H8: input hardening") would add `samtools quickcheck` +
`bcftools` validation gates, input size caps, non-root enforcement, and a
container-image CVE scan in CI.

## When this productizes into a hosted clinical service

At that point the threat model and the testing pyramid both expand, and the
previously "not applicable" items become mandatory:

- **Compliance**: HIPAA / GDPR, encryption at rest + in transit, audit logging,
  access control, data-retention policy.
- **Service testing**: load, spike, stress, soak, and volume testing against the
  API; security testing (authn/z, injection, dependency CVEs, pen-test);
  reliability/failover.
- **User-facing**: UI/UX, usability, accessibility, compatibility, UAT, alpha/beta.

We build that layer **deliberately when the service exists** — not preemptively
against a batch pipeline that has no surface for it.

Outputs remain **research-use only** and are not a validated diagnostic device.
