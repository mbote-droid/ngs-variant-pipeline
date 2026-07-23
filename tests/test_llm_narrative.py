"""
Unit tests for bin/llm_narrative.py (H6). Fully offline: a fake client is
injected, so no `anthropic` SDK, API key, or network is needed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "llm_narrative.py"
_spec = importlib.util.spec_from_file_location("llm_narrative", _BIN)
ln = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(ln)


# --- fake Anthropic client -------------------------------------------------

class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, text=None, exc=None):
        self._text, self._exc = text, exc
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        return _Response(self._text)


class _Client:
    def __init__(self, text=None, exc=None):
        self.messages = _Messages(text, exc)


def _summary():
    return {
        "total_variants": 2,
        "tier_counts": {"1": 1, "2": 1},
        "variants": [
            {"gene": "BRCA1", "impact": "HIGH", "effect": "stop_gained", "tier": 1,
             "acmg_classification": "Likely pathogenic", "clinvar_sig": "", "gnomad_af": 1e-5},
            {"gene": "TP53", "impact": "MODERATE", "effect": "missense_variant", "tier": 2},
        ],
    }


def _ok(text, genes):
    return json.dumps({"narrative": text, "genes_discussed": genes})


# --- helpers ---------------------------------------------------------------

def test_input_genes():
    assert ln.input_genes(_summary()) == {"BRCA1", "TP53"}


def test_build_messages_embeds_variants():
    msg = ln.build_messages(_summary())[0]["content"]
    assert "BRCA1" in msg and "TP53" in msg and "stop_gained" in msg


# --- happy path ------------------------------------------------------------

def test_generate_narrative_success():
    client = _Client(_ok("BRCA1 and TP53 carry notable variants.", ["BRCA1", "TP53"]))
    out = ln.generate_narrative(_summary(), client=client)
    assert out == "BRCA1 and TP53 carry notable variants."
    # request used the pinned model + structured-output guardrail
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["output_config"]["format"]["type"] == "json_schema"


def test_genes_case_insensitive_grounding():
    client = _Client(_ok("brca1 variant noted.", ["brca1"]))   # lowercase claim
    assert ln.generate_narrative(_summary(), client=client) == "brca1 variant noted."


# --- guardrails: reject and fall back --------------------------------------

def test_hallucinated_gene_rejected():
    client = _Client(_ok("EGFR is affected.", ["EGFR"]))       # EGFR not in input
    assert ln.generate_narrative(_summary(), client=client) is None


def test_invalid_json_rejected():
    assert ln.generate_narrative(_summary(), client=_Client("not json")) is None


def test_missing_narrative_field_rejected():
    client = _Client(json.dumps({"genes_discussed": ["BRCA1"]}))
    assert ln.generate_narrative(_summary(), client=client) is None


def test_sdk_error_falls_back():
    client = _Client(exc=RuntimeError("network down"))
    assert ln.generate_narrative(_summary(), client=client) is None


def test_empty_variants_no_call():
    client = _Client(_ok("x", []))
    assert ln.generate_narrative({"variants": []}, client=client) is None
    assert client.messages.calls == []    # never called the model


# --- client construction ---------------------------------------------------

def test_get_client_returns_injected():
    c = _Client()
    assert ln._get_client(c) is c


def test_get_client_none_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert ln._get_client(None) is None


# --- integration with generate_report --------------------------------------

def test_report_falls_back_when_llm_unavailable():
    gr_path = Path(__file__).resolve().parents[1] / "bin" / "generate_report.py"
    spec = importlib.util.spec_from_file_location("generate_report", gr_path)
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    s = _summary()
    # No credentials/SDK in the test env -> _llm_narrative returns None ->
    # maybe_llm_narrative degrades to the deterministic template (never raises).
    out = gr.maybe_llm_narrative(s, enable_llm=True)
    assert out == gr.build_narrative(s)
