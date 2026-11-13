#!/bin/bash
# gates3.sh TREE BASE PREFIX FILES: build TREE with two jobs, run FILES (test cases) in JIT/AOT,
# hosted and GC-stress modes, the make gates, and the opt-in verify group with the PR sample
# against BASE
S=/tmp/claude-0/-home-user-pystachy/8dfd0d3f-eb31-5d1b-8d1b-90a856e3b0b1/scratchpad
. $S/env316.sh
tree=$1; base=$2; lp=$3; F=$4
cd $tree || exit 1
export PYSTACHY_JOBS=2
make -j2 > $lp-make.log 2>&1; echo "make exit $?"
make test FILES="$F" > $lp-test.log 2>&1; tail -1 $lp-test.log | sed 's/^/jit+aot: /'
make test-py FILES="$F" > $lp-testpy.log 2>&1; tail -1 $lp-testpy.log | sed 's/^/hosted: /'
PYSTACHY_GC_STRESS_PROGRAM=1 make test FILES="$F" > $lp-gc.log 2>&1; tail -1 $lp-gc.log | sed 's/^/gc-stress: /'
for t in check-recordings lint check-ir check-runtime check-repository check-fast; do make $t > $lp-$t.log 2>&1; echo "$t exit $?"; done
VERIFY_PROFILE=pr CI_BASE_SHA=$base PY=$PY PYTHON=$PY tests/verify.sh opt-in > $lp-verify-optin.log 2>&1; echo "verify opt-in exit $?"
grep -E "^(bootstrap|dynany-optin-0|python-int-optin-0|annotation-widening) " $lp-verify-optin.log | sort -u | cut -c1-110
git rev-parse --short HEAD; git status --short | wc -l
