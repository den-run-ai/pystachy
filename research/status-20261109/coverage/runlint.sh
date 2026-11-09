#!/bin/sh
# make lint and check-repository in the worktree with the pinned dev tools
cd /home/user/wt/coverage-gaps || exit 1
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z0-9_]*\)=.*/\1/p'); do unset "$v"; done
export PATH=/home/user/wt/devenv/bin:$PATH
make lint check-repository PY=python3 LLVMBIN=/usr/lib/llvm-18/bin/
st=$?
echo "lint exit $st"
exit $st
