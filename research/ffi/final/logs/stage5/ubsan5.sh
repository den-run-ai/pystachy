#!/bin/sh
# UBSan in trap mode (an extension module inside python cannot load the UBSan runtime, so every
# check traps: SIGILL) over the three directions, JIT and AOT, against the twins on CPython 3.13.
# The runtime, pyext.c and pyembed.c are compiled with the flags (the driver caches them per flags).
S3=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage3
S5=$S3/../stage5
T=$S3/tree; X=$S3/fx; U=$S5/ub; TW=$T/tools/rt_cpython; PYS=$T/pystachy
export PYSTACHY_CFLAGS='-fsanitize=undefined -fsanitize-trap=undefined'
L13=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
rm -rf "$U"; mkdir -p "$U/x" && cd "$U" || exit 1
cp "$X"/s1/zstats.py "$X"/s1/neg.py "$X"/s1/sat.py "$X"/emb/jsondemo.py "$X"/emb/fin.py "$X"/emb/finside.py "$X"/emb/leak.py "$X"/emb/uac2.py "$X"/emb/sx.py "$X"/emb/sxb.py "$X"/emb/kb.py "$X"/emb/kbside.py .
cp "$X"/ext/*.py x/
# the regression tests of the stage-4 refutation (tests/ffi): C calls, embedding, extension modules
cp "$T"/tests/ffi/c_libm.py "$T"/tests/ffi/c_lib.py "$T"/tests/ffi/py_order.py "$T"/tests/ffi/py_stdin.py "$T"/tests/ffi/py_stdin.in "$T"/tests/ffi/py_redirect.py \
  "$T"/tests/ffi/py_badstr.py "$T"/tests/ffi/py_negzero.py "$T"/tests/ffi/py_convert.py "$T"/tests/ffi/side_badstr.py "$T"/tests/ffi/side_noisy.py .
cp "$T"/tests/ffi/ext/rd.py "$T"/tests/ffi/ext/rdclient.py "$T"/tests/ffi/ext/bx.py "$T"/tests/ffi/ext/bxclient.py "$T"/tests/ffi/ext/xbad.py \
  "$T"/tests/ffi/ext/wr.py "$T"/tests/ffi/ext/wrclient.py "$T"/tests/ffi/ext/evl.py "$T"/tests/ffi/ext/evl_loop.py "$T"/tests/ffi/ext/memclient.py x/
${CC:-cc} -shared -fPIC "$T"/tests/ffi/ffitest.c -o libpystachy-ffitest.so && export LD_LIBRARY_PATH="$U"
ok=0; bad=0
tb() { sed -e '/^Traceback (most recent call last):$/,/^[^ ]/{/^[^ ]/!d;/^Traceback (most recent call last):$/d;}' "$1"; }
check() { tb "$1" > "$1.n"; tb "$2" > "$2.n"; if cmp -s "$1.n" "$2.n"; then ok=$((ok+1)); echo "SAME  $3"; else bad=$((bad+1)); echo "DIFF  $3"; diff "$1.n" "$2.n" | head -10; fi; }
run() { out=$1; shift; sh -c "$*" > "$out" 2>&1; echo "exit=$?" >> "$out"; }
for p in zstats neg sat c_libm c_lib; do
  run $p.twin "PYTHONPATH=$TW python3.13 $p.py"
  run $p.jit "PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py"; check $p.twin $p.jit "UBSan-trap $p jit"
  $PYS build $p.py -o $p.exe && run $p.aot "PYSTACHY_GC_STRESS=7 ./$p.exe"; check $p.twin $p.aot "UBSan-trap $p aot"
done
for p in jsondemo fin leak uac2 sx sxb kb py_order py_stdin py_redirect py_badstr py_negzero py_convert; do
  if [ -f $p.in ]; then i=$p.in; else i=/dev/null; fi
  run $p.twin "PYTHONPATH=$TW python3.13 $p.py < $i"
  run $p.jit "PYSTACHY_LIBPYTHON=$L13 PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py < $i"; check $p.twin $p.jit "UBSan-trap $p jit (embedded 3.13)"
  PYSTACHY_LIBPYTHON=$L13 $PYS build $p.py -o $p.exe && run $p.aot "PYTHONPATH=. PYSTACHY_GC_STRESS=7 ./$p.exe < $i"; check $p.twin $p.aot "UBSan-trap $p aot (embedded 3.13)"
done
# the instrumentation is there: the trap mode leaves ud1 (llvm.ubsantrap) instructions in the AOT executable
echo "  traps (ud1/ud2) in zstats.exe: $(objdump -d zstats.exe | grep -c -E 'ud1|ud2'), in jsondemo.exe: $(objdump -d jsondemo.exe | grep -c -E 'ud1|ud2')"
cd x || exit 1
mkdir -p src so && cp ./*.py src/ && cp ./*.py so/
for m in fastmath mg reent viajson av rd bx wr evl; do $PYS ext $m.py -o so/$m.abi3.so && rm -f so/$m.py; done
echo "  traps (ud1/ud2) in fastmath.abi3.so: $(objdump -d so/fastmath.abi3.so | grep -c -E 'ud1|ud2')"
for c in client.py client2.py reclient.py pk3.py use3.py "avclient.py a b" rdclient.py bxclient.py wrclient.py memclient.py; do
  (cd src && run ../o.txt "PYTHONPATH=$TW PYSTACHY_GC_STRESS=1 python3.13 -W ignore $c")
  (cd so && run ../s.txt "PYSTACHY_GC_STRESS=1 python3.13 -W ignore $c")
  grep -v -e '^loaded ' -e '^gil ' o.txt > o2.txt; grep -v -e '^loaded ' -e '^gil ' s.txt > s2.txt
  check o2.txt s2.txt "UBSan-trap ext client $c (abi3 on 3.13, GC stress 1)"
done
echo "### ubsan (trap mode): $ok same, $bad different"
