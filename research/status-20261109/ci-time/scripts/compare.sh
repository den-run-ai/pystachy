#!/bin/sh
# Old (d93f853f) vs new (ce8c887) compiler on fixed inputs; each tree uses its own lib/.
#  1. self IR (frontend only), three times each: old-on-old, new-on-new, new-on-old source
#  2. sample cases: `ir` time and IR line count with each compiler on its own tree, interleaved
# Output: TSV lines on stdout.
S=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time
OLD=$S/old
NEW=/home/user/wt/ci-time
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2 PYSTACHY_PROGRAM_CACHE=0
T=$(mktemp -d "$S/cmp.XXXXXX")
now() { date +%s.%N; }
# timed DIR COMPILER ARGS... : run in DIR, print elapsed seconds
timed() { d=$1; shift; s=$(now); (cd "$d" && "$@") > /dev/null 2> "$T/err"; st=$?; e=$(now); echo "$(echo "$e - $s" | bc) $st"; }
for i in 1 2 3; do
  echo "self	old-on-old	$i	$(timed "$OLD" "$OLD/pystachy" ir pystachy.py -o "$T/o.ll")"
  echo "self	new-on-new	$i	$(timed "$NEW" "$NEW/pystachy" ir pystachy.py -o "$T/n.ll")"
  echo "self	new-on-old	$i	$(timed "$OLD" env PYSTACHY_HOME="$OLD" "$NEW/pystachy" ir pystachy.py -o "$T/no.ll")"
done
echo "selflines	old-on-old	$(wc -l < "$T/o.ll")	new-on-new	$(wc -l < "$T/n.ll")	new-on-old	$(wc -l < "$T/no.ll")"
while read -r c; do
  [ -n "$c" ] || continue
  p=""; [ -f "$OLD/${c%.py}.path" ] && p=$(cat "$OLD/${c%.py}.path")
  ro=$(timed "$OLD" env PYSTACHY_PATH="$p" "$OLD/pystachy" ir "$c" -o "$T/c-old.ll"); lo=$(wc -l < "$T/c-old.ll" 2>/dev/null || echo 0)
  rx=$(timed "$OLD" env PYSTACHY_PATH="$p" PYSTACHY_HOME="$OLD" "$NEW/pystachy" ir "$c" -o "$T/c-x.ll"); lx=$(wc -l < "$T/c-x.ll" 2>/dev/null || echo 0)
  p=""; [ -f "$NEW/${c%.py}.path" ] && p=$(cat "$NEW/${c%.py}.path")
  rn=$(timed "$NEW" env PYSTACHY_PATH="$p" "$NEW/pystachy" ir "$c" -o "$T/c-new.ll"); ln=$(wc -l < "$T/c-new.ll" 2>/dev/null || echo 0)
  echo "case	$c	$ro	$lo	$rn	$ln	$rx	$lx"
  rm -f "$T"/c-*.ll
done < "$S/sample_cases.txt"
rm -rf "$T"
