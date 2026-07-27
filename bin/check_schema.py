#!/usr/bin/env python3
"""Offline check that nextflow_schema.json and nextflow.config stay in sync (M10).

nf-core pipelines ship a JSON Schema describing every `--param`; it powers
`-params-file` validation, tab-completion and docs. The schema silently rotting
out of step with `nextflow.config` is the classic failure mode, so this check
(dependency-free, no Nextflow needed) enforces the invariant in CI:

  * every `params.*` default in nextflow.config is documented in the schema, and
  * every property in the schema corresponds to a real param.

A small allow-list covers params intentionally absent from one side.

Usage:
    check_schema.py [CONFIG] [SCHEMA]
    (defaults: nextflow.config  nextflow_schema.json)
Exit status is non-zero on any drift.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Params that may appear in config but need no schema entry (or vice versa).
# Kept empty by default; add names here only with a documented reason.
_IGNORE: set[str] = set()


def config_params(config_text: str) -> set[str]:
    """Extract top-level `name = value` keys from the `params { ... }` block.

    Only the first brace-balanced params block is read; nested maps (none today)
    and // comments are ignored.
    """
    start = config_text.find("params {")
    if start == -1:
        raise ValueError("no `params {` block found in config")

    depth = 0
    body_start = None
    end = None
    for i in range(start, len(config_text)):
        ch = config_text[i]
        if ch == "{":
            depth += 1
            if depth == 1:
                body_start = i + 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError("unterminated `params {` block")

    body = config_text[body_start:end]
    names: set[str] = set()
    for line in body.splitlines():
        code = line.split("//", 1)[0]           # strip trailing comment
        m = re.match(r"\s*([A-Za-z_]\w*)\s*=", code)
        if m:
            names.add(m.group(1))
    return names


def schema_params(schema: dict) -> set[str]:
    """Collect every key under any `properties` object in the schema tree."""
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                found.update(props.keys())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return found


def diff(config_text: str, schema: dict) -> tuple[set[str], set[str]]:
    cfg = config_params(config_text) - _IGNORE
    sch = schema_params(schema) - _IGNORE
    missing_in_schema = cfg - sch      # declared but undocumented
    missing_in_config = sch - cfg      # documented but not a real param
    return missing_in_schema, missing_in_config


def main(argv: list[str]) -> int:
    config_path = Path(argv[1]) if len(argv) > 1 else Path("nextflow.config")
    schema_path = Path(argv[2]) if len(argv) > 2 else Path("nextflow_schema.json")

    if not config_path.is_file():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 2
    if not schema_path.is_file():
        print(f"ERROR: schema not found: {schema_path}", file=sys.stderr)
        return 2

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL  schema is not valid JSON: {exc}")
        return 1

    missing_in_schema, missing_in_config = diff(
        config_path.read_text(encoding="utf-8"), schema)

    for name in sorted(missing_in_schema):
        print(f"FAIL  param '{name}' is in {config_path.name} but not documented in the schema")
    for name in sorted(missing_in_config):
        print(f"FAIL  schema property '{name}' has no matching param in {config_path.name}")

    if missing_in_schema or missing_in_config:
        total = len(missing_in_schema) + len(missing_in_config)
        print(f"\n{total} schema/config drift(s).")
        return 1

    n = len(config_params(config_path.read_text(encoding="utf-8")) - _IGNORE)
    print(f"OK: schema and config agree on all {n} parameters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
