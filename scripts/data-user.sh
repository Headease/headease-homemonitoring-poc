#!/bin/bash
# Runs scripts/data-user.py inside the Docker image where liboprf is available.
#
# Usage:
#   ./scripts/data-user.sh [BSN]
#
# Default BSN is 004895708.

set -euo pipefail

cd "$(dirname "$0")/.."

BSN=${1:-004895708}

docker compose run --rm --no-deps \
  -v "$(pwd)/scripts:/app/scripts" \
  fhir python scripts/data-user.py "$BSN"
