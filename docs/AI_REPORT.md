# AI report narrative (H6)

The report's narrative can be produced two ways:

1. **Deterministic template** (default, always available) — a factual summary
   built from the tier/ACMG counts and top genes. No model, no network, no
   dependencies. This is what CI and the offline profiles use.
2. **LLM narrative** (opt-in, `--report_llm`) — a real model call via
   `bin/llm_narrative.py` using the official **Anthropic SDK** (`claude-opus-4-8`),
   with strict guardrails. If anything about it isn't available or valid, the
   report **falls back to the template** — it never fabricates.

## Enabling it

```bash
pip install anthropic                 # in the report step's environment
export ANTHROPIC_API_KEY=sk-ant-...   # or ANTHROPIC_AUTH_TOKEN
nextflow run main.nf -profile docker --input samplesheet.csv --report_llm ...
```

- **Model:** `claude-opus-4-8` (default). Point at a **self-hosted / gateway**
  Anthropic-compatible endpoint with `ANTHROPIC_BASE_URL` — no code change.
- **No key or SDK?** The step logs and uses the templated narrative. Because of
  that graceful fallback, the default `python:3.11-slim` report container works
  unchanged; only add `anthropic` where you actually want the LLM path.

## Guardrails (why the output is trustworthy)

- **Structured output** — the model is constrained to a JSON schema
  (`output_config.format`), so the response is always parseable, with a
  `narrative` and a `genes_discussed` list.
- **Grounding check** — every gene the model claims to discuss must appear in the
  input variants; if it names a gene that isn't there, the narrative is
  **rejected** and the template is used. This is the anti-hallucination gate.
- **Scoped prompt** — the model is told to summarise *only* the supplied
  variants, give no diagnostic/treatment directions, and keep the research-use
  framing.
- **Graceful fallback** — missing SDK/key, network/API error, invalid JSON, or a
  failed grounding check all resolve to the deterministic template. Enrichment
  can never break the report or invent content.

The logic is unit-tested offline (`tests/test_llm_narrative.py`) by injecting a
fake client, so the guardrails and fallbacks are verified without an SDK, key, or
network.

## ⚠️ Privacy / research-use

Enabling `--report_llm` sends a **de-identified variant digest** — gene symbols,
predicted impact/effect, ACMG-style class, ClinVar/gnomAD annotations; **no
patient identifiers** — to the configured LLM endpoint. It is **off by default**.

- Do not enable it on identifiable patient data unless your endpoint and data
  agreements permit it. For strict data control, point `ANTHROPIC_BASE_URL` at an
  in-house/served gateway so nothing leaves your infrastructure.
- Outputs remain **research-use only** and are not a clinical determination — the
  same disclaimer as the rest of the pipeline applies to the LLM narrative.
