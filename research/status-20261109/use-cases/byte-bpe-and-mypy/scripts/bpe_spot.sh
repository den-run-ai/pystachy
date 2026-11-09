#!/bin/bash
# Byte-BPE correctness spot check on the main-equivalent compiler (no timing).
# Usage: bpe_spot.sh AGENT_DIR
set -u
D=$1
M=$D/main
C=/home/user/wt/alpha2-qual/pystachy
O=$D/out/bpe
mkdir -p "$O"
CORPUS=$M/bench/pyperformance/data/frankenstein_intro.txt
BASE=(env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0)
NATIVE=("${BASE[@]}" PYSTACHY_HOME="$M" PYSTACHY_CACHE="$D/cache" PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2)
PY=/usr/local/bin/python3

echo "compiler sha256 $(sha256sum "$C" | cut -c1-64)"
"${NATIVE[@]}" "$C" --version
"$PY" --version
date -u +%FT%TZ

# Probe modules: pristine kernels, the port, and five single reverts.
rm -rf "$D/variants"
"$PY" "$D/scripts/make_variants.py" "$M" "$D/variants" || exit 1

# 1. Demo program: pristine CPython, adapted CPython, JIT (program cache off), AOT.
run_demo() {  # tag, then demo arguments
  local tag=$1; shift
  ( cd "$D" && "${BASE[@]}" PYTHONPATH="$D/variants/pristine" "$PY" "$M/examples/byte_bpe/demo.py" "$@"; echo "[exit $?]" ) > "$O/demo-$tag.pristine" 2> "$O/demo-$tag.pristine.err"
  ( cd "$D" && "${BASE[@]}" PYTHONPATH="$M/bench/pyperformance" "$PY" "$M/examples/byte_bpe/demo.py" "$@"; echo "[exit $?]" ) > "$O/demo-$tag.adapted" 2> "$O/demo-$tag.adapted.err"
  ( cd "$D" && "${NATIVE[@]}" PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_PATH="$M/bench/pyperformance" "$C" run "$M/examples/byte_bpe/demo.py" "$@"; echo "[exit $?]" ) > "$O/demo-$tag.jit" 2> "$O/demo-$tag.jit.err"
  ( cd "$D" && "$D/byte-bpe-aot" "$@"; echo "[exit $?]" ) > "$O/demo-$tag.aot" 2> "$O/demo-$tag.aot.err"
  for mode in adapted jit aot; do
    if cmp -s "$O/demo-$tag.pristine" "$O/demo-$tag.$mode"; then echo "demo $tag $mode: identical to pristine CPython"; else echo "demo $tag $mode: DIFFERS"; diff "$O/demo-$tag.pristine" "$O/demo-$tag.$mode" | head -5; fi
  done
}
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PATH="$M/bench/pyperformance" "$C" build "$M/examples/byte_bpe/demo.py" -o "$D/byte-bpe-aot" ) > "$O/aot-build.log" 2>&1
echo "aot build status $? ($(wc -c < "$D/byte-bpe-aot" 2>/dev/null) bytes)"
run_demo custom "$CORPUS" 1024 'Hello, Sebastian! 日本語 🦉'
run_demo default "$CORPUS" 1024
run_demo base256 "$CORPUS" 256 $'tab\thereé'
run_demo toosmall "$CORPUS" 255
cat "$O/demo-custom.pristine"

# 2. Differential fixture against its recorded .out (JIT program cache off, then AOT).
T=$M/tests/programs/apps/byte_bpe.py
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_PATH="$M/bench/pyperformance" "$C" run "$T" a1 a2 < /dev/null; echo "[exit $?]" ) > "$O/fixture.jit" 2> "$O/fixture.jit.err"
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PATH="$M/bench/pyperformance" "$C" build "$T" -o "$D/byte-bpe-fixture" ) > "$O/fixture-build.log" 2>&1
( cd "$D" && "$D/byte-bpe-fixture" a1 a2 < /dev/null; echo "[exit $?]" ) > "$O/fixture.aot" 2> "$O/fixture.aot.err"
for mode in jit aot; do
  if cmp -s "$M/tests/programs/apps/byte_bpe.out" "$O/fixture.$mode"; then echo "fixture $mode: matches byte_bpe.out"; else echo "fixture $mode: DIFFERS"; diff "$M/tests/programs/apps/byte_bpe.out" "$O/fixture.$mode" | head -5; fi
done

# 3. Frontend probes: does each original upstream spelling compile on main today?
for v in port pristine r1_decoder_annotation r2_errors_keyword r3_enumerate_zip r4_ranks_annotation r5_untyped_counter; do
  ( cd "$D" && "${NATIVE[@]}" PYSTACHY_PATH="$D/variants/$v" "$C" ir "$M/examples/byte_bpe/stages.py" -o "$D/variants/$v/stages.ll" ) > "$D/variants/$v/ir.log" 2>&1
  s=$?
  echo "ir probe $v: status $s; $(head -c 400 "$D/variants/$v/ir.log" | tr '\n' ' ')"
done
date -u +%FT%TZ
