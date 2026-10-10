#!/bin/sh
# UBSan in trap mode (a .so in python cannot load the UBSan runtime) over the three directions, AOT
F=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2/final; T=$F/tree2; R=$F/run
export PYSTACHY_CFLAGS='-fsanitize=undefined -fsanitize-trap=undefined'
mkdir -p $F/ub && cd $F/ub && cp $R/s1/zstats.py $R/emb/jsondemo.py $R/emb/fin.py $R/emb/finside.py . && cp $R/x/fastmath.py $R/x/client2.py .
$T/pystachy build zstats.py -o zs && PYSTACHY_GC_STRESS=7 ./zs > zs.out 2>&1; echo "exit=$?" >> zs.out; cmp zs.out $R/s1/twin.out && echo "UBSAN-trap zstats aot: same as twin"
for p in jsondemo fin; do PYSTACHY_LIBPYTHON=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0 $T/pystachy build $p.py -o $p.exe && PYSTACHY_GC_STRESS=3 ./$p.exe > $p.out 2>&1; echo "exit=$?" >> $p.out; cmp $p.out $R/emb/$p.twin && echo "UBSAN-trap $p aot: same as twin"; done
$T/pystachy ext fastmath.py -o fastmath.abi3.so && PYSTACHY_GC_STRESS=1 python3 client2.py > c2.out 2>&1; cmp c2.out $R/x/o2.txt && echo "UBSAN-trap fastmath ext: same as twin oracle"
