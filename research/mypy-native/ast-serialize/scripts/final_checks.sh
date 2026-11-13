#!/bin/sh
# Final CPython comparisons of the port with the extension, one at a time, into $S/astser/final/
S=/tmp/claude-0/-home-user-pystachy/8dfd0d3f-eb31-5d1b-8d1b-90a856e3b0b1/scratchpad
. $S/env316.sh
O=$S/astser/final
mkdir -p $O
cd /home/user/wt-astser || exit 1
run() { name=$1; shift; echo "== $name: $*" >> $O/summary.txt; timeout 7000 $PY -I tools/ast_serialize_check.py --limit 5 "$@" > $O/$name.log 2>&1; echo "exit=$?" >> $O/$name.log; grep -E "^\[|^fuzz|^parse_type_string" $O/$name.log >> $O/summary.txt; grep -c "^MISMATCH" $O/$name.log >> $O/summary.txt; }
: > $O/summary.txt
run mypy --options all $S/sweep/pkgs/mypy
run mypyc --options all $S/sweep/pkgs/mypyc
run typeshed --options all $S/venv316/lib/python3.13/site-packages/mypy/typeshed
run sitepkgs --options all $S/venv316/lib/python3.13/site-packages
run repo --options all lib src tests
run edge --options all $S/astser/edge
run lib-cpython --options all $S/py316-src/Python-3.13.16/Lib
run mypy-str --options default,cv5 --source str $S/sweep/pkgs/mypy $S/sweep/pkgs/mypyc
run mypy-bytes --options default,cv5 --source bytes $S/sweep/pkgs/mypy $S/sweep/pkgs/mypyc
run types --options default --type-strings $S/astser/edge $S/sweep/pkgs/mypy $S/sweep/pkgs/mypyc $S/py316-src/Python-3.13.16/Lib $S/venv316/lib/python3.13/site-packages
run fuzz-mypy --fuzz 4000 --seed 1 --options all $S/sweep/pkgs/mypy $S/sweep/pkgs/mypyc
run fuzz-lib --fuzz 10000 --seed 2 --options all $S/py316-src/Python-3.13.16/Lib
run fuzz-repo --fuzz 4000 --seed 3 --options all lib src tests/programs
echo "== done" >> $O/summary.txt
