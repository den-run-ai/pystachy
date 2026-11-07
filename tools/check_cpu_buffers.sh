#!/bin/sh
# Isolated CPython buffer-protocol fault probe; PY needs development headers.
# Linux uses section GC so unrelated embedding/runtime glue is not linked.
# usage: PY=python3.13 CC=clang tools/check_cpu_buffers.sh [--negative-control] [SANITIZER_FLAGS]
set -eu
cd "$(dirname "$0")/.."
PY=${PY:-python3}
CC=${CC:-clang}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
# shellcheck disable=SC3045
ulimit -c 0  # Linux diagnostic; the intentional abort must not leave a core dump.
negative=0
if [ "${1:-}" = --negative-control ]; then negative=1; shift; fi
buffer_source=pyembed.c
if [ "$negative" = 1 ]; then
  # Mutate a temporary copy. The probe must detect the missing owning release.
  buffer_source="$tmp/pyembed.c"
  "$PY" - "$buffer_source" <<'PY'
from pathlib import Path
import sys
source = Path("pyembed.c").read_text()
old = "  if (b->export.obj) PyBuffer_Release(&b->export);"
assert source.count(old) == 1
Path(sys.argv[1]).write_text(source.replace(old, "  /* negative control: omit export release */"))
PY
fi
include=$($PY -c 'import sysconfig; print(sysconfig.get_path("include"))')
libdir=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
libname=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDLIBRARY"))')
# shellcheck disable=SC2086
$CC -O2 -g -Wall -Wextra -Werror -ffunction-sections -fdata-sections ${1:-} \
  -Dcalloc=pye_test_calloc -DPyCapsule_New=pye_test_capsule_new -c "$buffer_source" -o "$tmp/pyembed.o"
# shellcheck disable=SC2086
$CC -O2 -g -Wall -Wextra -Werror -I"$include" -ffunction-sections -fdata-sections ${1:-} \
  tests/ffi/cpu_buffer_probe.c "$tmp/pyembed.o" -Wl,--gc-sections -L"$libdir" -Wl,-rpath,"$libdir" \
  -l:"$libname" -o "$tmp/probe"
if [ "$negative" = 1 ]; then
  if "$tmp/probe" > "$tmp/output" 2>&1; then
    echo "FAIL: missing-release control unexpectedly passed"
    exit 1
  fi
  grep -Fq 'released == before + 1' "$tmp/output"
  echo "PASS missing-release negative control: release assertion failed as required"
else
  "$tmp/probe"
fi
