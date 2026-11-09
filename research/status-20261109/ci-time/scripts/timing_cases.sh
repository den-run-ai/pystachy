#!/bin/sh
# usage: timing_cases.sh CHECKOUT MODE CASE...   (runs each case once with PYSTACHY_TIMING=1)
cd "$1" || exit 1; mode=$2; shift 2
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2 PYSTACHY_PROGRAM_CACHE=0
for c; do
  p=""; [ -f "${c%.py}.path" ] && p=$(cat "${c%.py}.path")
  s=$(date +%s.%N)
  if [ "$mode" = ir ]; then
    PYSTACHY_PATH="$p" PYSTACHY_TIMING=1 ./pystachy ir "$c" -o /dev/null 2> /tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time/timing.err
  else
    PYSTACHY_PATH="$p" PYSTACHY_TIMING=1 ./pystachy run "$c" < /dev/null > /dev/null 2> /tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time/timing.err
  fi
  e=$(date +%s.%N)
  echo "== $c wall=$(echo "$e - $s" | bc)"
  grep '^pystachy-timing' /tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time/timing.err | awk -F'\t' '{printf "   %-28s %s\n", $2, $3}' | grep -E 'program\.(attempt|frontend|analysis|lower|optimize|discover|load|prepare|finalize)|driver|runtime\.frontend|llvm|codegen|link|lookup' | head -40
done
