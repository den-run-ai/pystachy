#!/bin/sh
# usage: run-subset.sh NAME: rerun the subset (subset-list.txt) in the official layout with the
# instrumented oracle, keeping outputs, then compare each case's outputs with run O2's.
set -u
E=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/alpha2-qual.tqelyE
W=/home/user/wt/alpha2-qual
R=$E/q/runs/$1
[ ! -e "$R" ] || exit 2
mkdir -p "$R"
start=$(date +%s)
"$E/scripts/clean-env.sh" env PYSTACHY_HOME= IRSAME_ROOT="$W" IRSAME_KEEP="$R" \
  sh "$E/scripts/irsame-keep.sh" build/ref/pystachy ./pystachy $(cat "$E/subset-list.txt") > "$R.oracle.out" 2>&1
echo "$1: oracle exit $? after $(( $(date +%s) - start )) s; verdict: $(tail -1 "$R.oracle.out")"
python3 -I "$E/scripts/analyze.py" collect "$R" "$E/subset-list.txt" "$R.json"
