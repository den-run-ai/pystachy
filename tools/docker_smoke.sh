#!/bin/sh
# Test the installed compiler outside its source tree without running Python.
# Docker's final build stage runs this; CI may run it again as an arbitrary UID.
set -eu
compiler=${1:-pystachy}
[ $# -le 1 ] || { echo "usage: pystachy-smoke [COMPILER]" >&2; exit 2; }
work=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-docker-smoke.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
export PYSTACHY_CACHE="$work/cache"
cat > "$work/demo.py" <<'PY'
import fnmatch
from functools import lru_cache
import sys
import textwrap


@lru_cache(maxsize=2)
def route(name: str) -> str:
    if fnmatch.fnmatchcase(name, "api.*"):
        return "api"
    return "other"


for event in ["api.read", "api.read", "misc"]:
    print(route(event))
print(textwrap.fill("alpha beta gamma", width=10))
print("argument", sys.argv[1])
PY
cat > "$work/expected" <<'OUT'
api
api
other
alpha beta
gamma
argument from-container
OUT
# Relative source/output paths exercise the documented /work bind-mount usage.
cd "$work"
"$compiler" run demo.py from-container > jit.out
"$compiler" build demo.py -o demo
./demo from-container > aot.out
cmp expected jit.out
cmp expected aot.out
printf '%s\n' "installed JIT/AOT smoke: passed (fnmatch, lru_cache, textwrap, arguments)"
