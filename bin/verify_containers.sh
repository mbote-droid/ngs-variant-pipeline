#!/usr/bin/env bash
#
# verify_containers.sh - pull-verify every container image the pipeline pins.
#
# This is the half of H1 verification that needs a container engine + network,
# so it is NOT part of CI's offline checks. Run it once on a Docker- (or
# Singularity-) capable host to confirm every pinned tag actually resolves and
# pulls from the registry. bin/check_containers.py handles the offline half
# (presence + well-formedness) and runs in CI.
#
# Usage:
#   bin/verify_containers.sh                 # docker pull (default)
#   ENGINE=singularity bin/verify_containers.sh
#   MODULES_DIR=modules/local bin/verify_containers.sh
#
# Exit status is non-zero if any image fails to pull.
set -uo pipefail

MODULES_DIR="${MODULES_DIR:-modules/local}"
ENGINE="${ENGINE:-docker}"

if [[ ! -d "$MODULES_DIR" ]]; then
    echo "ERROR: modules dir not found: $MODULES_DIR" >&2
    exit 2
fi

# Extract the quoted value of each real (non-commented) `container` directive.
# Strips inline // comments first so commented-out directives are ignored.
mapfile -t IMAGES < <(
    for f in "$MODULES_DIR"/*.nf; do
        sed 's,//.*,,' "$f" \
            | grep -oE "^[[:space:]]*container[[:space:]]+['\"][^'\"]+['\"]" \
            | sed -E "s/^[[:space:]]*container[[:space:]]+['\"]//; s/['\"][[:space:]]*$//"
    done | sort -u
)

if [[ "${#IMAGES[@]}" -eq 0 ]]; then
    echo "ERROR: no container images found under $MODULES_DIR" >&2
    exit 2
fi

echo "Verifying ${#IMAGES[@]} unique image(s) with engine: $ENGINE"
echo

fail=0
for img in "${IMAGES[@]}"; do
    case "$ENGINE" in
        docker)
            if docker pull "$img" >/dev/null 2>&1; then
                echo "  OK    $img"
            else
                echo "  FAIL  $img"
                fail=1
            fi
            ;;
        singularity|apptainer)
            # Nextflow pulls biocontainers docker images via docker:// under
            # Singularity; mirror that here.
            if "$ENGINE" pull --force "/tmp/$(echo "$img" | tr '/:' '__').sif" \
                    "docker://$img" >/dev/null 2>&1; then
                echo "  OK    $img"
            else
                echo "  FAIL  $img"
                fail=1
            fi
            ;;
        *)
            echo "ERROR: unknown ENGINE '$ENGINE' (use docker or singularity)" >&2
            exit 2
            ;;
    esac
done

echo
if [[ "$fail" -ne 0 ]]; then
    echo "One or more images failed to pull. See FAIL lines above."
    exit 1
fi
echo "All ${#IMAGES[@]} images pulled successfully."
