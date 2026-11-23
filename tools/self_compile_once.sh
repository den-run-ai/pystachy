#!/bin/sh
# Bootstrap check: COMPILER compiles the compiler's own source (pystachy.py) to OUT.ll, as
# `COMPILER ir pystachy.py -o OUT.ll`, and must infer its types in one attempt. A restart
# (diagnostics.Rejoin) compiles the whole program again from loading on, so one variable,
# field or return that holds two types can double every self-compilation.
# The attempts are counted from PYSTACHY_TIMING's program.attempt records; the compiler's
# other messages pass through (its timing records too, where the caller set PYSTACHY_TIMING=1).
# tools/inference_restarts.py names what restarted it.
# usage: tools/self_compile_once.sh COMPILER OUT.ll
[ $# -eq 2 ] || { echo 'usage: tools/self_compile_once.sh COMPILER OUT.ll' >&2; exit 2; }
compiler=$1
out=$2
err=$(mktemp "${TMPDIR:-/tmp}/pystachy-self-compile.XXXXXX") || exit 1
trap 'rm -f "$err"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
tab=$(printf '\t')
PYSTACHY_TIMING=1 "$compiler" ir pystachy.py -o "$out" 2> "$err"
status=$?
if [ "${PYSTACHY_TIMING:-}" = 1 ]; then
  cat "$err" >&2
else
  grep -v "^pystachy-timing$tab" "$err" >&2
fi
[ "$status" -eq 0 ] || exit "$status"
attempts=$(grep -c "^pystachy-timing${tab}program\.attempt$tab" "$err")
if [ "$attempts" -ne 1 ]; then
  echo "self_compile_once: $compiler took $attempts type-inference attempts on pystachy.py, where one is required." >&2
  echo "Each restart compiles the whole compiler again: usually a variable, field or return holds two types." >&2
  echo "Run 'python3 tools/inference_restarts.py' to name each one, then rename or annotate it." >&2
  exit 1
fi
