#!/bin/bash
# measure.sh: each workload built ahead of time by compiler A (the bytes-like branch, no payload
# tags) and B (the alias-class branch), its outputs compared, then its instructions counted by
# callgrind: "name A B change"
S=/tmp/claude-0/-home-user-pystachy/8dfd0d3f-eb31-5d1b-8d1b-90a856e3b0b1/scratchpad
. "$S/env316.sh"
cd "$S/tb/bench" || exit 1
A=/home/user/wt-byteslike/pystachy
B=/home/user/wt-bytetbaa/pystachy
run() {  # name source pathdir args...
  name=$1; src=$2; path=$3; shift 3
  for v in A B; do
    c=$A; [ $v = B ] && c=$B
    PYSTACHY_PATH=$path PYSTACHY_CACHE="$S/tb/bench/cache-$v" timeout 900 $c build "$src" -o "$name.$v.bin" > "$name.$v.build" 2>&1 || { echo "$name: build $v failed"; return; }
    (cd "$S/perf" && "$S/tb/bench/$name.$v.bin" "$@") > "$name.$v.out" 2>&1
  done
  sed -E 's/[0-9]+\.[0-9]+ (ms|s)/T/g; s/best T/best/' "$name.A.out" > "$name.A.cmp"; sed -E 's/[0-9]+\.[0-9]+ (ms|s)/T/g; s/best T/best/' "$name.B.out" > "$name.B.cmp"
  cmp -s "$name.A.cmp" "$name.B.cmp" || { echo "$name: OUTPUTS DIFFER"; diff "$name.A.cmp" "$name.B.cmp" | head -4; return; }
  for v in A B; do
    (cd "$S/perf" && valgrind --tool=callgrind --callgrind-out-file="$S/tb/bench/cg-$name.$v.out" "$S/tb/bench/$name.$v.bin" "$@") > "$name.$v.cg" 2>&1
  done
  a=$(grep -o 'Collected : [0-9]*' "$name.A.cg" | grep -o '[0-9]*$'); b=$(grep -o 'Collected : [0-9]*' "$name.B.cg" | grep -o '[0-9]*$')
  echo "$name $a $b $(python3 -c "print('%+.2f%%' % (100.0 * ($b - $a) / $a))")"
}
run appendix "$S/tb/bench/appendix.py" "" 2000000 1
run buffers "$S/tb/bench/bench_buffers.py" "" 200000 1
run scan "$S/tb/bench/scan.py" "" "$S/tb/bench/scan1m.in"
run parser_list "$S/perf/bench2.py" "$S/ba/consumer/base" 1
run parser_bytearray "$S/perf/bench2.py" "$S/ba/consumer/ba" 1
