# FHIR output (H7): HL7 Genomics Reporting IG-aligned bundle

Every report emits `results/report/<sample>/<sample>.fhir.json` — a **FHIR R4
collection Bundle** aligned to the [HL7 Genomics Reporting Implementation
Guide](http://hl7.org/fhir/uv/genomics-reporting) so the results can be ingested
by a FHIR-aware EHR/LIS or knowledge base without bespoke parsing.

**Research use only.** The bundle is labelled RESEARCH USE ONLY in the
`DiagnosticReport.conclusion`; it is not a validated diagnostic document.

## Bundle shape

```
Bundle (collection)
├── Patient          de-identified: a research sample id only (no name/DOB/PII)
├── Specimen         DNA specimen, linked to the Patient
├── DiagnosticReport profile: .../genomic-report  (LOINC 51969-4)
│     subject → Patient, specimen → Specimen, result → [Observations]
│     conclusion = deterministic narrative + "RESEARCH USE ONLY."
└── Observation …    one per variant, profile: .../variant  (LOINC 69548-6)
      subject → Patient, specimen → Specimen, value = "Present" (LA9633-4)
```

Entries are addressed by **stable `urn:uuid` fullUrls** (deterministic UUIDv5 of
`sample / resource-type / key`), so the graph is self-contained, references
resolve inside the bundle, and re-running on the same input yields byte-identical
UUIDs (reproducibility).

## Variant Observation components

Each variant Observation carries the IG's LOINC-coded components:

| LOINC | Meaning | Value |
|---|---|---|
| `48018-6` | Gene studied | CodeableConcept (HGNC symbol) |
| `62374-4` | Reference assembly | LOINC answer (GRCh38 `LA26806-2`, GRCh37 `LA14029-5`) |
| `48013-7` | Genomic reference sequence | chromosome |
| `exact-start-end` | Genomic coordinate | Range (1-based start) — IG tbd-codes |
| `69547-8` / `69551-0` | Ref / alt allele | string |
| `48004-6` / `48005-3` | DNA / amino-acid change | HGVS `c.` / `p.` |
| `53034-5` | Allelic state | Heterozygous `LA6706-1` / Homozygous `LA6705-3` |
| `48002-0` | Genomic source class | Germline `LA6683-2` / Somatic `LA6684-0` |
| `48006-1` | Molecular consequence | Sequence Ontology term (e.g. `SO:0001583`) |
| `53037-8` | Clinical significance | LOINC answer from ClinVar / ACMG-style class |

Assembly and source class are set per run: the pipeline passes
`--assembly <params.genome>` and `--source-class germline|somatic` (from
`--somatic`) to `generate_report.py`. Clinical significance uses the ClinVar
assertion when present, otherwise the pipeline's transparent ACMG-style class
(both research-use; see `EVIDENCE.md`).

## Validation

Two levels:

1. **Offline structural gate (in CI, no dependencies).**
   `bin/validate_fhir.py <bundle>.fhir.json` checks mandatory elements, that
   every component has a `value[x]`, and that every internal reference resolves.
   It runs in CI against the stub-run bundle and is also unit-tested
   (`tests/test_fhir_bundle.py`). This catches the mistakes that break bundle
   consumers, but it is **not** full profile validation.

2. **Authoritative IG profile validation (on a FHIR host).** For true
   conformance, run the official HL7 FHIR validator with the genomics-reporting
   package (needs Java + network):

   ```bash
   # one-time: get the validator jar from https://github.com/hapifhir/org.hl7.fhir.core/releases
   java -jar validator_cli.jar results/report/*/**.fhir.json \
     -version 4.0.1 \
     -ig hl7.fhir.uv.genomics-reporting#2.0.0
   ```

## Scope / known simplifications

- Molecular consequence and clinical significance are carried as **components**
  on the variant Observation rather than as separate `molecular-consequence` /
  `genomic-implication` Observations linked by `derivedFrom`. This is simpler for
  consumers and keeps the bundle compact; splitting them out is a drop-in
  extension if a downstream system requires the separate profiles.
- Gene is coded by HGNC **symbol** (display) rather than HGNC id, since the
  annotation layer emits symbols.
- `Patient` is intentionally minimal and de-identified (no demographics).

Outputs remain **research-use only**.
