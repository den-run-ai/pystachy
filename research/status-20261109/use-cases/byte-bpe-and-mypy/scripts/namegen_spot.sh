#!/bin/bash
# Unchanged upstream mypyc NameGenerator on the main-equivalent compiler (no timing).
# Usage: namegen_spot.sh AGENT_DIR
set -u
D=$1
M=$D/main
C=/home/user/wt/alpha2-qual/pystachy
O=$D/out/namegen
mkdir -p "$O" "$D/namegen-input" "$D/namegen-probe"
BASE=(env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0)
NATIVE=("${BASE[@]}" PYSTACHY_HOME="$M" PYSTACHY_CACHE="$D/cache" PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2)
PY=/usr/local/bin/python3

# Input: mypyc/namegen.py from the pinned mypy 2.4.1 dev tool; must equal the recorded hash.
cp /home/user/wt/devenv/lib/python3.13/site-packages/mypyc/namegen.py "$D/namegen-input/namegen.py"
echo "739a7bcb1c54c96a8944da8a9a4542475c56d2ee392db22ba933e74749fe23ae  $D/namegen-input/namegen.py" | sha256sum -c - || exit 1
git -C /home/user/pystachy show origin/research/compiler-host-scaling:bench/compiler_parallel/namegen_probe.py > "$D/namegen-probe/namegen_probe.py" || exit 1
sha256sum "$D/namegen-probe/namegen_probe.py"
P=$D/namegen-probe/namegen_probe.py

for rounds in 2 2000; do
  ( cd "$D" && "${BASE[@]}" PYTHONPATH="$D/namegen-input" "$PY" "$P" $rounds; echo "[exit $?]" ) > "$O/cpython-$rounds" 2> "$O/cpython-$rounds.err"
  ( cd "$D" && "${NATIVE[@]}" PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_PATH="$D/namegen-input" "$C" run "$P" $rounds; echo "[exit $?]" ) > "$O/jit-$rounds" 2> "$O/jit-$rounds.err"
done
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PATH="$D/namegen-input" "$C" build "$P" -o "$D/namegen-aot" ) > "$O/aot-build.log" 2>&1
echo "aot build status $?"
for rounds in 2 2000; do
  ( cd "$D" && "$D/namegen-aot" $rounds; echo "[exit $?]" ) > "$O/aot-$rounds" 2> "$O/aot-$rounds.err"
  for mode in jit aot; do
    if cmp -s "$O/cpython-$rounds" "$O/$mode-$rounds"; then echo "namegen rounds=$rounds $mode: identical to CPython ($(wc -l < "$O/cpython-$rounds") lines)"; else echo "namegen rounds=$rounds $mode: DIFFERS"; diff "$O/cpython-$rounds" "$O/$mode-$rounds" | head -8; head -c 600 "$O/$mode-$rounds.err"; fi
  done
done
tail -2 "$O/cpython-2000"

# Upstream mypyc test_namegen.py bodies (five methods), transcribed without unittest.
U=$D/namegen-probe/upstream_tests.py
sha256sum /home/user/wt/devenv/lib/python3.13/site-packages/mypyc/test/test_namegen.py
( cd "$D" && "${BASE[@]}" PYTHONPATH="$D/namegen-input" "$PY" "$U"; echo "[exit $?]" ) > "$O/tests.cpython" 2> "$O/tests.cpython.err"
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_PATH="$D/namegen-input" "$C" run "$U"; echo "[exit $?]" ) > "$O/tests.jit" 2> "$O/tests.jit.err"
( cd "$D" && "${NATIVE[@]}" PYSTACHY_PATH="$D/namegen-input" "$C" build "$U" -o "$D/namegen-tests-aot" ) > "$O/tests-build.log" 2>&1
( cd "$D" && "$D/namegen-tests-aot"; echo "[exit $?]" ) > "$O/tests.aot" 2> "$O/tests.aot.err"
cat "$O/tests.cpython"
for mode in jit aot; do
  if cmp -s "$O/tests.cpython" "$O/tests.$mode"; then echo "upstream tests $mode: identical to CPython"; else echo "upstream tests $mode: DIFFERS"; diff "$O/tests.cpython" "$O/tests.$mode" | head -8; head -c 600 "$O/tests.$mode.err"; fi
done
date -u +%FT%TZ
