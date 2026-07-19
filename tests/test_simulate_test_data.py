"""
Unit tests for the codon-aware logic in bin/simulate_test_data.py.

These guard the test-data generator so the committed dataset stays meaningful
(a real stop-gain / missense / synonymous spread that SnpEff will reproduce).
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin" / "simulate_test_data.py"
_spec = importlib.util.spec_from_file_location("simulate_test_data", _BIN)
sim = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(sim)


def test_classify_stop_gained():
    assert sim._classify("TAT", "TAA") == "stop_gained"   # Y -> *


def test_classify_missense():
    assert sim._classify("TAT", "TGT") == "missense_variant"  # Y -> C


def test_classify_synonymous():
    assert sim._classify("TTT", "TTC") == "synonymous_variant"  # F -> F


def test_classify_unknown_codon():
    assert sim._classify("TNT", "TAA") == "unknown"


def test_resolve_variants_matches_specs():
    rng = random.Random(53)
    ref = sim.gen_reference(12000, rng)
    resolved = sim.resolve_variants(ref)
    assert len(resolved) == len(sim.VARIANT_SPECS)
    effects = [v[5] for v in resolved]
    assert effects == ["stop_gained", "missense_variant", "synonymous_variant"]
    # Each resolved variant's REF base must match the reference at that position.
    for pos, ref_base, alt, _af, _z, _e in resolved:
        assert ref[pos - 1] == ref_base
        assert alt != ref_base


def test_resolve_variants_effect_is_reproducible_in_frame():
    rng = random.Random(53)
    ref = sim.gen_reference(12000, rng)
    for pos, ref_base, alt, _af, _z, effect in sim.resolve_variants(ref):
        codon_idx = (pos - sim.CDS_START) // 3
        codon_start = sim.CDS_START + codon_idx * 3
        codon = ref[codon_start - 1:codon_start + 2]
        mutated = list(codon)
        mutated[pos - codon_start] = alt
        assert sim._classify(codon, "".join(mutated)) == effect
