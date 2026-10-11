#!/bin/sh
# FFI probes on the rebased tree (stage3/tree). Usage: probe.sh COMPILER-CMD
# Every comparison is native output against the same file run by CPython with the twins
# (tools/rt_cpython on PYTHONPATH), on the same CPython version; an extension module's client is
# compared with the same client run against the module's source (with the twins).
# Compared: stdout and stderr together and the exit status, with CPython's traceback cut to its
# last line (Pystachy prints only that line: docs/language.md, "An exception that nothing catches").
S3=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage3
S5=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage5
C=$S3/../stage2/capi-verify
T=$S3/tree; X=$S3/fx; R=$S5/run; PYS="$1"; TW=$T/tools/rt_cpython
TOML=$C/stable_abi_3150.toml
SYS=/usr/lib/x86_64-linux-gnu
P11=/usr/bin/python3.11; L11=$SYS/libpython3.11.so.1.0
# version name, python, libpython, PYTHONHOME for embedding ("" for the system's)
VERSIONS="3.12 3.13 3.13t 3.14 3.14t 3.15 3.15t"
py_of() { case $1 in 3.12) echo /usr/bin/python3.12 ;; 3.13) echo /usr/bin/python3.13 ;; 3.13t) echo $C/py313t/python/bin/python3 ;;
  3.14) echo $C/py314/python/bin/python3 ;; 3.14t) echo $C/py314t/python/bin/python3 ;; 3.15) echo $C/py315/python/bin/python3 ;; 3.15t) echo $C/py315t/python/bin/python3 ;; esac; }
lib_of() { case $1 in 3.12) echo $SYS/libpython3.12.so.1.0 ;; 3.13) echo $SYS/libpython3.13.so.1.0 ;; 3.13t) echo $C/py313t/python/lib/libpython3.13t.so.1.0 ;;
  3.14) echo $C/py314/python/lib/libpython3.14.so.1.0 ;; 3.14t) echo $C/py314t/python/lib/libpython3.14t.so.1.0 ;; 3.15) echo $C/py315/python/lib/libpython3.15.so.1.0 ;;
  3.15t) echo $C/py315t/python/lib/libpython3.15t.so.1.0 ;; esac; }
home_of() { case $1 in 3.12 | 3.13) echo "" ;; 3.13t) echo $C/py313t/python ;; 3.14) echo $C/py314/python ;; 3.14t) echo $C/py314t/python ;; 3.15) echo $C/py315/python ;; 3.15t) echo $C/py315t/python ;; esac; }
rm -rf "$R"; mkdir -p "$R" && cp -r "$X"/s1 "$X"/loc "$X"/emb "$X"/ext "$R"/
ok=0; bad=0; dev=0
tb() { sed -e '/^Traceback (most recent call last):$/,/^[^ ]/{/^[^ ]/!d;/^Traceback (most recent call last):$/d;}' "$1"; }
check() { tb "$1" > "$1.n"; tb "$2" > "$2.n"; if cmp -s "$1.n" "$2.n"; then ok=$((ok+1)); echo "SAME  $3"; else bad=$((bad+1)); echo "DIFF  $3"; diff "$1.n" "$2.n" | head -10; fi; }
expect() { if [ "$1" = "$2" ]; then ok=$((ok+1)); echo "SAME  $3: $1"; else bad=$((bad+1)); echo "DIFF  $3: want '$2', got '$1'"; fi; }
deviation() { if [ "$1" = "$2" ]; then dev=$((dev+1)); echo "DEV   $3 (documented deviation, observed as documented): $1"; else bad=$((bad+1)); echo "DIFF  $3: the documented deviation is '$2', got '$1'"; fi; }
run() { out=$1; shift; sh -c "$*" > "$out" 2>&1; echo "exit=$?" >> "$out"; }

echo "### S1: @extern, Pystachy calls C (twin on 3.13 vs JIT vs AOT, GC stress 7)"
cd "$R/s1" || exit 1
for p in zstats sat neg ok_rt; do
  run $p.twin "PYTHONPATH=$TW python3.13 $p.py"
  run $p.jit "PYSTACHY_GC_STRESS_PROGRAM=7 $PYS run $p.py"; check $p.twin $p.jit "$p jit"
  $PYS build $p.py -o $p.exe && run $p.aot "PYSTACHY_GC_STRESS=7 ./$p.exe"; check $p.twin $p.aot "$p aot"
done
for f in e_int e_dup e_res e_rt e_list e_bool e_body; do
  m=$($PYS run $f.py 2>&1); s=$?
  case "$s:$m" in "1:$f.py:"[0-9]*": error: "*) ok=$((ok+1)); echo "SAME  rejected: $m" ;; *) bad=$((bad+1)); echo "DIFF  $f.py: want a file:line error, got status $s: $m" ;; esac
