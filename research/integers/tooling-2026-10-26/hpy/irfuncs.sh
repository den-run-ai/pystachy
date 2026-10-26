#!/bin/sh
# for each program: compile with OLD and NEW (shared home), list the functions whose IR differs
cd /home/user/pystachy || exit 1
OLD=$1; NEW=$2; shift 2
T=$(mktemp -d "$SP/irf.XXXXXX")
for f; do
  mp=$PYSTACHY_PATH
  if [ -f "${f%.py}.path" ]; then mp=$(sh tests/prepare_path.sh "$f" "$T") || { echo "$f: no path"; continue; }; fi
  how=ir
  case $f in runtime.py | */rtmode_*.py) how=rt ;; esac
  PYSTACHY_PATH=$mp $OLD $how "$f" -o "$T/old.ll" > /dev/null 2>&1
  PYSTACHY_PATH=$mp $NEW $how "$f" -o "$T/new.ll" > /dev/null 2>&1
  "$SP/venv/bin/python" -I "$SP/hpy/irfuncs.py" "$T/old.ll" "$T/new.ll" | sed "s|^|$f |"
done
rm -rf "$T"
