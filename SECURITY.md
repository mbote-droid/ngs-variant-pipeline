# Security policy

**Research use only.** This pipeline is not a validated diagnostic device and
must not be used for clinical decision-making.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab) rather than a public
issue. Include a description, affected component, and reproduction steps.

## Threat model & hardening (H8)

The primary untrusted input is **sequencing data** (FASTQ), plus any
user-supplied VCFs (ClinVar/gnomAD/dbSNP/truth/PoN). The design keeps the attack
surface small:

- **Memory-safe first line.** All `bin/` logic is stdlib-only Python (no
  `eval`/`exec`, no `pickle`, no shell built from input, no third-party parser).
  A `bandit` SAST scan runs in CI.
- **Pre-flight input gate (`--validate_inputs`).** `bin/validate_inputs.py`
  rejects, before any C/C++ tool runs: truncated or non-FASTQ files, invalid
  gzip, sequences over a DNA alphabet, oversized inputs (`--max_fastq_gb`), and
  **decompression bombs** (`--max_compression_ratio`, caught by bounded
  streaming — the file is never fully expanded). A failure aborts the run.
- **Containment.** Every tool runs in a **pinned** container (versions tracked
  for CVEs). The `docker` profile runs as the calling user (non-root) with
  `--security-opt=no-new-privileges --cap-drop=ALL`, so a tool exploited by a
  malformed input is sandboxed, not on the host.
- **No secrets / no PII exfiltration.** Offline batch job: no server, no auth,
  no stored credentials. The FHIR `Patient` is de-identified; the optional LLM
  narrative sees only a de-identified digest.
- **Dependency awareness.** `pip-audit` runs in CI (advisory) over the Python
  toolchain; container image versions are pinned and checkable.

## Not yet covered

- Container **image** CVE scanning (e.g. Trivy) is not yet wired into CI (image
  pulls are heavy); tags are pinned so this can be added.
- No cryptographic **provenance/attestation** of inputs beyond optional format
  validation.

These become first-class if/when the pipeline is exposed as a hosted service
accepting third-party uploads — see `docs/QUALITY.md` for the productization
security roadmap (authn/z, encryption, audit logging, HIPAA/GDPR).
