#!/bin/sh
# usage: build.sh RUNTIME.c GLUE.c   (spike_ext/build_ext.sh, parameterized)
set -e
cd "$(dirname "$0")"
RT=$1; GL=$2
PY=/home/user/pystachy/pystachy.py
STRIP='s/ "(target-cpu|target-features|tune-cpu)"="[^"]*"//g'
python3 $PY ir prog.py -o prog.ll
python3 libify.py prog.ll prog_eh.ll eh >/dev/null
clang -O2 -fPIC -S -emit-llvm $RT -o rtlib.ll -fexceptions
sed -E "$STRIP" rtlib.ll > rtlib-s.ll
llvm-as rtlib-s.ll -o rtlib-c.bc
llvm-link rtpy.ll rtlib-c.bc -o rtlib-l.bc
opt -O2 rtlib-l.bc -o rtlib.bc
clang -O2 -fPIC -fexceptions -S -emit-llvm -I/usr/include/python3.13 $GL -o glue.ll
sed -E "$STRIP" glue.ll > glue-s.ll
llvm-link prog_eh.ll glue-s.ll -o glue.bc
llvm-link --only-needed glue.bc rtlib.bc -o all.bc
opt -passes='internalize,default<O2>' -internalize-public-api-list=PyInit_spikemod all.bc -o all.opt.bc
clang -O2 -fPIC -c all.opt.bc -o all.o -Wno-unused-command-line-argument
clang -shared all.o -o spikemod.abi3.so -lm
