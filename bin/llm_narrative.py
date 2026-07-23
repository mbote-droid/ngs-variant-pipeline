#!/usr/bin/env python3
"""
Optional LLM narrative enrichment for the clinical report (H6).

Turns the report's "AI narrative" hook from a deterministic-template stub into a
real LLM call, with strict guardrails and graceful fallback:

  * Backend      - the official Anthropic SDK (`anthropic`), model claude-opus-4-8.
                   A self-hosted / gateway endpoint can be targeted with the
                   ANTHROPIC_BASE_URL env var without changing this code.
  * Guardrails   - structured JSON output (output_config.format) + a *grounding*
                   check: every gene the model claims to discuss must appear in
                   the input. If it invents one, the result is rejected.
  * Fallback     - if `anthropic` isn't installed, no API key is configured, the
                   call errors, or the output fails validation, this returns None
                   and the caller uses the deterministic templated narrative.
                   Nothing is ever fabricated.

The `anthropic` import is lazy, so this module imports fine in the stdlib-only
environments the rest of the pipeline runs in, and the whole thing is unit-tested
offline by injecting a fake client (no SDK, no network).

PRIVACY / RESEARCH-USE: enabling this sends a de-identified variant digest (genes,
impacts, effects, ACMG-style class, ClinVar/gnomAD annotations - no patient
identifiers) to the configured LLM endpoint. It is off by default and must not be
used with identifiable patient data unless your endpoint and agreements permit it.
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("llm_narrative")

DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 1024
MAX_VARIANTS = 25   # cap the digest sent to the model

SYSTEM_PROMPT = (
    "You are a careful assistant summarising a RESEARCH-USE-ONLY germline variant "
    "report for a clinician-scientist. Write a short, factual narrative (3-6 "
    "sentences) about ONLY the variants provided in the input. Rules: do not "
    "invent genes, variants, frequencies, or clinical claims; discuss only genes "
    "present in the input; do not give diagnostic or treatment directions; note "
    "that findings are research-use and not a clinical determination. In "
    "'genes_discussed', list exactly the gene symbols you mention."
)

# Structured-output schema — guarantees parseable JSON with the fields we check.
OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "narrative": {"type": "string"},
            "genes_discussed": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["narrative", "genes_discussed"],
        "additionalProperties": False,
    },
}


def input_genes(summary: dict) -> set[str]:
    """Gene symbols present in the input (upper-cased), for the grounding check."""
    return {str(v.get("gene", "")).upper()
            for v in summary.get("variants", []) if v.get("gene")}


def _digest(summary: dict) -> dict:
    """A compact, de-identified digest of the top variants for the prompt."""
    variants = []
    for v in summary.get("variants", [])[:MAX_VARIANTS]:
        variants.append({
            "gene": v.get("gene", ""),
            "impact": v.get("impact", ""),
            "effect": v.get("effect", ""),
            "tier": v.get("tier", ""),
            "acmg": v.get("acmg_classification", ""),
            "clinvar": v.get("clinvar_sig", ""),
            "gnomad_af": v.get("gnomad_af"),
        })
    return {
        "total_variants": summary.get("total_variants", len(summary.get("variants", []))),
        "tier_counts": summary.get("tier_counts", {}),
        "acmg_counts": summary.get("acmg_counts", {}),
        "variants": variants,
    }


def build_messages(summary: dict) -> list[dict]:
    return [{
        "role": "user",
        "content": ("Summarise these prioritised variants for the report. "
                    "Input JSON:\n" + json.dumps(_digest(summary), indent=2)),
    }]


def _get_client(client):
    """Return the injected client, or construct a real Anthropic one (or None)."""
    if client is not None:
        return client
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        log.info("no ANTHROPIC_API_KEY/AUTH_TOKEN set; skipping LLM narrative")
        return None
    try:
        import anthropic  # lazy: keeps this module import-safe without the SDK
    except ImportError:
        log.info("`anthropic` SDK not installed; skipping LLM narrative")
        return None
    return anthropic.Anthropic()   # honours ANTHROPIC_BASE_URL for a gateway


def _extract_json(response) -> dict | None:
    """Pull the JSON object out of the first text block of a Messages response."""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            try:
                return json.loads(block.text)
            except (ValueError, TypeError):
                return None
    return None


def generate_narrative(summary: dict, *, client=None,
                       model: str = DEFAULT_MODEL) -> str | None:
    """Return an LLM narrative grounded in `summary`, or None to fall back.

    `client` is injectable (a fake in tests); when omitted, a real Anthropic
    client is constructed if credentials + SDK are available.
    """
    if not summary.get("variants"):
        return None   # nothing to narrate; let the caller's template handle it
    api = _get_client(client)
    if api is None:
        return None
    try:
        response = api.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=build_messages(summary),
            output_config={"format": OUTPUT_SCHEMA, "effort": "low"},
        )
    except Exception as exc:                       # any SDK/network error -> fallback
        log.warning("LLM narrative call failed (%s); using templated narrative", exc)
        return None

    data = _extract_json(response)
    if not isinstance(data, dict) or not data.get("narrative"):
        log.warning("LLM returned no usable narrative; using templated narrative")
        return None

    # Grounding guardrail: reject any gene the model claims that isn't in the input.
    allowed = input_genes(summary)
    claimed = {str(g).upper() for g in data.get("genes_discussed", [])}
    hallucinated = claimed - allowed
    if hallucinated:
        log.warning("LLM mentioned genes not in the input %s; rejecting", sorted(hallucinated))
        return None

    return str(data["narrative"]).strip()
