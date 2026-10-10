#!/bin/sh
# FFI probes against tree3 (the final prototype). Usage: probe3.sh COMPILER-CMD
# Every comparison is native output against the same file run by CPython with the twins
# (tools/rt_cpython on PYTHONPATH), on the same CPython version.
S=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2
F=$S/final; T=$F/tree3; C=$S/capi-verify; X=$F/fx; R=$F/run3; PYS="$1"; TW=$T/tools/rt_cpython
L12=/usr/lib/x86_64-linux-gnu/libpython3.12.so.1.0; L13=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
L15=$C/py315/python/lib/libpython3.15.so.1.0; L15t=$C/py315t/python/lib/libpython3.15t.so.1.0
P12=/usr/bin/python3.12; P13=/usr/bin/python3.13; P14=$C/py314/python/bin/python3; P15=$C/py315/python/bin/python3; P15t=$C/py315t/python/bin/python3
P13t=$C/py313t/python/bin/python3; P14t=$C/py314t/python/bin/python3
TOML=$C/stable_abi_3150.toml
rm -rf $R; mkdir -p $R && cp -r $X/s1 $X/loc $X/emb $X/ext $R/
ok=0; bad=0
check() { if cmp -s "$1" "$2"; then ok=$((ok+1)); echo "SAME  $3"; else bad=$((bad+1)); echo "DIFF  $3"; diff "$1" "$2" | head -10; fi; }
run() { out=$1; shift; sh -c "$*" > $out 2>&1; echo "exit=$?" >> $out; }

echo "### S1: @extern (twin vs JIT vs AOT, GC stress 7)"
cd $R/s1
for p in zstats sat; do
  run $p.twin "PYTHONPATH=$TW $P13 $p.py"
  run $p.jit "PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py"; check $p.twin $p.jit "$p jit"
  $PYS build $p.py -o $p.exe && run $p.aot "PYSTACHY_GC_STRESS=7 ./$p.exe"; check $p.twin $p.aot "$p aot"
done
for f in e_int e_dup e_res e_rt e_list e_bool e_body; do echo "  $($PYS run $f.py 2>&1 | tail -1)"; done
echo "  ok_rt: $($PYS run ok_rt.py 2>&1)"
cd $R/loc
run m.cpy "$P13 m.py"; run m.jit "$PYS run m.py"; check m.cpy m.jit "a program's own ffi.py (jit)"
$PYS build m.py -o m.exe && run m.aot "./m.exe"; check m.cpy m.aot "a program's own ffi.py (aot)"
echo "  own ffi.py + pyobj: $(PYSTACHY_LIBPYTHON=$L13 $PYS run pm.py 2>&1 | tail -1)"

echo "### S2: pyobj embedding"
cd $R/emb
for p in jsondemo uac sx sxb fin; do
  run $p.twin "PYTHONPATH=$TW $P13 $p.py"
  run $p.jit "PYSTACHY_LIBPYTHON=$L13 PYSTACHY_GC_STRESS_PROGRAM=3 $PYS run $p.py"; check $p.twin $p.jit "$p jit 3.13 (GC stress 3)"
  PYSTACHY_LIBPYTHON=$L13 $PYS build $p.py -o $p.exe && run $p.aot "PYSTACHY_GC_STRESS=3 ./$p.exe"; check $p.twin $p.aot "$p aot 3.13 (GC stress 3)"
  run $p.t12 "PYTHONPATH=$TW $P12 $p.py"
  PYSTACHY_LIBPYTHON=$L12 $PYS build $p.py -o $p.e12 && run $p.a12 "PYSTACHY_GC_STRESS=3 ./$p.e12"; check $p.t12 $p.a12 "$p aot 3.12 (GC stress 3)"
done
for p in jsondemo fin leak; do
  run $p.t15t "PYTHONPATH=$TW $P15t $p.py"
  run $p.j15t "PYTHONHOME=$C/py315t/python PYSTACHY_LIBPYTHON=$L15t PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py"; check $p.t15t $p.j15t "$p jit 3.15t (GC stress 7)"
done
run leak.twin "PYTHONPATH=$TW $P13 leak.py"
run leak.jit "PYSTACHY_LIBPYTHON=$L13 PYSTACHY_GC_STRESS_PROGRAM=50 $PYS run leak.py"; check leak.twin leak.jit "leak jit 3.13 (GC stress 50)"
PYSTACHY_LIBPYTHON=$L13 $PYS build leak.py -o leak.exe && run leak.aot "PYSTACHY_GC_STRESS=50 ./leak.exe"; check leak.twin leak.aot "leak aot 3.13 (GC stress 50)"
echo "  leak aot, no stress, PYSTACHY_GC=stats, 3,000,000 dropped: $(PYSTACHY_GC=stats ./leak.exe 3000000 2>&1 | tr '\n' ' ')"
for v in py315 py315t; do L=$L15; [ $v = py315t ] && L=$L15t
  PYSTACHY_LIBPYTHON=$L $PYS build stw.py -o stw.$v && echo "  stw aot $v: $(PYTHONHOME=$C/$v/python ./stw.$v)"
done

echo "### S3: pystachy ext, abi3 and abi3t, each client against its source run under the twin (same CPython)"
cd $R/ext
mkdir -p src a3 a3t
cp *.py src/
for m in fastmath viajson mg av reent bad_once; do
  $PYS ext $m.py -o a3/$m.abi3.so && $PYS ext $m.py --abi abi3t -o a3t/$m.abi3t.so || echo "BUILD FAILED $m"
  python3 $F/abi_check.py $TOML a3/$m.abi3.so 3.12 PyInit_$m; python3 $F/abi_check.py $TOML a3t/$m.abi3t.so 3.15 PyModExport_$m
done
for d in a3 a3t; do cp client.py client2.py use3.py cb.py pk3.py avclient.py reent_cb.py reclient.py reimp.py $d/; done
clients="client.py client2.py use3.py pk3.py reclient.py reimp.py"
for pv in "$P12 a3" "$P13 a3" "$P14 a3" "$P15 a3" "$P15 a3t" "$P15t a3t"; do
  py=${pv% *}; d=${pv#* }; ver=$($py -VV 2>&1 | cut -c1-34)
  for c in $clients "avclient.py a b" "-c 'import mg'"; do
    rm -f src/bad_once.flag $d/bad_once.flag
    (cd src && run ../o.txt "PYTHONPATH=$TW PYSTACHY_GC_STRESS=1 timeout 120 $py -W ignore $c")
    (cd $d && run ../s.txt "PYSTACHY_GC_STRESS=1 timeout 120 $py -W ignore $c")
    if [ "$c" = client.py ]; then sed 2d o.txt > o2.txt; sed 2d s.txt > s2.txt; check o2.txt s2.txt "$d $c on $ver (but its 'loaded' line)"; echo "    so: $(sed -n 2p s.txt)"
    else check o.txt s.txt "$d $c on $ver"; fi
  done
done
for py in $P13t $P14t; do echo "  abi3 on $($py -VV | cut -c1-40): $(cd a3 && $py -c 'import fastmath' 2>&1 | tail -1)"; done
echo "  abi3t on 3.15t, PYTHON_GIL=0: $(cd a3t && PYTHON_GIL=0 $P15t -c 'import fastmath' 2>&1 | tail -1)"
echo "  abi3 on 3.11 (below the floor): $(cd a3 && /usr/bin/python3.11 -c 'import fastmath' 2>&1 | tail -1)"
for b in bad_pub bad_def bad_cls bad_var bad_call; do echo "  $($PYS ext $b.py 2>&1 | tail -1)"; done
echo "### probes: $ok same, $bad different"