done
# documented deviations: "" is the process's own C library, and lli's process has more in it; a C string
# that is not UTF-8 is read as it is (the twin's decode raises UnicodeDecodeError)
$PYS build zv.py -o zv.exe
deviation "$($PYS run zv.py 2>&1 | tail -1) / $(./zv.exe 2>&1 | tail -1) / $(PYTHONPATH=$TW python3.13 zv.py 2>&1 | tail -1)" "1. / AttributeError: ./zv.exe: undefined symbol: zlibVersion / 1." "@extern(\"\") zlibVersion: JIT finds it in lli's process / an AOT build's process has no libz / python3 links libz"
deviation "$(FFI_PROBE_TEXT=$(printf 'caf\351') $PYS run nonutf8.py 2>&1) / $(FFI_PROBE_TEXT=$(printf 'caf\351') PYTHONPATH=$TW python3.13 nonutf8.py 2>&1 | tail -1 | cut -d: -f1)" "4 False / UnicodeDecodeError" "a C string that is not UTF-8: native / twin"
run nonutf8.twin "FFI_PROBE_TEXT=cafe PYTHONPATH=$TW python3.13 nonutf8.py"; run nonutf8.jit "FFI_PROBE_TEXT=cafe $PYS run nonutf8.py"; check nonutf8.twin nonutf8.jit "a C string that is ASCII (jit)"
cd "$R/loc" || exit 1
run m.cpy "python3.13 m.py"; run m.jit "$PYS run m.py"; check m.cpy m.jit "a program's own ffi.py (jit)"
$PYS build m.py -o m.exe && run m.aot "./m.exe"; check m.cpy m.aot "a program's own ffi.py (aot)"
m=$(PYSTACHY_LIBPYTHON=$(lib_of 3.13) $PYS run pm.py 2>&1)
case $m in *"/lib/pyobj.py:"[0-9]*": error: module 'pyobj' needs Pystachy's builtin ffi module, which the program's own ./ffi.py replaces: rename that module") ok=$((ok+1)); echo "SAME  own ffi.py + pyobj, rejected: $m" ;; *) bad=$((bad+1)); echo "DIFF  own ffi.py + pyobj: $m" ;; esac

echo "### S2: lib/pyobj.py, Pystachy calls CPython (embedded), each against the twin on the same CPython"
cd "$R/emb" || exit 1
for v in $VERSIONS; do
  py=$(py_of $v); L=$(lib_of $v); H=$(home_of $v); E="PYSTACHY_LIBPYTHON=$L${H:+ PYTHONHOME=$H}"
  for p in jsondemo uac uac2 sx sxb fin kb; do
    run $p.t$v "PYTHONPATH=$TW $py $p.py"
    run $p.j$v "$E PYSTACHY_GC_STRESS_PROGRAM=3 $PYS run $p.py"; check $p.t$v $p.j$v "$p jit $v (GC stress 3)"
    env PYSTACHY_LIBPYTHON="$L" $PYS build $p.py -o $p.e$v && run $p.a$v "${H:+PYTHONHOME=$H }PYSTACHY_GC_STRESS=3 ./$p.e$v"; check $p.t$v $p.a$v "$p aot $v (GC stress 3)"
  done
  run leak.t$v "PYTHONPATH=$TW $py leak.py"
  run leak.j$v "$E PYSTACHY_GC_STRESS_PROGRAM=50 $PYS run leak.py"; check leak.t$v leak.j$v "leak jit $v (GC stress 50)"
  env PYSTACHY_LIBPYTHON="$L" $PYS build leak.py -o leak.e$v && run leak.a$v "${H:+PYTHONHOME=$H }PYSTACHY_GC_STRESS=50 ./leak.e$v"; check leak.t$v leak.a$v "leak aot $v (GC stress 50)"
  env PYSTACHY_LIBPYTHON="$L" $PYS build stw.py -o stw.e$v && echo "  stw aot $v (no stress): $(env ${H:+PYTHONHOME=$H} ./stw.e$v 2>&1 | tr '\n' ' ')"
done
echo "  leak aot 3.13, no stress, PYSTACHY_GC=stats, 3,000,000 dropped: $(PYSTACHY_GC=stats ./leak.e3.13 3000000 2>&1 | tr '\n' ' ')"
m=$(PYSTACHY_LIBPYTHON=$L11 $PYS run jsondemo.py 2>&1); s=$?
expect "$s: $m" "1: jsondemo.py:0: error: the program embeds CPython (it imports pyobj), which needs CPython 3.12 or later: PYSTACHY_LIBPYTHON is CPython 3.11's ($L11)" "embedding libpython 3.11 (below the floor), jit"
m=$(PYSTACHY_LIBPYTHON=$L11 $PYS build jsondemo.py -o j11.exe 2>&1); s=$?
expect "$s: $m" "1: jsondemo.py:0: error: the program embeds CPython (it imports pyobj), which needs CPython 3.12 or later: PYSTACHY_LIBPYTHON is CPython 3.11's ($L11)" "embedding libpython 3.11 (below the floor), aot"

