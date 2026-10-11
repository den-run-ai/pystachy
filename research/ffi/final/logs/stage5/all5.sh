#!/bin/sh
# Every check on stage3/tree after the stage-4 fixes, each with its log under stage5/logs
S5=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage5
G=$S5/logs; cd "$S5/../stage3/tree" || exit 1
export PATH=/root/.local/bin:$PATH
echo "## tree: $(git rev-parse --short HEAD) on base $(git rev-parse --short base) ($(git log --oneline base..HEAD | wc -l) commits), dirty: $(git status --porcelain | wc -l) files"
echo "## make (three-stage fixed point, runtime.py's fixed point)"; rm -rf build/stage*.ll build/rt*.ll build/pystachy1 build/pystachy2 pystachy
make pystachy > $G/make.log 2>&1; echo "make exit=$?"; grep "fixed point" $G/make.log
echo "## runtime.py's IR: this compiler vs base's (build/ref)"
rm -rf build/ref; make ref REF=base > $G/ref.log 2>&1 || echo "make ref failed"
PYSTACHY_HOME= build/ref/pystachy rt runtime.py -o $G/rt-base.ll; PYSTACHY_HOME= ./pystachy rt runtime.py -o $G/rt-ffi.ll
cmp $G/rt-base.ll $G/rt-ffi.ll && echo "runtime.py IR byte-identical ($(wc -l < $G/rt-ffi.ll) lines)"; rm -f $G/rt-base.ll $G/rt-ffi.ll
echo "## check_runtime"; python3 tools/check_runtime.py > $G/check_runtime.log 2>&1; echo "exit=$?"; tail -1 $G/check_runtime.log
echo "## rtabi"; python3 tools/rtabi.py ./pystachy > $G/rtabi.log 2>&1; echo "exit=$?"; tail -2 $G/rtabi.log
echo "## tests/run.sh ./pystachy (JIT and AOT)"; tests/run.sh ./pystachy > $G/tests.log 2>&1; echo "exit=$?"; tail -1 $G/tests.log
echo "## make irsame REF=base"; make irsame REF=base > $G/irsame.log 2>&1; echo "exit=$?"; tail -1 $G/irsame.log
echo "## irsame of the files main's corpus leaves out (lib/*.py, tests/ subdirectories, the FFI tests' plain modules)"
PYSTACHY_HOME= tools/irsame.sh build/ref/pystachy ./pystachy $(ls lib/*.py tests/defmods/*.py tests/infer/*.py tests/linked/*.py tests/loader/*.py tests/mods/*.py tests/scope/*.py tests/ownffi/*.py tests/ffi/side_*.py | grep -v lib/pyobj.py) > $G/irsame-extra.log 2>&1; echo "exit=$?"; tail -1 $G/irsame-extra.log
echo "## make check-ir"; make check-ir > $G/check-ir.log 2>&1; echo "exit=$?"; tail -1 $G/check-ir.log
echo "## make lint (ruff $(ruff --version | cut -d' ' -f2), shellcheck $(shellcheck --version | sed -n 's/^version: //p'))"; make lint > $G/lint.log 2>&1; echo "exit=$?"; tail -3 $G/lint.log
C=$S5/../stage2/capi-verify
for nv in "3.13 python3" "3.12 python3.12" "3.13t $C/py313t/python/bin/python3" "3.14 $C/py314/python/bin/python3" "3.14t $C/py314t/python/bin/python3" "3.15 $C/py315/python/bin/python3" "3.15t $C/py315t/python/bin/python3" "3.11 python3.11"; do
  n=${nv%% *}; v=${nv#* }
  echo "## tests/ffi/run.sh, native compiler, PY=$n"; PY=$v tests/ffi/run.sh ./pystachy > $G/ffi-tests-$n.log 2>&1; echo "exit=$?"; tail -1 $G/ffi-tests-$n.log
done
echo "## tests/ffi/run.sh, CPython-hosted compiler (python3 -m pystachy)"
python3 -c 'import py_compile as c; c.compile("pystachy.py", doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH)'
tests/ffi/run.sh "python3 -m pystachy" > $G/ffi-tests-hosted.log 2>&1; echo "exit=$?"; tail -1 $G/ffi-tests-hosted.log
echo "## FFI probes (probe5.sh): 3.11 (below the floor), 3.12, 3.13, 3.13t, 3.14, 3.14t, 3.15, 3.15t; JIT and AOT"; sh $S5/probe5.sh $S5/../stage3/tree/pystachy > $G/probe.log 2>&1; tail -1 $G/probe.log
echo "## the stage-4 refuters' cases (refute5.sh)"; sh $S5/refute5.sh > $G/refute.log 2>&1; tail -1 $G/refute.log
echo "## UBSan trap mode (ubsan5.sh)"; sh $S5/ubsan5.sh > $G/ubsan.log 2>&1; tail -1 $G/ubsan.log; grep 'traps' $G/ubsan.log
