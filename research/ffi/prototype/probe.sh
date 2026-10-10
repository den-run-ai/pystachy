#!/bin/sh
# Reruns the FFI probes against tree2 (the final prototype). Usage: probe.sh COMPILER-CMD
S=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2
T=$S/final/tree2; C=$S/capi-verify; R=$S/final/run; PYS="$1"
L13=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
L15=$C/py315/python/lib/libpython3.15.so.1.0; L15t=$C/py315t/python/lib/libpython3.15t.so.1.0
rm -rf $R; mkdir -p $R/emb $R/ext $R/s1 && cd $R
cp $S/final/w/emb/*.py emb/; cp $S/final/w/s1/*.py s1/; cp $S/final/w/fastmath.py $S/final/w/client.py ext/; cp $S/final/w/vj/viajson.py $S/final/w/vj/use2.py $S/final/w/vj/use3.py $S/final/w/vj/cb.py ext/
ok=0; bad=0
check() { if [ "${3%% *}" = uac ]; then tail -2 "$1" > "$1.t"; tail -2 "$2" > "$2.t"; set -- "$1.t" "$2.t" "$3"; fi; if cmp -s "$1" "$2"; then ok=$((ok+1)); echo "SAME  $3"; else bad=$((bad+1)); echo "DIFF  $3"; diff "$1" "$2" | head -8; fi; }
echo "### S1: @extern (twin vs JIT vs AOT, GC stress 7)"
cd $R/s1
PYTHONPATH=$T/tools/rt_cpython python3 zstats.py > twin.out 2>&1; echo "exit=$?" >> twin.out
PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run zstats.py > jit.out 2>&1; echo "exit=$?" >> jit.out; check twin.out jit.out "zstats jit"
$PYS build zstats.py -o zs && PYSTACHY_GC_STRESS=7 ./zs > aot.out 2>&1; echo "exit=$?" >> aot.out; check twin.out aot.out "zstats aot"
for f in e_int e_dup e_res e_rt e_list e_bool e_body; do echo "  $($PYS run $f.py 2>&1 | tail -1)"; done
echo "  ok_rt: $($PYS run ok_rt.py 2>&1)"
echo "### S2: pyobj embedding (twin 3.13 vs JIT/AOT 3.13, GC stress 3)"
cd $R/emb
for p in jsondemo uac sx fin; do
  PYTHONPATH=$T/tools/rt_cpython python3 $p.py > $p.twin 2>&1; echo "exit=$?" >> $p.twin
  PYSTACHY_LIBPYTHON=$L13 PYSTACHY_GC_STRESS_PROGRAM=3 $PYS run $p.py > $p.jit 2>&1; echo "exit=$?" >> $p.jit; check $p.twin $p.jit "$p jit 3.13"
  PYSTACHY_LIBPYTHON=$L13 $PYS build $p.py -o $p.exe && PYSTACHY_GC_STRESS=3 ./$p.exe > $p.aot 2>&1; echo "exit=$?" >> $p.aot; check $p.twin $p.aot "$p aot 3.13"
done
for p in jsondemo fin; do
  PYTHONHOME=$C/py315t/python PYSTACHY_LIBPYTHON=$L15t PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py > $p.j15t 2>&1; echo "exit=$?" >> $p.j15t; check $p.twin $p.j15t "$p jit 3.15t"
done
for v in py315 py315t; do L=$L15; [ $v = py315t ] && L=$L15t
  PYSTACHY_LIBPYTHON=$L $PYS build stw.py -o stw.$v && echo "  stw aot $v: $(PYTHONHOME=$C/$v/python ./stw.$v)"
done
echo "### S3: pystachy ext (abi3 and abi3t, GC stress 1)"
cd $R/ext
mkdir -p src a3 a3t; cp fastmath.py client.py src/; (cd src && python3 client.py > ../oracle.txt 2>&1)
$PYS ext fastmath.py -o a3/fastmath.abi3.so && $PYS ext fastmath.py --abi abi3t -o a3t/fastmath.abi3t.so
$PYS ext viajson.py -o a3/viajson.abi3.so && $PYS ext viajson.py --abi abi3t -o a3t/viajson.abi3t.so
cp client.py use2.py use3.py cb.py a3/; cp client.py use2.py use3.py cb.py a3t/
for so in a3/fastmath.abi3.so a3t/fastmath.abi3t.so a3/viajson.abi3.so a3t/viajson.abi3t.so; do echo "  $so exports: $(nm -D --defined-only $so | awk '{print $3}' | tr '\n' ' ')"; done
python3 $S/final/abi_check.py $C/stable_abi_3150.toml a3/fastmath.abi3.so 3.12; python3 $S/final/abi_check.py $C/stable_abi_3150.toml a3/viajson.abi3.so 3.12
python3 $S/final/abi_check.py $C/stable_abi_3150.toml a3t/fastmath.abi3t.so 3.15; python3 $S/final/abi_check.py $C/stable_abi_3150.toml a3t/viajson.abi3t.so 3.15
for py in /usr/bin/python3 $C/py314/python/bin/python3 $C/py315/python/bin/python3; do
  (cd a3 && PYSTACHY_GC_STRESS=1 $py client.py > ../c.out 2>&1); check oracle.txt c.out "fastmath abi3 on $($py -V 2>&1) (vs source run; expect the 2 listed deviations)"
  (cd a3 && PYSTACHY_GC_STRESS=1 $py use3.py > ../u.out 2>&1); echo "  viajson nested abi3 $($py -V 2>&1): $(tr '\n' ' ' < u.out)"
done
for py in $C/py313t/python/bin/python3 $C/py314t/python/bin/python3; do echo "  abi3 on $($py -VV | cut -c1-40): $(cd a3 && $py client.py 2>&1 | tail -1)"; done
for py in $C/py315/python/bin/python3 $C/py315t/python/bin/python3; do
  (cd a3t && PYSTACHY_GC_STRESS=1 $py -W ignore client.py > ../c.out 2>&1); check oracle.txt c.out "fastmath abi3t on $($py -VV | cut -c1-30) (vs source run)"
  (cd a3t && PYSTACHY_GC_STRESS=1 $py -W ignore use3.py > ../u.out 2>&1); echo "  viajson nested abi3t: $(tr '\n' ' ' < u.out)"
done
echo "  abi3t on 3.15t, PYTHON_GIL=0: $(cd a3t && PYTHON_GIL=0 $C/py315t/python/bin/python3 client.py 2>&1 | tail -1)"
echo "### S3 @export: .so vs its source run under the twin (oracle recorded on 3.13)"
mkdir -p $R/x/src $R/x/so && cd $R/x && cp $S/final/w/x/fastmath.py $S/final/w/client.py $S/final/w/x/client2.py $S/final/w/x/bad_pub.py $S/final/w/x/bad_def.py .
cp fastmath.py client.py client2.py src/; cp client.py client2.py so/
(cd src && PYTHONPATH=$T/tools/rt_cpython python3 client.py > ../o1.txt 2>&1; PYTHONPATH=$T/tools/rt_cpython python3 client2.py > ../o2.txt 2>&1)
$PYS ext fastmath.py -o so/fastmath.abi3.so && $PYS ext fastmath.py --abi abi3t -o so/fastmath.abi3t.so
for py in /usr/bin/python3 $C/py314/python/bin/python3 $C/py315/python/bin/python3 $C/py315t/python/bin/python3; do
  (cd so && PYSTACHY_GC_STRESS=1 $py -W ignore client.py 2>&1 | sed 2d > ../s1.txt; PYSTACHY_GC_STRESS=1 $py -W ignore client2.py > ../s2.txt 2>&1)
  sed 2d o1.txt > o1s.txt; check o1s.txt s1.txt "@export client on $($py -VV | cut -c1-34)"; check o2.txt s2.txt "@export client2 on $($py -VV | cut -c1-34)"
done
for b in bad_pub bad_def; do echo "  $($PYS ext $b.py 2>&1 | tail -1)"; done
echo "### probes: $ok same, $bad different"
