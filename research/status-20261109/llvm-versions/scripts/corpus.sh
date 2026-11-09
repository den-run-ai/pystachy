#!/bin/bash
# usage: corpus.sh N LOG FILES...   tests/run.sh with LLVM N, its private cache, 2 jobs, scratch TMPDIR
N=$1; LOG=$2; shift 2
cd /home/user/wt/llvm-versions
TIMEFORMAT="elapsed %Rs"
{ time /tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/llvmver.NWwbC2/scripts/penv.sh $N env PYSTACHY_JOBS=2 TMPDIR=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/llvmver.NWwbC2/tmp tests/run.sh ./pystachy "jit aot" "$@"; echo "EXIT=$?"; } > $LOG 2>&1
