"""
Unit tests for the H3 evidence + ACMG-style logic in bin/prioritize_variants.py.

Fully offline; no pipeline, tools, or network. Covers ClinVar/gnomAD/dbSNP
evidence extraction, VEP CSQ parsing, the ACMG criteria that fire, the
ACMG/AMP-2015 combining rules, and evidence-aware tiering.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "prioritize_variants.py"
_spec = importlib.util.spec_from_file_location("prioritize_variants", _BIN)
pv = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(pv)


# --- INFO / evidence parsing ----------------------------------------------

def test_info_dict_flags_and_values():
    d = pv.info_dict("AC=1;DB;CLNSIG=Pathogenic;AF=0.5")
    assert d["AC"] == "1"
    assert d["DB"] == ""
    assert d["CLNSIG"] == "Pathogenic"


def test_parse_af_multiallelic_takes_max():
    assert pv._parse_af("0.01,0.2,.") == 0.2
    assert pv._parse_af(".") is None
    assert pv._parse_af(None) is None


def test_extract_evidence():
    info = pv.info_dict("CLNSIG=Likely_pathogenic;gnomAD_AF=0.0003")
    ev = pv.extract_evidence(info, "rs123")
    assert ev["clinvar_sig"] == "Likely pathogenic"
    assert abs(ev["gnomad_af"] - 0.0003) < 1e-12
    assert ev["rsid"] == "rs123"
    # A non-rs id is not treated as an rsID.
    assert pv.extract_evidence({}, "chr1:1")["rsid"] == ""


# --- VEP CSQ ---------------------------------------------------------------

CSQ_HEADER = (
    '##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence annotations '
    'from Ensembl VEP. Format: Allele|Consequence|IMPACT|SYMBOL|Gene|'
    'Feature_type|Feature|BIOTYPE|EXON|INTRON|HGVSc|HGVSp">'
)


def test_csq_format_and_parse():
    fmt = pv.csq_format([CSQ_HEADER])
    assert fmt[:4] == ["Allele", "Consequence", "IMPACT", "SYMBOL"]
    info = ("CSQ=A|missense_variant|MODERATE|BRCA1|ENSG|Transcript|ENST|"
            "protein_coding|2/23||c.100A>T|ENSP:p.Lys34Asn")
    ann = pv.parse_csq(info, fmt)
    assert ann["impact"] == "MODERATE"
    assert ann["gene_name"] == "BRCA1"
    assert ann["effect"] == "missense_variant"
    assert ann["hgvs_p"] == "ENSP:p.Lys34Asn"


def test_parse_vcf_reads_vep_csq(tmp_path):
    text = (
        "##fileformat=VCFv4.2\n" + CSQ_HEADER + "\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\n"
        "chr1\t100\trs9\tA\tT\t50\tPASS\t"
        "CSQ=T|stop_gained|HIGH|BRCA1|ENSG|Transcript|ENST|protein_coding|"
        "2/23||c.100A>T|ENSP:p.Lys34Ter\tGT\t0/1\n"
    )
    p = tmp_path / "vep.vcf"
    p.write_text(text)
    variants = pv.parse_vcf(p)
    assert variants[0]["impact"] == "HIGH"
    assert variants[0]["gene"] == "BRCA1"
    assert variants[0]["rsid"] == "rs9"


# --- ACMG criteria ---------------------------------------------------------

def test_pvs1_for_lof_high():
    crits = pv.acmg_criteria({"impact": "HIGH", "effect": "stop_gained"})
    assert any(c["code"] == "PVS1" for c in crits)


def test_pm2_ba1_bs1_by_af():
    assert any(c["code"] == "PM2" for c in pv.acmg_criteria({"gnomad_af": 1e-5}))
    assert any(c["code"] == "BS1" for c in pv.acmg_criteria({"gnomad_af": 0.02}))
    assert any(c["code"] == "BA1" for c in pv.acmg_criteria({"gnomad_af": 0.10}))
    # No gnomAD track -> PM2 not asserted.
    assert not any(c["code"] == "PM2" for c in pv.acmg_criteria({"impact": "HIGH"}))


def test_clinvar_criteria():
    assert any(c["code"] == "PP5" for c in
               pv.acmg_criteria({"clinvar_sig": "pathogenic"}))
    assert any(c["code"] == "BP6" for c in
               pv.acmg_criteria({"clinvar_sig": "benign"}))


# --- ACMG combining --------------------------------------------------------

def _crits(*codes):
    return [{"code": c, "reason": ""} for c in codes]


def test_classify_pathogenic_and_likely():
    assert pv.classify_acmg(_crits("PVS1", "PM2")) == "Likely pathogenic"
    assert pv.classify_acmg(_crits("PVS1", "PM2", "PP3")) == "Pathogenic"
    assert pv.classify_acmg(_crits("PM2", "PM2", "PM2")) == "Likely pathogenic"


def test_classify_benign():
    assert pv.classify_acmg(_crits("BA1")) == "Benign"
    assert pv.classify_acmg(_crits("BS1", "BP6")) == "Likely benign"
    assert pv.classify_acmg(_crits("BP6")) == "Uncertain significance"


def test_classify_conflicting_is_vus():
    # Strong pathogenic + stand-alone benign -> conflicting -> VUS.
    assert pv.classify_acmg(_crits("PVS1", "PM2", "BA1")) == "Uncertain significance"


def test_classify_empty_is_vus():
    assert pv.classify_acmg([]) == "Uncertain significance"


# --- evidence-aware tiering ------------------------------------------------

def test_tier_clinvar_pathogenic_overrides_impact():
    # A MODIFIER variant that ClinVar calls pathogenic still tiers 1.
    assert pv.assign_tier({"impact": "MODIFIER", "passed": True,
                           "clinvar_sig": "Pathogenic"}) == 1


def test_tier_common_variant_downgraded():
    assert pv.assign_tier({"impact": "HIGH", "passed": True,
                           "gnomad_af": 0.2}) == 4


def test_tier_clinvar_benign_downgraded():
    assert pv.assign_tier({"impact": "HIGH", "passed": True,
                           "clinvar_sig": "Benign"}) == 4


def test_tier_conflicting_clinvar_not_forced_to_one():
    v = {"impact": "MODERATE", "passed": True,
         "clinvar_sig": "Conflicting interpretations of pathogenicity"}
    assert pv.assign_tier(v) == 2  # falls back to impact, not forced pathogenic


# --- end-to-end JSON -------------------------------------------------------

def test_prioritize_populates_acmg_and_counts(tmp_path):
    header = (
        "##fileformat=VCFv4.2\n"
        '##INFO=<ID=ANN,Number=.,Type=String,Description="SnpEff">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\n"
    )
    ann = "ANN=T|stop_gained|HIGH|BRCA1|g|transcript|t|protein_coding|1/1|c.1A>T|p.X|||||"
    row = f"chr1\t100\trs1\tA\tT\t50\tPASS\t{ann};gnomAD_AF=1e-05\tGT\t0/1\n"
    p = tmp_path / "in.vcf"
    p.write_text(header + row)
    variants = pv.prioritize(pv.parse_vcf(p))
    v = variants[0]
    assert v["acmg_classification"] == "Likely pathogenic"  # PVS1 + PM2
    assert {c["code"] for c in v["acmg_criteria"]} >= {"PVS1", "PM2"}

    out = tmp_path / "p.json"
    pv.write_json(variants, out, "s1")
    data = json.loads(out.read_text())
    assert data["acmg_counts"]["Likely pathogenic"] == 1
    assert "research" in data["disclaimer"].lower()


def test_tsv_has_evidence_columns(tmp_path):
    header = (
        "##fileformat=VCFv4.2\n"
        '##INFO=<ID=ANN,Number=.,Type=String,Description="SnpEff">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\n"
    )
    ann = "ANN=T|missense_variant|MODERATE|G|g|transcript|t|protein_coding|1/1|c.1A>T|p.X|||||"
    p = tmp_path / "in.vcf"
    p.write_text(header + f"chr1\t100\t.\tA\tT\t50\tPASS\t{ann}\tGT\t0/1\n")
    variants = pv.prioritize(pv.parse_vcf(p))
    out = tmp_path / "p.tsv"
    pv.write_tsv(variants, out)
    cols = out.read_text().splitlines()[0].split("\t")
    assert "acmg_classification" in cols
    assert "gnomad_af" in cols
    assert "clinvar_sig" in cols
