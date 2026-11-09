#!/bin/sh
# runs the new tests with main's native compiler, JIT and AOT, then under program GC stress
cd /home/user/wt/coverage-gaps || exit 1
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z0-9_]*\)=.*/\1/p'); do unset "$v"; done
S=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/covgaps
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2 PYSTACHY_CACHE=$S/native-cache
F="tests/programs/inference/dynany_type_is_unopted.py tests/programs/inference/dynany_native_int_list_prefix.py tests/programs/inference/dyn_star_reducer_arity.py"
# shellcheck disable=SC2086
tests/run.sh /home/user/pystachy/pystachy "jit aot" $F; a=$?
# shellcheck disable=SC2086
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh /home/user/pystachy/pystachy "jit aot" $F; b=$?
echo "normal $a, gc-stress $b"
