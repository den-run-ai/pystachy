#!/bin/bash
# usage: probe.sh [-a] file.py ...   compare CPython 3.13 with pystachy JIT (and AOT with -a)
ROOT=${PYSTACHY_REPO:?set PYSTACHY_REPO to the checkout that holds ./pystachy}
SP=${TMPDIR:-/tmp}
AOT=0
if [ "$1" = "-a" ]; then AOT=1; shift; fi
for f in "$@"; do
  d=$(dirname "$f"); b=$(basename "$f" .py)
  inf=/dev/null; [ -f "$d/$b.in" ] && inf="$d/$b.in"
  exp_out=$(cd "$d" && timeout 60 python3.13 "$b.py" 2>"$SP/.exp_err" <"$inf"; echo "status=$?")
  exp_err=$(tail -n 1 "$SP/.exp_err")
  got_out=$(cd "$d" && timeout 120 $ROOT/pystachy run "$b.py" 2>"$SP/.got_err" <"$inf"; echo "status=$?")
  got_err=$(tail -n 1 "$SP/.got_err")
  if [ "$exp_out" == "$got_out" ] && [ "$exp_err" == "$got_err" ]; then
    echo "OK   $f"
  else
    echo "DIFF $f"
    diff <(echo "$exp_out"; echo "ERR: $exp_err") <(echo "$got_out"; echo "ERR: $got_err") | head -${DIFFLINES:-30}
  fi
  if [ $AOT = 1 ]; then
    if (cd "$d" && timeout 300 $ROOT/pystachy build "$b.py" -o "$SP/.aot_$b" 2>"$SP/.aot_err"); then
      aot_out=$(cd "$d" && timeout 120 "$SP/.aot_$b" 2>"$SP/.got_err2" <"$inf"; echo "status=$?")
      aot_err=$(tail -n 1 "$SP/.got_err2")
      if [ "$exp_out" != "$aot_out" ] || [ "$exp_err" != "$aot_err" ]; then
        echo "DIFF-AOT $f"
        diff <(echo "$exp_out"; echo "ERR: $exp_err") <(echo "$aot_out"; echo "ERR: $aot_err") | head -${DIFFLINES:-30}
      fi
      rm -f "$SP/.aot_$b"
    else
      echo "AOT-BUILD-FAIL $f: $(tail -n 2 $SP/.aot_err)"
    fi
  fi
done
