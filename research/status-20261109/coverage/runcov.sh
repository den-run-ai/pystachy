#!/bin/sh
# runs tools/coverage.sh in the worktree with a clean PYSTACHY_* environment; args: FILE...
cd /home/user/wt/coverage-gaps || exit 1
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z0-9_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2 PY=/home/user/wt/devenv/bin/python3
export PATH=/home/user/wt/devenv/bin:$PATH
t0=$(date +%s)
tools/coverage.sh "$@"
st=$?
echo "coverage.sh exit $st after $(($(date +%s) - t0)) s"
exit $st
