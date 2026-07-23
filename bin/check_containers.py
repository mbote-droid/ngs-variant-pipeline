#!/usr/bin/env python3
"""Offline container-declaration checker for the pipeline's process modules.

H1 (hardening) requires that *every* process is pinned to a container so the
docker/singularity profiles are fully reproducible. This checker enforces that
invariant without needing a container engine or network access, so it can run
in the existing pytest CI job:

  * HARD FAILURE  - a process module is missing a `conda` or `container`
                    directive, or its container string is empty/malformed.
  * WARNING       - the version encoded in the container tag does not line up
                    with the conda pin (best-effort; skipped for mulled/multi-
                    tool images whose tag is a content hash, not a version).

Registry *pullability* (does the tag actually exist?) is intentionally NOT
checked here - that needs a Docker host and lives in bin/verify_containers.sh.

Usage:
    check_containers.py [MODULES_DIR]      # defaults to modules/local
Exit status is non-zero if any hard failure is found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# A directive line like:  conda 'bioconda::fastqc=0.12.1'
#                         container 'biocontainers/fastqc:0.12.1--hdfd78af_0'
# We match single- or double-quoted values and ignore commented-out lines.
_CONDA_RE = re.compile(r"""^\s*conda\s+(['"])(?P<val>.+?)\1""", re.MULTILINE)
_CONTAINER_RE = re.compile(r"""^\s*container\s+(['"])(?P<val>.+?)\1""", re.MULTILINE)
_PROCESS_RE = re.compile(r"^\s*process\s+\w+\s*\{", re.MULTILINE)

# From "biocontainers/fastqc:0.12.1--hdfd78af_0" -> tool "fastqc", tag "0.12.1--..."
# From "python:3.11-slim"                        -> tool "python", tag "3.11-slim"
_IMAGE_RE = re.compile(r"^(?:[^/]+/)*(?P<tool>[^/:]+):(?P<tag>[^/]+)$")


def _strip_comments(text: str) -> str:
    """Drop // line comments so commented-out directives don't count as real."""
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def _tag_version(tag: str) -> str | None:
    """The leading version token of an image tag, or None if it looks like a hash.

    "0.12.1--hdfd78af_0" -> "0.12.1"; "1.21--pyhdfd78af_0" -> "1.21";
    "3.11-slim" -> "3.11"; a mulled content hash -> None.
    """
    head = tag.split("--", 1)[0].split("-", 1)[0]
    return head if re.match(r"^\d", head) else None


def check_module(path: Path) -> tuple[list[str], list[str]]:
    """Return (failures, warnings) for a single process module file."""
    raw = path.read_text()
    text = _strip_comments(raw)
    name = path.name
    failures: list[str] = []
    warnings: list[str] = []

    if not _PROCESS_RE.search(text):
        # Not a process module (e.g. a helper include); nothing to enforce.
        return failures, warnings

    conda_m = _CONDA_RE.search(text)
    container_m = _CONTAINER_RE.search(text)

    if conda_m is None:
        failures.append(f"{name}: no `conda` directive")
    if container_m is None:
        failures.append(f"{name}: no `container` directive")
        return failures, warnings

    image = container_m.group("val").strip()
    if not image:
        failures.append(f"{name}: empty container string")
        return failures, warnings

    img_m = _IMAGE_RE.match(image)
    if img_m is None:
        failures.append(f"{name}: malformed container image '{image}'")
        return failures, warnings

    # Best-effort version cross-check (warning only). Skip mulled/hash tags.
    if conda_m is not None and "mulled-" not in image:
        ver = _tag_version(img_m.group("tag"))
        conda_val = conda_m.group("val")
        if ver is not None and ver not in conda_val:
            warnings.append(
                f"{name}: container tag version '{ver}' "
                f"not found in conda pin '{conda_val}'"
            )

    return failures, warnings


def main(argv: list[str]) -> int:
    modules_dir = Path(argv[1]) if len(argv) > 1 else Path("modules/local")
    if not modules_dir.is_dir():
        print(f"ERROR: modules dir not found: {modules_dir}", file=sys.stderr)
        return 2

    files = sorted(modules_dir.glob("*.nf"))
    if not files:
        print(f"ERROR: no .nf modules under {modules_dir}", file=sys.stderr)
        return 2

    all_failures: list[str] = []
    all_warnings: list[str] = []
    checked = 0
    for path in files:
        failures, warnings = check_module(path)
        # Count only real process modules (those that produced a verdict).
        if _PROCESS_RE.search(_strip_comments(path.read_text())):
            checked += 1
        all_failures.extend(failures)
        all_warnings.extend(warnings)

    for w in all_warnings:
        print(f"WARN  {w}")
    for f in all_failures:
        print(f"FAIL  {f}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s) across {checked} process module(s).")
        return 1

    print(f"OK: all {checked} process modules declare conda + container.")
    if all_warnings:
        print(f"({len(all_warnings)} non-fatal version warning(s) above.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
