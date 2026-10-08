#!/bin/sh
# Record what CPython prints for differential tests, the way tests/run.sh runs them:
# tests/NAME.out is stdout followed by "[exit N]"; tests/NAME.err, kept only where CPython
# wrote to stderr, is the last line it wrote there. tests/NAME.in, if present, is stdin.
# usage: tests/record.sh NAME...      (PYTHON=python3.13 tests/record.sh NAME to pick one)
cd "$(dirname "$0")/.." || exit 1
PY=${PYTHON:-python3}
err=$(mktemp) || exit 1
for n in "$@"; do
  n=$(basename "$n" .py); in=/dev/null; [ -f "tests/$n.in" ] && in="tests/$n.in"
  # unset PYTHONUNBUFFERED: it changes what reaches a stdout the program shares (os.system)
  (env -u PYTHONUNBUFFERED "$PY" "tests/$n.py" a1 a2 < "$in"; echo "[exit $?]") > "tests/$n.out" 2> "$err"
  if [ -s "$err" ]; then tail -1 "$err" > "tests/$n.err"; else rm -f "tests/$n.err"; fi
  echo "$n: $(tail -1 "tests/$n.out") $(cat "tests/$n.err" 2>/dev/null)"
done
rm -f "$err"
