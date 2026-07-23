#!/usr/bin/env python3
"""Offline structural conformance check for a generated FHIR bundle (H7).

Loads one or more `*.fhir.json` bundles and runs the dependency-free structural
gate from generate_report.validate_fhir_bundle: mandatory elements present,
component values present, and every internal (urn:uuid) reference resolves
inside the bundle. This is the fast CI-friendly check.

It is NOT a substitute for full HL7 Genomics Reporting IG profile validation,
which needs the official FHIR validator (Java + the IG package + network). Run
that on a FHIR host for authoritative conformance; see docs/FHIR.md.

Usage:
    validate_fhir.py BUNDLE.fhir.json [MORE.fhir.json ...]
Exit status is non-zero if any bundle has a structural problem.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Import the validator from the sibling report generator (stdlib-only module).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_report  # noqa: E402


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    if not paths:
        print("usage: validate_fhir.py BUNDLE.fhir.json [...]", file=sys.stderr)
        return 2

    total_problems = 0
    for path in paths:
        if not path.is_file():
            print(f"FAIL  {path}: not found")
            total_problems += 1
            continue
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAIL  {path}: invalid JSON ({exc})")
            total_problems += 1
            continue
        problems = generate_report.validate_fhir_bundle(bundle)
        if problems:
            for p in problems:
                print(f"FAIL  {path.name}: {p}")
            total_problems += len(problems)
        else:
            n = sum(1 for e in bundle.get("entry", [])
                    if e.get("resource", {}).get("resourceType") == "Observation")
            print(f"OK    {path.name}: structurally valid ({n} variant observation(s)).")

    if total_problems:
        print(f"\n{total_problems} structural problem(s) across {len(paths)} bundle(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