echo "### S3: pystachy ext, CPython calls Pystachy: abi3 and abi3t, each client against its source run with the twins (same CPython)"
cd "$R/ext" || exit 1
mkdir -p src a3 a3t
cp ./*.py src/
for m in fastmath viajson mg av reent bad_once; do
  $PYS ext $m.py -o a3/$m.abi3.so && $PYS ext $m.py --abi abi3t -o a3t/$m.abi3t.so || { bad=$((bad+1)); echo "DIFF  BUILD FAILED $m"; }
  for x in "a3/$m.abi3.so 3.12 PyInit_$m" "a3t/$m.abi3t.so 3.15 PyModExport_$m"; do
    # shellcheck disable=SC2086
    if r=$(sh "$T/tools/abi_check.sh" "$TOML" $x 2>&1); then ok=$((ok+1)); echo "SAME  abi_check: $r"; else bad=$((bad+1)); echo "DIFF  abi_check: $r"; fi
  done
done
for d in a3 a3t; do cp client.py client2.py use3.py cb.py pk3.py avclient.py reent_cb.py reclient.py reimp.py which.py $d/; done
clients="client.py client2.py use3.py pk3.py reclient.py reimp.py"
for pv in "3.12 a3" "3.13 a3" "3.14 a3" "3.15 a3" "3.15 a3t" "3.15t a3t"; do
  v=${pv% *}; d=${pv#* }; py=$(py_of "$v")
  expect "$(cd $d && $py which.py 2>&1 | tail -1)" "loaded from ['$(if [ $d = a3 ]; then echo abi3; else echo abi3t; fi)']" "$d on $v: the modules load from the extension"
  for c in $clients "avclient.py a b" "-c 'import mg'"; do
    rm -f src/bad_once.flag $d/bad_once.flag
    (cd src && run ../o.txt "PYTHONPATH=$TW PYSTACHY_GC_STRESS=1 timeout 120 $py -W ignore $c")
    (cd $d && run ../s.txt "PYSTACHY_GC_STRESS=1 timeout 120 $py -W ignore $c")
    if [ "$c" = client.py ]; then
      # the client's 'loaded' line names the file it loaded, and its 'gil' line differs on 3.15t by design
      grep -v -e '^loaded ' -e '^gil ' o.txt > o2.txt; grep -v -e '^loaded ' -e '^gil ' s.txt > s2.txt
      check o2.txt s2.txt "$d $c on $v (but its 'loaded' and 'gil' lines)"
      if [ "$v" = 3.15t ]; then
        deviation "$(grep '^gil ' o.txt) / $(grep '^gil ' s.txt) / $(grep -c 'The global interpreter lock (GIL) has been enabled to load m' s.txt)" "gil False / gil True / 1" "$d on 3.15t: the extension turns the GIL on, with a RuntimeWarning"
      else
        expect "$(grep '^gil ' s.txt)" "$(grep '^gil ' o.txt)" "$d $c on $v, its 'gil' line"
      fi
    else check o.txt s.txt "$d $c on $v"; fi
  done
done
for v in 3.13t 3.14t; do
  expect "$(cd a3 && $(py_of $v) -c 'import fastmath' 2>&1 | tail -1)" "ImportError: fastmath.abi3.so is built for CPython's GIL builds (abi3): on a free-threaded build, use the abi3t module (CPython 3.15+) or the source" "abi3 on $v"
  expect "$(cd a3t && $(py_of $v) -c 'import fastmath' 2>&1 | tail -1)" "ModuleNotFoundError: No module named 'fastmath'" "abi3t on $v (it loads no .abi3t.so)"
done
expect "$(cd a3t && PYTHON_GIL=0 $(py_of 3.15t) -c 'import fastmath' 2>&1 | tail -1)" "ImportError: a Pystachy extension module needs the GIL (its runtime is single-threaded), which PYTHON_GIL=0 or -X gil=0 keeps off" "abi3t on 3.15t, PYTHON_GIL=0"
expect "$(cd a3 && $P11 -c 'import fastmath' 2>&1 | tail -1 | sed 's|: /.*/a3/|: |')" "ImportError: fastmath.abi3.so: undefined symbol: PyErr_GetRaisedException" "abi3 on 3.11 (below the floor): ImportError from the dynamic loader"
for b in bad_pub bad_def bad_cls bad_var bad_call; do
  m=$($PYS ext $b.py 2>&1); s=$?
  case "$s:$m" in "1:$b.py:"[0-9]*": error: "*) ok=$((ok+1)); echo "SAME  rejected: $m" ;; *) bad=$((bad+1)); echo "DIFF  $b.py: want a file:line error, got status $s: $m" ;; esac
done
echo "### probes: $ok same, $bad different; $dev documented deviations observed as documented"
