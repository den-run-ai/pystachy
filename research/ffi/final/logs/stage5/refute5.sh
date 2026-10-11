#!/bin/sh
# Re-runs the cases of the 15 blocking issues the stage-4 refuters found, on stage3/tree.
# Each native run (JIT and AOT, or the extension module) is compared with CPython running the same
# file with the twins (tools/rt_cpython), or the extension's client with the module's source.
# usage: sh refute5.sh
S5=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage5
T=$S5/../stage3/tree; TW=$T/tools/rt_cpython; PYS=$T/pystachy; F=$S5/fx5; RI=$S5/ri
C=$S5/../stage2/capi-verify
SYS=/usr/lib/x86_64-linux-gnu
L12=$SYS/libpython3.12.so.1.0; L13=$SYS/libpython3.13.so.1.0
H14=$(cd "$C/py314/python" && pwd); L14=$H14/lib/libpython3.14.so.1.0
W=$S5/r5; rm -rf "$W"; mkdir -p "$W"
ok=0; bad=0; dev=0
deviation() { if [ "$1" = "$2" ]; then dev=$((dev+1)); echo "DEV   $3 (documented deviation, observed as documented): $1"; else bad=$((bad+1)); echo "DIFF  $3: the documented deviation is '$2', got '$1'"; fi; }
tb() { sed -e '/^Traceback (most recent call last):$/,/^[^ ]/{/^[^ ]/!d;/^Traceback (most recent call last):$/d;}' "$1"; }
check() { tb "$1" > "$1.n"; tb "$2" > "$2.n"; if cmp -s "$1.n" "$2.n"; then ok=$((ok+1)); echo "SAME  $3"; else bad=$((bad+1)); echo "DIFF  $3"; diff "$1.n" "$2.n" | head -8; fi; }
expect() { case "$1" in $2) ok=$((ok+1)); echo "SAME  $3: $1" ;; *) bad=$((bad+1)); echo "DIFF  $3: want '$2', got '$1'" ;; esac; }
run() { out=$1; shift; sh -c "$*" > "$out" 2>&1; echo "exit=$?" >> "$out"; }
# tri DIR FILE LIB [ENV]: the twin, then JIT and AOT (embedding LIB if given), each compared with the twin
tri() {
  d=$1; f=$2; lib=$3; env=$4; n=$(basename "$f" .py)
  cd "$d" || return
  run "$W/$n.tw" "$env PYTHONPATH=$TW python3 $f"
  run "$W/$n.jit" "$env PYSTACHY_LIBPYTHON=$lib PYSTACHY_GC_STRESS_PROGRAM=3 $PYS run $f"; check "$W/$n.tw" "$W/$n.jit" "$n jit"
  if PYSTACHY_LIBPYTHON=$lib $PYS build "$f" -o "$W/$n.exe" 2> "$W/$n.berr"; then
    run "$W/$n.aot" "$env PYTHONPATH=. PYSTACHY_GC_STRESS=3 $W/$n.exe"; check "$W/$n.tw" "$W/$n.aot" "$n aot"
  else bad=$((bad+1)); echo "DIFF  $n aot: build failed: $(cat "$W/$n.berr")"; fi
}
# rejected FILE: a file:line compile-time error, which the contract allows in place of the twin's run
rejected() {
  m=$($PYS ir "$1" -o /dev/null 2>&1); s=$?
  case "$s:$m" in "1:$1:"[0-9]*": error: "*) ok=$((ok+1)); echo "SAME  rejected at compile time: $m" ;; *) bad=$((bad+1)); echo "DIFF  $1: want a file:line error, got status $s: $m" ;; esac
}
# extcase DIR MODULES CLIENT [ENV]: the client against the modules' source with the twins, and against them compiled
extcase() {
  d=$1; mods=$2; cl=$3; env=$4
  rm -rf "$W/src" "$W/so"; mkdir -p "$W/src" "$W/so"
  cp "$d"/*.py "$W/src/"; cp "$d"/*.py "$W/so/"
  for m in $mods; do $PYS ext "$d/$m.py" -o "$W/so/$m.abi3.so" || { bad=$((bad+1)); echo "DIFF  ext build $m"; }; rm -f "$W/so/$m.py"; done
  (cd "$W/src" && run ../o.txt "$env PYTHONPATH=$TW python3 -W ignore $cl")
  (cd "$W/so" && run ../s.txt "$env PYSTACHY_GC_STRESS=1 python3 -W ignore $cl")
  check "$W/o.txt" "$W/s.txt" "ext $cl ($mods)"
}

echo "### 1 (invariants) -0.0 through @extern and pyobj.of_float"
tri "$F/inv" e13_negzero.py ""
tri "$F/inv" e14_pyneg0.py "$L13"
echo "### 2, 13 (invariants, recommendation) JIT: lli's libraries must not stand in for the library an @extern names, or an extension module links"
tri "$F/shadow" p.py ""
tri "$F/collide" collide.py ""
tri "$F/inv" e20_rl.py "$L13"
tri "$F/rec" rl2.py "$L13"
echo "### 3 (invariants) no segfault: Object() made by a program, an exception whose str() raises"
cd "$F/inv" && rejected e11_ctor.py
tri "$F/inv" e16_badstr.py "$L13"
echo "### 4 (invariants) only what the twins offer: ffi internals, pyobj internals; @extern keywords and defaults; to_float"
cd "$F/inv" && rejected e2_track.py && rejected e12_internal.py
tri "$F/inv" e1_kw.py ""
tri "$F/inv" e7_default.py ""
tri "$F/inv" e3_tofloat.py "$L13"
rm -rf "$W/m1"; mkdir -p "$W/m1/src" "$W/m1/so"; cp "$F"/ext/m1.py "$F"/ext/c1.py "$W/m1/src/"; cp "$F"/ext/c1.py "$W/m1/so/"
$PYS ext "$F/ext/m1.py" -o "$W/m1/so/m1.abi3.so"
deviation "$(cd "$W/m1/src" && PYTHONPATH=$TW python3 c1.py 2>&1 | grep -v -e '^ ' -e '^Traceback' | tr '\n' ' ') / $(cd "$W/m1/so" && python3 c1.py 2>&1 | grep -v -e '^ ' -e '^Traceback' | tr '\n' ' ')" "caught _Bad ('init failed',) m1._Bad: init failed  / caught ValueError ('init failed',) ValueError: init failed " "an exception raised by an extension module's code at import leaves as its nearest builtin class"
echo "### 5, 11 (invariants, interop) one order of output, one stdin: embedding and extension modules"
tri "$F/inv" e4_importprint.py "$L13"
cd "$F/inv" && printf 'a\nb\n' > "$W/ab.txt" && tri "$F/inv" e10_stdin.py "$L13" "< $W/ab.txt"
tri "$RI/e1" order.py "$L13"
printf 'a\nb\nc\n' > "$W/abc.txt"; tri "$RI/e1" stdin2.py "$L13" "< $W/abc.txt"
extcase "$F/ext" m2 c2.py
printf 'one\ntwo\nthree\nfour\n' > "$W/in4.txt"; extcase "$RI/x2/src" rd rdclient.py "< $W/in4.txt"
extcase "$RI/x2/src" rd none.py
echo "### 6, 7, 15 (invariants, interop, recommendation) dropped large Python objects: peak RSS (MiB) bounded, twin vs native"
rss() { python3 "$S5/maxrss.py" "$*"; }
cd "$F/inv" && PYSTACHY_LIBPYTHON=$L13 $PYS build e21_big.py -o "$W/e21.exe" && a=$(rss "PYTHONPATH=$TW python3 e21_big.py") && b=$(rss "$W/e21.exe")
expect "$((b / 1024 <= a / 1024 + 96))" 1 "e21_big (300 x 10 MB bytearrays): twin $((a / 1024)) MiB, AOT $((b / 1024)) MiB (bound: twin + 96)"
cd "$F/rec" && PYSTACHY_LIBPYTHON=$L13 $PYS build big.py -o "$W/big.exe" && a=$(rss "PYTHONPATH=$TW python3 big.py") && b=$(rss "$W/big.exe")
expect "$((b / 1024 <= a / 1024 + 96))" 1 "interpose/big (3000 x 1 MiB): twin $((a / 1024)) MiB, AOT $((b / 1024)) MiB"
cd "$RI/e1" && PYSTACHY_LIBPYTHON=$L13 $PYS build big.py -o "$W/big2.exe" && a=$(rss "PYTHONPATH=$TW python3 big.py") && b=$(rss "$W/big2.exe")
expect "$((b / 1024 <= a / 1024 + 96))" 1 "refute-interop e1/big (1500 x 1 MiB): twin $((a / 1024)) MiB, AOT $((b / 1024)) MiB"
rm -rf "$W/x1"; mkdir -p "$W/x1/src" "$W/x1/so"; cp "$RI"/x1/src/*.py "$W/x1/src/"; cp "$RI"/x1/src/evl_client.py "$RI"/x1/src/evl_loop.py "$W/x1/so/"
$PYS ext "$RI/x1/src/evl.py" -o "$W/x1/so/evl.abi3.so"
a=$(cd "$W/x1/src" && rss "PYTHONPATH=$TW python3 evl_client.py 1000"); b=$(cd "$W/x1/so" && rss "python3 evl_client.py 1000")
expect "$((b / 1024 <= a / 1024 + 96))" 1 "x1 nested callbacks (1000 x 1 MiB inside one outer call): source $((a / 1024)) MiB, ext $((b / 1024)) MiB"
b=$(cd "$W/x1/so" && rss "PYSTACHY_GC_STRESS=1 python3 evl_client.py 1000")
expect "$((b / 1024 <= a / 1024 + 96))" 1 "x1 nested callbacks, GC stress 1: ext $((b / 1024)) MiB"
echo "### 8 (interop) an extension module's Python objects released at the host's exit (atexit)"
for c in wr lg; do
  rm -rf "$W/x4"; mkdir -p "$W/x4/src" "$W/x4/so"; cp "$RI"/x4/src/$c.py "$RI"/x4/src/${c}client.py "$W/x4/src/"; cp "$RI"/x4/src/${c}client.py "$W/x4/so/"
  $PYS ext "$RI/x4/src/$c.py" -o "$W/x4/so/$c.abi3.so"
  f=a.txt; [ $c = lg ] && f=log.txt
  (cd "$W/x4/src" && PYTHONPATH=$TW python3 ${c}client.py > out.txt 2>&1; cat $f) > "$W/x4.o"
  (cd "$W/x4/so" && python3 ${c}client.py > out.txt 2>&1; cat $f) > "$W/x4.s"
  check "$W/x4.o" "$W/x4.s" "x4 $c: the file's contents after the host exits"
  [ $c = wr ] && deviation "$(cat "$W/x4/src/out.txt") / $(cat "$W/x4/so/out.txt")" "a.txt right after save: 'hello\n' / a.txt right after save: ''" "x4 wr: a file written through a dropped Object is flushed when the Object is released (release timing)"
done
echo "### 9, 14 (interop, recommendation) embedded CPython as python3 sets it up: C locale, sys.executable, multiprocessing"
tri "$RI/e1" loc.py "$L13" "LC_ALL= LANG= LC_CTYPE="
tri "$RI/e1" loc.py "$L12" "LC_ALL=C"
cd "$RI/e1" || exit 1
for v in "3.12 python3.12 $L12" "3.13 python3.13 $L13"; do
  set -- $v
  run "$W/exe$1.tw" "PYTHONPATH=$TW $2 exe.py"
  PYSTACHY_LIBPYTHON=$3 $PYS build exe.py -o "$W/exe$1.exe" && run "$W/exe$1.aot" "$W/exe$1.exe"; check "$W/exe$1.tw" "$W/exe$1.aot" "exe.py: a child run with sys.executable, embedded $1 (aot)"
  run "$W/exe$1.jit" "PYSTACHY_LIBPYTHON=$3 $PYS run exe.py"; check "$W/exe$1.tw" "$W/exe$1.jit" "exe.py, embedded $1 (jit)"
done
cd "$F/rec" || exit 1
run "$W/pool14.tw" "PYTHONPATH=$TW $H14/bin/python3 pool.py"
PYSTACHY_LIBPYTHON=$L14 $PYS build pool.py -o "$W/pool14.exe" && run "$W/pool14.aot" "PYTHONHOME=$H14 timeout 60 $W/pool14.exe"; check "$W/pool14.tw" "$W/pool14.aot" "pool.py: multiprocessing (forkserver), embedded 3.14 (aot)"
run "$W/pool14.jit" "PYTHONHOME=$H14 PYSTACHY_LIBPYTHON=$L14 timeout 60 $PYS run pool.py"; check "$W/pool14.tw" "$W/pool14.jit" "pool.py, embedded 3.14 (jit)"
run "$W/pool14n.aot" "timeout 60 $W/pool14.exe"; check "$W/pool14.tw" "$W/pool14n.aot" "pool.py, embedded 3.14 without PYTHONHOME (aot)"
cd "$RI/e1" || exit 1
run "$W/mp14.tw" "PYTHONPATH=$TW timeout 60 $H14/bin/python3 mp.py"
PYSTACHY_LIBPYTHON=$L14 $PYS build mp.py -o "$W/mp14.exe" && run "$W/mp14.aot" "PYTHONHOME=$H14 timeout 60 $W/mp14.exe"; check "$W/mp14.tw" "$W/mp14.aot" "mp.py: Pool(2) map, embedded 3.14 (aot)"
cd "$F/rec" && PYSTACHY_LIBPYTHON=$L13 $PYS build exe.py -o "$W/recexe.exe"
expect "$(PYTHONPATH=$TW python3 exe.py | sed -n 1p) / $("$W/recexe.exe" | sed -n 1p) / $(PATH=/nonexistent "$W/recexe.exe" | sed -n 1p)" "exe /usr/bin/python3 / exe /usr/bin/python3 / exe /usr/bin/python3" "sys.executable: twin (python3) / AOT 3.13 / AOT 3.13 with PATH=/nonexistent"
PYSTACHY_LIBPYTHON=$L14 $PYS build exe.py -o "$W/recexe14.exe"
expect "$(PYTHONPATH=$TW $H14/bin/python3 exe.py | sed -n 1p) / $(PYTHONHOME=$H14 "$W/recexe14.exe" | sed -n 1p)" "exe $H14/bin/python3 / exe $H14/bin/python3" "sys.executable: twin 3.14 / AOT embedding 3.14"
echo "### 10 (interop) Python's setlocale does not change Pystachy's float text (de_DE.UTF-8 from LOCPATH)"
extcase "$RI/x4/src" fm2 fm2client.py "LANG=de_DE.UTF-8 LOCPATH=$RI/locales"
extcase "$RI/x4/src" fm fmclient.py "LOCPATH=$RI/locales"
tri "$RI/e2" fe2.py "$L13" "LOCPATH=$RI/locales"
echo "### 12 (interop) unchecked NULLs: a str() that raises, a non-UTF-8 argument"
tri "$RI/e1" bs1.py "$L13"
cd "$RI/e2" || exit 1
arg=$(printf 'caf\351')
run "$W/av.tw" "PYTHONPATH=$TW python3 av.py ok '$arg'"
PYSTACHY_LIBPYTHON=$L13 $PYS build av.py -o "$W/av.exe" && run "$W/av.aot" "$W/av.exe ok '$arg'"
sed -i 's|"/tmp[^"]*/av.exe"|"av.py"|; s|\["[^"]*av.exe"|["av.py"|' "$W/av.aot"; check "$W/av.tw" "$W/av.aot" "av.py with a non-UTF-8 argument (aot; argv[0] named as the twin's)"
run "$W/av.jit" "PYSTACHY_LIBPYTHON=$L13 $PYS run av.py ok '$arg'"; check "$W/av.tw" "$W/av.jit" "av.py with a non-UTF-8 argument (jit)"
extcase "$RI/x6/src" bx bxclient.py
echo "### refute5: $ok same, $bad different; $dev documented deviations observed as documented"
