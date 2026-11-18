#!/bin/sh
# irsame-metadata-only.sh FILE OUTDIR: of FILE's IR from build/ref/pystachy and ./pystachy (as
# tools/irsame.sh compiles it), whether the two differ only in metadata: the !tbaa and !range
# attachments of loads and stores and the metadata nodes (lines that start with "!"), with the
# reference compiler's library path (build/ref/lib/) taken as lib/. Prints "SAME", "METADATA" or
# "CODE n" (n: lines that differ once metadata is stripped), then FILE
f=$1; d=$(mktemp -d "$2/w.XXXXXX") || exit 1
mp=$PYSTACHY_PATH
if [ -f "${f%.py}.path" ]; then mp=$(sh tests/prepare_path.sh "$f" "$d") || { echo "PATHFAIL $f"; exit 0; }; fi
how=ir
case $f in runtime.py | */rtmode_*.py) how=rt ;; esac
PYSTACHY_HOME= PYSTACHY_PATH=$mp build/ref/pystachy $how "$f" -o "$d/old.ll" > /dev/null 2>&1
PYSTACHY_HOME= PYSTACHY_PATH=$mp ./pystachy $how "$f" -o "$d/new.ll" > /dev/null 2>&1
if [ ! -f "$d/old.ll" ] || [ ! -f "$d/new.ll" ]; then echo "NOIR $f"; rm -rf "$d"; exit 0; fi
strip() { sed -e 's|build/ref/lib/|lib/|g' -e 's/, !tbaa ![0-9]*//g' -e 's/, !range ![0-9]*//g' -e '/^![0-9]* = /d' "$1"; }
if cmp -s "$d/old.ll" "$d/new.ll" || [ "$(sed 's|build/ref/lib/|lib/|g' "$d/old.ll" | cmp -s - "$d/new.ll"; echo $?)" = 0 ]; then echo "SAME $f"
else
  strip "$d/old.ll" > "$d/o" ; strip "$d/new.ll" > "$d/n"
  n=$(diff "$d/o" "$d/n" | grep -c '^[<>]')
  if [ "$n" = 0 ]; then echo "METADATA $f"; else echo "CODE $n $f"; fi
fi
rm -rf "$d"
