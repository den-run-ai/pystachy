#!/bin/bash
# The JIT's cleanup alone (PYSTACHY_JIT_OPT=0) against the new default (loop passes within the
# inlining budget), on the loop-passes branch's build: #1456's run_all.sh workloads
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
cd $SP/pr-jitlp || exit 1
env -u PYSTACHY_HOME -u PYSTACHY_LLVM -u PYSTACHY_OPT JV_VARIANTS="cleanup=PYSTACHY_JIT_OPT=0;default=" \
  bash $SP/jitopt-meas/run_all.sh $SP/pr-jitlp $SP/passx/final tiny padded imports router nbody spectral mandel sieve fib dictcount words \
  pp_chaos pp_float pp_nbody pp_raytrace pp_scimark pp_spectral_norm pp_fannkuch pp_nqueens pp_regex_v8 pp_richards pp_go pp_hexiom pp_json_loads pp_json_dumps pp_generators \
  long_richards long_regex_effbot long_go long_json_loads long_chaos long_raytrace long_scimark long_nbody long_generators
