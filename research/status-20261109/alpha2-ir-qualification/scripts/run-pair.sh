#!/bin/sh
# usage: run-pair.sh NAME KEEP OLD NEW
# One full-corpus run of the instrumented oracle (irsame-keep.sh, the unchanged invocations of
# tools/irsame.sh) from the #1187 checkout W, comparing compiler OLD with compiler NEW (absolute or
# W-relative binary paths; each loads the lib/ and runtime.c beside it, PYSTACHY_HOME empty as
# `make irsame` sets it). KEEP must not exist: it is created empty, holds every case directory,
# and is moved to runs/NAME afterwards. W, both homes and the corpus list are inventoried before
# and after; any change fails the run.
set -u
E=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/alpha2-qual.tqelyE
W=/home/user/wt/alpha2-qual
NAME=$1 KEEP=$2 OLD=$3 NEW=$4
R=$E/q/runs/$NAME
[ ! -e "$R" ] && [ ! -e "$KEEP" ] || { echo "run-pair: $R or $KEEP exists" >&2; exit 2; }
mkdir -p "$R.meta" "$KEEP" || exit 2
L=$R.meta/log
home() { case $1 in /*) h=${1%/*} ;; */*) h=$W/${1%/*} ;; *) h=$W ;; esac; [ -f "$h/runtime.c" ] || h=$h/..; printf '%s\n' "$h"; }
OH=$(home "$OLD"); NH=$(home "$NEW")
{
  echo "run $NAME start $(date -u +%FT%TZ)"
  echo "W=$W HEAD=$(git -C "$W" rev-parse HEAD)"
  echo "OLD=$OLD home=$OH sha256=$(sha256sum < "$OH/pystachy" | cut -c1-64)"
  echo "NEW=$NEW home=$NH sha256=$(sha256sum < "$NH/pystachy" | cut -c1-64)"
  echo "KEEP=$KEEP"
  echo "corpus-list sha256=$(sha256sum < "$E/corpus-list.txt" | cut -c1-64)"
  echo "uname: $(uname -srm)"; echo "lli: $(/usr/lib/llvm-18/bin/lli --version | sed -n 's/.*LLVM version //p' | head -1)"
  git -C "$W" status --porcelain=v1 --untracked-files=all --ignored | sed 's/^/W status: /'
} > "$L"
for x in W:$W OLDHOME:$OH NEWHOME:$NH; do
  python3 -I "$E/scripts/manifest.py" "${x#*:}" "$R.meta/${x%%:*}.before.json" | sed "s/^/manifest before ${x%%:*}: /" >> "$L"
done
start=$(date +%s)
"$E/scripts/clean-env.sh" env PYSTACHY_HOME= IRSAME_ROOT="$W" IRSAME_KEEP="$KEEP" PYSTACHY_CASE_TIMES="$R.meta/times" \
  sh "$E/scripts/irsame-keep.sh" "$OLD" "$NEW" > "$R.meta/oracle.out" 2>&1
code=$?
echo "oracle exit $code after $(( $(date +%s) - start )) s; verdict: $(tail -1 "$R.meta/oracle.out")" >> "$L"
for x in W:$W OLDHOME:$OH NEWHOME:$NH; do
  python3 -I "$E/scripts/manifest.py" "${x#*:}" "$R.meta/${x%%:*}.after.json" | sed "s/^/manifest after ${x%%:*}: /" >> "$L"
  if cmp -s "$R.meta/${x%%:*}.before.json" "$R.meta/${x%%:*}.after.json"; then
    echo "integrity ${x%%:*}: unchanged" >> "$L"
  else
    echo "integrity ${x%%:*}: CHANGED" >> "$L"; code=99
  fi
done
mv "$KEEP" "$R" || code=98
python3 -I "$E/scripts/analyze.py" collect "$R" "$E/corpus-list.txt" "$R.json" >> "$L" 2>&1 || code=97
echo "run $NAME end $(date -u +%FT%TZ) status $code" >> "$L"
cat "$L"
exit $code
