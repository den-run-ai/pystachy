#!/bin/sh
# make check-fast lint in the worktree with the pinned dev tools first on PATH (CI's Lint step)
cd /home/user/wt/coverage-gaps || exit 1
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z0-9_]*\)=.*/\1/p'); do unset "$v"; done
export PATH=/home/user/wt/devenv/bin:$PATH PYSTACHY_LLVM=/usr/lib/llvm-18/bin
t0=$(date +%s)
make check-fast lint PY=python3 LLVMBIN=/usr/lib/llvm-18/bin/
st=$?
echo "check-fast lint exit $st after $(($(date +%s) - t0)) s"
python3 -m unittest discover -s tools -p test_coverage_report.py; a=$?
python3 -m unittest discover -s tools -p test_workflow_limits.py; b=$?
echo "coverage_report tests $a, workflow limits $b"
exit $st
