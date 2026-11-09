#!/bin/sh
# usage: clean-env.sh COMMAND [ARG...]: run COMMAND with every inherited PYSTACHY_* variable removed
# and a fixed, explicit PATH/LLVM (LLVM 18.1.3 default), PYSTACHY_JOBS=2, LC_ALL=C.
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$v"; done
export PATH=/usr/lib/llvm-18/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PYSTACHY_JOBS=2
export LC_ALL=C
exec "$@"
