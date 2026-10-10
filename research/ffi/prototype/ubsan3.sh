#!/bin/sh
# UBSan in trap mode (a .so in python cannot load the UBSan runtime) over the three directions, AOT, tree3
F=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2/final; T=$F/tree3; R=$F/run3; TW=$T/tools/rt_cpython
export PYSTACHY_CFLAGS='-fsanitize=undefined -fsanitize-trap=undefined'
L13=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
rm -rf $F/ub3; mkdir -p $F/ub3 && cd $F/ub3 && cp $R/s1/zstats.py $R/emb/jsondemo.py $R/emb/fin.py $R/emb/finside.py $R/emb/leak.py . && mkdir -p x && cp $R/ext/*.py x/
$T/pystachy build zstats.py -o zs && PYSTACHY_GC_STRESS=7 ./zs > zs.out 2>&1; echo "exit=$?" >> zs.out; cmp zs.out $R/s1/zstats.twin && echo "UBSAN-trap zstats aot: same as twin"
for p in jsondemo fin leak; do PYSTACHY_LIBPYTHON=$L13 $T/pystachy build $p.py -o $p.exe && PYSTACHY_GC_STRESS=7 ./$p.exe > $p.out 2>&1; echo "exit=$?" >> $p.out; cmp $p.out $R/emb/$p.twin && echo "UBSAN-trap $p aot: same as twin"; done
cd x && for m in fastmath mg reent; do $T/pystachy ext $m.py -o $m.abi3.so; done && rm -f fastmath.py mg.py reent.py
PYSTACHY_GC_STRESS=1 python3.13 client2.py > c2.out 2>&1; (cd ../../run3/ext/src && PYTHONPATH=$TW python3.13 client2.py) > c2.want 2>&1; cmp c2.out c2.want && echo "UBSAN-trap fastmath ext: same as its source run"
PYSTACHY_GC_STRESS=1 python3.13 reclient.py > re.out 2>&1; (cd ../../run3/ext/src && PYTHONPATH=$TW PYSTACHY_GC_STRESS=1 python3.13 reclient.py) > re.want 2>&1; cmp re.out re.want && echo "UBSAN-trap reent ext (nested entries, releases): same as its source run"
python3.13 pk3.py > pk.out 2>&1; (cd ../../run3/ext/src && PYTHONPATH=$TW python3.13 pk3.py) > pk.want 2>&1; cmp pk.out pk.want && echo "UBSAN-trap mg ext (pickle, spawn Pool): same as its source run"
