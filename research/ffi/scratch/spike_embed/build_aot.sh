#!/bin/sh
# usage: build_aot.sh prog.py exe   (Pystachy program with py_* stubs -> executable linked with libpython3.13)
set -e
S=$(dirname "$0"); P=$1; E=$2
RTB=$(ls $S/home/build/runtime-py-*.bc)
PYSTACHY_HOME=$S/home python3 $S/home/pystachy.py ir $P -o $P.ll
python3 $S/postprocess.py $P.ll $P.pp.ll
llvm-link-18 --only-needed $P.pp.ll $S/pyshim.bc $RTB -o $P.bc
clang -O2 -c $P.bc -o $P.o -Wno-unused-command-line-argument
clang $P.o -o $E -lm $(python3.13-config --ldflags --embed)
