"""
Unit tests for the HL7 Genomics Reporting IG-aligned FHIR bundle (H7) in
bin/generate_report.py plus the standalone bin/validate_fhir.py checker.
Fully offline; no pipeline, no network, no FHIR validator.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin"
_spec = importlib.util.spec_from_file_location("generate_report", _BIN / "generate_report.py")
gr = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(gr)

_vspec = importlib.util.spec_from_file_location("validate_fhir", _BIN / "validate_fhir.py")
vf = importlib.util.module_from_spec(_vspec)
assert _vspec and _vspec.loader
_vspec.loader.exec_module(vf)


def _variant(**over):
    v = {
        "tier": 1, "chrom": "chr17", "pos": 43093464, "ref": "C", "alt": "T",
        "gene": "BRCA1", "impact": "HIGH", "effect": "stop_gained",
        "hgvs_c": "c.100C>T", "hgvs_p": "p.Gln34Ter", "genotype": "het",
        "filter": "PASS", "clinvar_sig": "Pathogenic",
        "acmg_classification": "Pathogenic",
    }
    v.update(over)
    return v


def _summary(variants=None, sample="sampleX"):
    variants = variants if variants is not None else [_variant()]
    counts = {str(t): sum(1 for v in variants if v["tier"] == t) for t in (1, 2, 3, 4)}
    return {"sample": sample, "variants": variants, "tier_counts": counts,
            "total_variants": len(variants)}


# --- structural validity ---------------------------------------------------

def test_bundle_passes_structural_validator():
    assert gr.validate_fhir_bundle(gr.build_fhir(_summary())) == []


def test_empty_bundle_still_valid():
    # No variants -> Patient + Specimen + DiagnosticReport, no Observations.
    assert gr.validate_fhir_bundle(gr.build_fhir(_summary(variants=[]))) == []


def test_all_internal_references_resolve():
    bundle = gr.build_fhir(_summary(variants=[_variant(), _variant(pos=200)]))
    urls = {e["fullUrl"] for e in bundle["entry"]}
    def walk(o):
        if isinstance(o, dict):
            for k, val in o.items():
                if k == "reference":
                    yield val
                else:
                    yield from walk(val)
        elif isinstance(o, list):
            for x in o:
                yield from walk(x)
    for ref in walk(bundle):
        if ref.startswith("urn:uuid:"):
            assert ref in urls


def test_fullurls_are_stable_and_deterministic():
    a = gr.build_fhir(_summary())
    b = gr.build_fhir(_summary())
    assert [e["fullUrl"] for e in a["entry"]] == [e["fullUrl"] for e in b["entry"]]
    # Different sample -> different Patient urn.
    c = gr.build_fhir(_summary(sample="other"))
    assert a["entry"][0]["fullUrl"] != c["entry"][0]["fullUrl"]


# --- profiles + coding -----------------------------------------------------

def test_report_and_variant_profiles_present():
    bundle = gr.build_fhir(_summary())
    report = next(e["resource"] for e in bundle["entry"]
                  if e["resource"]["resourceType"] == "DiagnosticReport")
    obs = next(e["resource"] for e in bundle["entry"]
               if e["resource"]["resourceType"] == "Observation")
    assert any("genomic-report" in p for p in report["meta"]["profile"])
    assert any(p.endswith("/variant") for p in obs["meta"]["profile"])
    # Variant observation is coded 69548-6 with a Present value.
    assert obs["code"]["coding"][0]["code"] == "69548-6"
    assert obs["valueCodeableConcept"]["coding"][0]["code"] == "LA9633-4"


def _components(obs):
    return {c["code"]["coding"][0]["code"]: c for c in obs["component"]}


def test_variant_components_have_expected_loinc_codes():
    bundle = gr.build_fhir(_summary())
    obs = next(e["resource"] for e in bundle["entry"]
               if e["resource"]["resourceType"] == "Observation")
    comps = _components(obs)
    for code in ("48018-6", "62374-4", "48013-7", "69547-8", "69551-0",
                 "48004-6", "48005-3", "53034-5", "48002-0", "48006-1", "53037-8"):
        assert code in comps, f"missing component {code}"
    # every component carries a value[x]
    for c in obs["component"]:
        assert any(k.startswith("value") for k in c)


def test_allelic_state_maps_zygosity():
    het = _components(_first_obs(gr.build_fhir(_summary([_variant(genotype="het")]))))
    hom = _components(_first_obs(gr.build_fhir(_summary([_variant(genotype="hom_alt")]))))
    assert het["53034-5"]["valueCodeableConcept"]["coding"][0]["code"] == "LA6706-1"
    assert hom["53034-5"]["valueCodeableConcept"]["coding"][0]["code"] == "LA6705-3"


def test_clinical_significance_maps_to_loinc():
    obs = _first_obs(gr.build_fhir(_summary([_variant(clinvar_sig="Likely pathogenic")])))
    cc = _components(obs)["53037-8"]["valueCodeableConcept"]
    assert cc["coding"][0]["code"] == "LA26332-9"


def test_assembly_and_source_class_are_configurable():
    b37 = gr.build_fhir(_summary(), assembly="GRCh37", source_class="somatic")
    obs = _first_obs(b37)
    comps = _components(obs)
    assert comps["62374-4"]["valueCodeableConcept"]["coding"][0]["code"] == "LA14029-5"
    assert comps["48002-0"]["valueCodeableConcept"]["coding"][0]["code"] == "LA6684-0"


def test_molecular_consequence_uses_sequence_ontology():
    obs = _first_obs(gr.build_fhir(_summary([_variant(effect="missense_variant")])))
    cc = _components(obs)["48006-1"]["valueCodeableConcept"]
    assert cc["coding"][0]["code"] == "SO:0001583"


def test_patient_is_deidentified():
    bundle = gr.build_fhir(_summary())
    patient = next(e["resource"] for e in bundle["entry"]
                   if e["resource"]["resourceType"] == "Patient")
    assert "name" not in patient and "birthDate" not in patient
    assert patient["identifier"][0]["value"] == "sampleX"


def _first_obs(bundle):
    return next(e["resource"] for e in bundle["entry"]
                if e["resource"]["resourceType"] == "Observation")


# --- validator catches breakage --------------------------------------------

def test_validator_flags_dangling_reference():
    bundle = gr.build_fhir(_summary())
    # Point the report subject at a non-existent resource.
    report = next(e["resource"] for e in bundle["entry"]
                  if e["resource"]["resourceType"] == "DiagnosticReport")
    report["subject"] = {"reference": "urn:uuid:does-not-exist"}
    problems = gr.validate_fhir_bundle(bundle)
    assert any("dangling reference" in p for p in problems)


def test_validator_flags_valueless_component():
    bundle = gr.build_fhir(_summary())
    obs = _first_obs(bundle)
    obs["component"].append({"code": {"coding": [{"code": "X"}]}})  # no value[x]
    assert any("has no value[x]" in p for p in gr.validate_fhir_bundle(bundle))


def test_validator_flags_missing_patient():
    bundle = gr.build_fhir(_summary())
    bundle["entry"] = [e for e in bundle["entry"]
                       if e["resource"]["resourceType"] != "Patient"]
    assert any("no Patient" in p for p in gr.validate_fhir_bundle(bundle))


# --- standalone CLI --------------------------------------------------------

def test_validate_fhir_cli_ok_and_bad(tmp_path, capsys):
    good = tmp_path / "s.fhir.json"
    good.write_text(json.dumps(gr.build_fhir(_summary())), encoding="utf-8")
    assert vf.main(["validate_fhir.py", str(good)]) == 0

    bad_bundle = gr.build_fhir(_summary())
    _first_obs(bad_bundle).pop("code")
    bad = tmp_path / "bad.fhir.json"
    bad.write_text(json.dumps(bad_bundle), encoding="utf-8")
    assert vf.main(["validate_fhir.py", str(bad)]) == 1

    assert vf.main(["validate_fhir.py", str(tmp_path / "missing.json")]) == 1
    assert vf.main(["validate_fhir.py"]) == 2
