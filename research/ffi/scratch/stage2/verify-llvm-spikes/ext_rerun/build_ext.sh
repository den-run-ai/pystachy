#!/bin/sh
# Build spikemod.abi3.so: program + boundary + C glue + runtime as ONE LLVM module (whole-program -O2),
# then internalize everything but PyInit_spikemod. Mirrors pystachy.py:16642 and :16653.
set -ex
cd "$(dirname "$0")"
PY=/home/user/pystachy/pystachy.py
STRIP='s/ "(target-cpu|target-features|tune-cpu)"="[^"]*"//g'
python3 $PY ir prog.py -o prog.ll
python3 libify.py prog.ll prog_eh.ll eh
# runtime: as the driver builds runtime-py-*.bc, from runtime_lib.c (+ -fPIC)
clang -O2 -fPIC -S -emit-llvm runtime_lib.c -o rtlib.ll -fexceptions
sed -E "$STRIP" rtlib.ll > rtlib-s.ll
llvm-as rtlib-s.ll -o rtlib-c.bc
llvm-link rtpy.ll rtlib-c.bc -o rtlib-l.bc
opt -O2 rtlib-l.bc -o rtlib.bc
# the C glue (what an ext lowering would emit), as bitcode so LLVM inlines across it
clang -O2 -fPIC -fexceptions -S -emit-llvm -I/usr/include/python3.13 spikemod.c -o glue.ll
sed -E "$STRIP" glue.ll > glue-s.ll
llvm-link prog_eh.ll glue-s.ll -o glue.bc
llvm-link --only-needed glue.bc rtlib.bc -o all.bc
opt -passes='internalize,default<O2>' -internalize-public-api-list=PyInit_spikemod all.bc -o all.opt.bc
clang -O2 -fPIC -c all.opt.bc -o all.o -Wno-unused-command-line-argument
clang -shared all.o -o spikemod.abi3.so -lm
