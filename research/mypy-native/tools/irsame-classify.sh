#!/bin/sh
# one.sh FILE OUTDIR: compile FILE with build/ref/pystachy and ./pystachy as tools/irsame.sh does and
# print one line: SAME, or what differs (STATUS, MESSAGES, IR with the function of the first difference)
f=$1; d=$(mktemp -d "$2/w.XXXXXX") || exit 1
mp=$PYSTACHY_PATH
if [ -f "${f%.py}.path" ]; then mp=$(sh tests/prepare_path.sh "$f" "$d") || { echo "PATHFAIL $f"; exit 0; }; fi
how=ir
case $f in runtime.py | */rtmode_*.py) how=rt ;; esac
PYSTACHY_HOME= PYSTACHY_PATH=$mp build/ref/pystachy $how "$f" -o "$d/old.ll" > "$d/old.msg" 2>&1; a=$?
PYSTACHY_HOME= PYSTACHY_PATH=$mp ./pystachy $how "$f" -o "$d/new.ll" > "$d/new.msg" 2>&1; b=$?
sed 's|build/ref/lib/|lib/|g' "$d/old.msg" > "$d/old.n"
r=
[ $a = $b ] || r="$r STATUS($a->$b)"
cmp -s "$d/old.n" "$d/new.msg" || r="$r MESSAGES"
if [ -f "$d/old.ll" ] && [ -f "$d/new.ll" ]; then
  if ! cmp -s "$d/old.ll" "$d/new.ll"; then
    l=$(diff "$d/old.ll" "$d/new.ll" | sed -n '1s/^\([0-9]*\).*/\1/p')
    fn=$(head -n "${l:-0}" "$d/old.ll" | sed -n 's/^define [^@]*\(@[^(]*\)(.*/\1/p' | tail -1)
    n=$(diff "$d/old.ll" "$d/new.ll" | grep -c '^[<>]')
    i32=$(diff "$d/old.ll" "$d/new.ll" | grep -c '^> .* i32 ')
    r="$r IR($fn;lines=$n;i32=$i32)"
  fi
elif [ -f "$d/old.ll" ] || [ -f "$d/new.ll" ]; then r="$r ONE-IR"; fi
echo "${r:- SAME} $f"
rm -rf "$d"
