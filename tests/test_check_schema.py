"""
Unit tests for bin/check_schema.py (M10). Fully offline.

Includes an integration assertion that the *real* nextflow.config and
nextflow_schema.json are in sync, so drift fails the suite (and CI).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BIN = _ROOT / "bin" / "check_schema.py"
_spec = importlib.util.spec_from_file_location("check_schema", _BIN)
cs = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(cs)


_CONFIG = """
manifest { name = 'x' }
params {
    input  = null            // required
    outdir = 'results'
    somatic = false          // a toggle
    // a fully commented line = should_not_count
    max_memory = '6.GB'
}
profiles { standard { process.executor = 'local' } }
"""

_SCHEMA = {
    "$defs": {
        "io": {"properties": {"input": {"type": "string"}, "outdir": {"type": "string"}}},
        "more": {"properties": {"somatic": {"type": "boolean"}, "max_memory": {"type": "string"}}},
    }
}


# --- parsing ---------------------------------------------------------------

def test_config_params_extracts_names_and_skips_comments():
    names = cs.config_params(_CONFIG)
    assert names == {"input", "outdir", "somatic", "max_memory"}
    assert "should_not_count" not in names
    assert "name" not in names          # from manifest block, not params


def test_schema_params_collects_nested_properties():
    assert cs.schema_params(_SCHEMA) == {"input", "outdir", "somatic", "max_memory"}


# --- diff ------------------------------------------------------------------

def test_in_sync_reports_no_drift():
    assert cs.diff(_CONFIG, _SCHEMA) == (set(), set())


def test_param_missing_from_schema_is_flagged():
    schema = json.loads(json.dumps(_SCHEMA))
    del schema["$defs"]["more"]["properties"]["somatic"]
    missing_in_schema, missing_in_config = cs.diff(_CONFIG, schema)
    assert missing_in_schema == {"somatic"}
    assert missing_in_config == set()


def test_schema_property_without_param_is_flagged():
    schema = json.loads(json.dumps(_SCHEMA))
    schema["$defs"]["more"]["properties"]["ghost"] = {"type": "string"}
    missing_in_schema, missing_in_config = cs.diff(_CONFIG, schema)
    assert missing_in_schema == set()
    assert missing_in_config == {"ghost"}


# --- CLI + real files ------------------------------------------------------

def test_cli_ok_and_drift(tmp_path):
    cfg = tmp_path / "nextflow.config"
    sch = tmp_path / "nextflow_schema.json"
    cfg.write_text(_CONFIG, encoding="utf-8")
    sch.write_text(json.dumps(_SCHEMA), encoding="utf-8")
    assert cs.main(["check_schema.py", str(cfg), str(sch)]) == 0

    # introduce drift
    bad = json.loads(json.dumps(_SCHEMA))
    del bad["$defs"]["io"]["properties"]["outdir"]
    sch.write_text(json.dumps(bad), encoding="utf-8")
    assert cs.main(["check_schema.py", str(cfg), str(sch)]) == 1

    assert cs.main(["check_schema.py", str(tmp_path / "nope.config"), str(sch)]) == 2


def test_real_config_and_schema_are_in_sync():
    config_text = (_ROOT / "nextflow.config").read_text(encoding="utf-8")
    schema = json.loads((_ROOT / "nextflow_schema.json").read_text(encoding="utf-8"))
    missing_in_schema, missing_in_config = cs.diff(config_text, schema)
    assert missing_in_schema == set(), f"undocumented params: {missing_in_schema}"
    assert missing_in_config == set(), f"schema props with no param: {missing_in_config}"
