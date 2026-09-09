#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python "$ROOT/scripts/release.py" validate

python -B scripts/v23_acceptance.py
