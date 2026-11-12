#!/bin/bash
# usage: run_corpus.sh LISTFILE OUTDIR  -- AOT-builds each program with inline remarks logged
A=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad/aot
W=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad/llvmwrap
mkdir -p "$2"
while read -r f; do
  n=$(echo "$f" | tr '/' '_')
  PYSTACHY_LLVM=$W PYSTACHY_CACHE=$2/../cache PYSTACHY_PROGRAM_CACHE=0 timeout 120 "$A/pystachy" build "$A/$f" -o "$2/$n.exe" > /dev/null 2> "$2/$n.err"
  echo "$? $f" >> "$2/status"
  rm -f "$2/$n.exe"
done < "$1"
