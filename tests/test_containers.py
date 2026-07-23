"""
Unit tests for bin/check_containers.py and the container invariant it enforces.

Runs fully offline with no container engine or network. Guards H1: every
process module must pin both a conda env and a container image, so the
docker/singularity profiles stay reproducible. This is the regression test
that would have caught the un-containerized bwa-mem2|samtools step.

Run:  pytest -q   (from the repo root)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Load the script from bin/ as a module (it has no package/__init__).
_ROOT = Path(__file__).resolve().parents[1]
_BIN = _ROOT / "bin" / "check_containers.py"
_spec = importlib.util.spec_from_file_location("check_containers", _BIN)
cc = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(cc)

_MODULES = _ROOT / "modules" / "local"

_MODULE = """\
process FOO {{
    conda '{conda}'
    container '{container}'
    script:
    \"\"\"echo hi\"\"\"
}}
"""


def _mod(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "modules"
    d.mkdir()
    (d / "foo.nf").write_text(body)
    return d


# --- The real repo satisfies the invariant -------------------------------

def test_repo_modules_all_containerized():
    """Every real process module declares conda + container (no hard failures)."""
    rc = cc.main(["check_containers.py", str(_MODULES)])
    assert rc == 0


def test_every_real_module_has_a_container_directive():
    """Belt-and-suspenders: scan the files directly, independent of main()."""
    offenders = []
    for nf in sorted(_MODULES.glob("*.nf")):
        failures, _ = cc.check_module(nf)
        if failures:
            offenders.append((nf.name, failures))
    assert not offenders, f"process modules missing directives: {offenders}"


# --- The checker actually fails when it should ---------------------------

def test_missing_container_is_a_hard_failure(tmp_path):
    body = "process FOO {\n    conda 'bioconda::fastqc=0.12.1'\n    script:\n    \"\"\"x\"\"\"\n}\n"
    d = _mod(tmp_path, body)
    assert cc.main(["check_containers.py", str(d)]) == 1


def test_missing_conda_is_a_hard_failure(tmp_path):
    body = "process FOO {\n    container 'biocontainers/fastqc:0.12.1--hdfd78af_0'\n    script:\n    \"\"\"x\"\"\"\n}\n"
    d = _mod(tmp_path, body)
    assert cc.main(["check_containers.py", str(d)]) == 1


def test_commented_out_container_does_not_count(tmp_path):
    body = (
        "process FOO {\n"
        "    conda 'bioconda::fastqc=0.12.1'\n"
        "    // container 'biocontainers/fastqc:0.12.1--hdfd78af_0'\n"
        "    script:\n    \"\"\"x\"\"\"\n}\n"
    )
    d = _mod(tmp_path, body)
    assert cc.main(["check_containers.py", str(d)]) == 1


# --- Version cross-check (warning only, never fatal) ---------------------

def test_version_mismatch_warns_but_passes(tmp_path):
    body = _MODULE.format(
        conda="bioconda::fastqc=0.12.1",
        container="biocontainers/fastqc:0.11.9--hdfd78af_0",
    )
    d = _mod(tmp_path, body)
    # Mismatch is a warning, not a failure: the run still succeeds.
    assert cc.main(["check_containers.py", str(d)]) == 0
    failures, warnings = cc.check_module(d / "foo.nf")
    assert not failures
    assert warnings


def test_mulled_hash_tag_is_not_version_checked(tmp_path):
    body = _MODULE.format(
        conda="bioconda::bwa-mem2=2.2.1 bioconda::samtools=1.19.2",
        container=(
            "biocontainers/mulled-v2-"
            "e5d375990341c5aef3c9aff74f96f66f65375ef6:"
            "2cdf6bf1e92acbeb9b2834b1c58b6a682df32abb-0"
        ),
    )
    d = _mod(tmp_path, body)
    failures, warnings = cc.check_module(d / "foo.nf")
    assert not failures
    assert not warnings  # content-hash tag is skipped, not flagged
