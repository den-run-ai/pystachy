#!/bin/sh
F=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2/final
cd $F/tree2 || exit 1
echo "## make"; make pystachy > $F/tree2-make.log 2>&1; echo "make exit=$?"; grep "fixed point" $F/tree2-make.log
echo "## runtime.py IR vs original compiler"; build/orig1 rt runtime.py -o /tmp/rt_orig_$$.ll 2>/dev/null; ./pystachy rt runtime.py -o /tmp/rt_new_$$.ll; cmp /tmp/rt_orig_$$.ll /tmp/rt_new_$$.ll && echo "runtime.py IR byte-identical"; rm -f /tmp/rt_*_$$.ll
echo "## tests"; tests/run.sh ./pystachy > $F/tree2-tests.log 2>&1; tail -1 $F/tree2-tests.log
echo "## irsame"; same=0; diff=0; : > $F/tree2-irsame.log
for f in $(cat $F/corpus.txt); do r=$(sh $F/irsame.sh "$f"); if [ "$r" = same ]; then same=$((same+1)); else diff=$((diff+1)); echo "$r" >> $F/tree2-irsame.log; fi; done
echo "irsame: $same same, $diff different"
echo "## probes (native compiler)"; $F/probe.sh "$F/tree2/pystachy" > $F/probe-native.log 2>&1; tail -1 $F/probe-native.log
