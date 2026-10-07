#!/bin/sh
# Differential tests. Every tests/*.py must print exactly what CPython printed
# (stdout + exit code, recorded in tests/*.out) both JIT-run and AOT-compiled.
# Every tests/errors/*.py must be rejected with the message in its first line.
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
    if cmp -s "$T/$n.$mode" "tests/$n.out"; then pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL $n ($mode)"; diff "tests/$n.out" "$T/$n.$mode" | head -10; head -5 "$T/$n.err"; fi
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
