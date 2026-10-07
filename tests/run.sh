#!/bin/sh
# Differential tests. Every tests/*.py must print exactly what CPython printed
# (stdout + exit code, recorded in tests/*.out) both JIT-run and AOT-compiled; where
# CPython wrote to stderr, the last line (tests/*.err) must match too.
# Every tests/errors/*.py must be rejected with the message in its first line, and every
# tests/deviations/*.py must print its hand-written .out (documented deviations from CPython).
# usage: tests/run.sh [COMPILER [MODES]]   (default: ./pystachy "jit aot"; e.g. "python3 pystachy.py")
cd "$(dirname "$0")/.." || exit 1
PYS=${1:-./pystachy}
MODES=${2:-jit aot}
T=${TMPDIR:-/tmp}/pystachy-tests.$$
mkdir -p "$T"
pass=0; fail=0
for t in tests/*.py; do
  n=$(basename "$t" .py); in=/dev/null; [ -f "tests/$n.in" ] && in="tests/$n.in"
  for mode in $MODES; do
    if [ $mode = jit ]; then
      ($PYS run "$t" a1 a2 < "$in"; echo "[exit $?]") > "$T/$n.$mode" 2> "$T/$n.err"
    else
      $PYS build "$t" -o "$T/$n.exe" 2> "$T/$n.err" &&
        ("$T/$n.exe" a1 a2 < "$in"; echo "[exit $?]") > "$T/$n.$mode" 2>> "$T/$n.err"
    fi
    if cmp -s "$T/$n.$mode" "tests/$n.out" && { [ ! -f "tests/$n.err" ] || [ "$(tail -1 "$T/$n.err")" = "$(cat "tests/$n.err")" ]; }; then
      pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL $n ($mode)"; diff "tests/$n.out" "$T/$n.$mode" | head -10
      [ -f "tests/$n.err" ] && echo "  stderr: want '$(cat "tests/$n.err")', got '$(tail -1 "$T/$n.err")'"; head -5 "$T/$n.err"; fi
  done
done
# Documented deviations from CPython: tests/deviations/*.out is written by hand and holds
# stdout and stderr together (the runtime flushes stdout before reporting an error).
for t in tests/deviations/*.py; do
  [ -f "$t" ] || continue
  n=$(basename "$t" .py); exp="tests/deviations/$n.out"
  for mode in $MODES; do
    if [ $mode = jit ]; then
      ($PYS run "$t" a1 a2 < /dev/null 2>&1; echo "[exit $?]") > "$T/dev.$n.$mode"
    else
      { $PYS build "$t" -o "$T/dev.$n.exe" 2>&1 && "$T/dev.$n.exe" a1 a2 < /dev/null 2>&1; echo "[exit $?]"; } > "$T/dev.$n.$mode"
    fi
    if cmp -s "$T/dev.$n.$mode" "$exp"; then pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL deviations/$n ($mode)"; diff "$exp" "$T/dev.$n.$mode" | head -10; fi
  done
done
for t in tests/errors/*.py; do
  [ -f "$t" ] || continue
  want=$(head -1 "$t" | sed 's/^# error: //')
  if $PYS ir "$t" > /dev/null 2> "$T/err" || ! grep -qF "$want" "$T/err"; then
    fail=$((fail + 1)); echo "FAIL $t: expected error '$want', got: $(cat "$T/err")"
  else pass=$((pass + 1)); fi
done
rm -rf "$T"
echo "$pass passed, $fail failed"
[ $fail = 0 ]
