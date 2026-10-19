#!/bin/sh
# Coverage of the compiler's own source (make coverage; docs/testing.md#compiler-coverage): tests/run.sh
# runs the corpus, or the FILEs given, JIT and AOT with the CPython-hosted compiler ($PY -m pystachy, as
# make test-py runs it) under coverage.py, as .coveragerc sets it: the lines and branches of
# src/pystachy_compiler/, one data file per compiler process, combined afterwards. The runtime cache is
# a new, empty one, so that the runtime is built (runtime.py compiled) under coverage on every run.
# Report only: it fails when a test fails or a compiler process left no data, never on a percentage.
# Writes build/coverage/: html/ (the annotated source), coverage.json, tests.log (tests/run.sh's
# report), summary.md (the commit, the tests' counts, the time taken and a table of the modules) and
# badge.json (the total, as a shields.io endpoint badge).
# usage: tools/coverage.sh [FILE...]   env: PY (default python3), which has coverage.py
#        (pip install -r tools/requirements-dev.txt)
cd "$(dirname "$0")/.." || exit 1
PY=${PY:-python3}
C=build/coverage
$PY -m coverage --version > /dev/null || { echo "tools/coverage.sh: $PY has no coverage.py (pip install -r tools/requirements-dev.txt)" >&2; exit 1; }
rm -rf "$C" && mkdir -p "$C" || exit 1
cache=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-coverage.XXXXXX") || exit 1
trap 'rm -rf "$cache"' EXIT
trap 'exit 130' INT TERM
start=$(date +%s)
PYSTACHY_CACHE=$cache tests/run.sh "$PY -m coverage run -m pystachy" "jit aot" "$@" > "$C/tests.log" 2>&1
st=$?
secs=$(($(date +%s) - start))
cat "$C/tests.log"
[ $st = 0 ] || exit $st
# every compiler process saves its data: the run that builds the runtime, and one per check
passed=$(tail -1 "$C/tests.log" | sed -n 's/^\([0-9]*\) passed, 0 failed$/\1/p')
n=$(find "$C" -name 'data.*' | wc -l | tr -d ' ')
[ -n "$passed" ] && [ "$n" = $((passed + 1)) ] || {
  echo "tools/coverage.sh: $n coverage data files, for $passed checks and the runtime's build" >&2; exit 1; }
$PY -m coverage combine -q && $PY -m coverage html -q && $PY -m coverage json -q || exit 1
rev=$(git rev-parse HEAD 2> /dev/null) || rev=unknown
dirty=
[ -z "$(git status --porcelain --untracked-files=no 2> /dev/null)" ] || dirty=" with uncommitted changes"
{
  echo "## Hosted compiler coverage"
  echo
  echo "Commit \`$rev\`$dirty: $(tail -1 "$C/tests.log") (tests/run.sh, JIT and AOT, $n compiler processes) in $secs s."
  echo "Lines and branches of src/pystachy_compiler/, run by CPython; not runtime.c, runtime.py or lib/."
  echo
  $PY -m coverage report --format=markdown
} > "$C/summary.md" || exit 1
total=$($PY -m coverage report --format=total) || exit 1
color=$(awk -v t="$total" 'BEGIN { print (t >= 90 ? "brightgreen" : t >= 80 ? "green" : t >= 70 ? "yellowgreen" : t >= 60 ? "yellow" : t >= 50 ? "orange" : "red") }') || exit 1
printf '{"schemaVersion": 1, "label": "hosted compiler coverage", "message": "%s%%", "color": "%s"}\n' "$total" "$color" > "$C/badge.json"
$PY -m coverage report
echo "hosted compiler coverage: $total% (build/coverage/html/index.html, build/coverage/summary.md)"
