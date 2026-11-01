#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "${PYSTACHY_SPAN_PYTHON:-python3.13}" "$script_dir/reproduce.py" "$@"
