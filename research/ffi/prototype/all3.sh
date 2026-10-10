#!/bin/sh
F=/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad/stage2/final
cd $F/tree3 || exit 1
echo "## make"; make pystachy > $F/tree3-make.log 2>&1; echo "make exit=$?"; grep "fixed point" $F/tree3-make.log
echo "## runtime.py IR vs original compiler"; build/orig1 rt runtime.py -o /tmp/rt_orig_$$.ll 2>/dev/null; ./pystachy rt runtime.py -o /tmp/rt_new_$$.ll; cmp /tmp/rt_orig_$$.ll /tmp/rt_new_$$.ll && echo "runtime.py IR byte-identical"; rm -f /tmp/rt_*_$$.ll
echo "## check_runtime"; python3 tools/check_runtime.py 2>&1 | tail -2
echo "## rtabi"; python3 tools/rtabi.py ./pystachy 2>&1 | tail -3
echo "## tests"; tests/run.sh ./pystachy > $F/tree3-tests.log 2>&1; tail -1 $F/tree3-tests.log
echo "## irsame"; same=0; diff=0; : > $F/tree3-irsame.log
for f in $(cat $F/corpus.txt); do r=$(sh $F/irsame.sh "$f"); if [ "$r" = same ]; then same=$((same+1)); else diff=$((diff+1)); echo "$r" >> $F/tree3-irsame.log; fi; done
echo "irsame: $same same, $diff different"
echo "## probes (native compiler)"; sh $F/probe3.sh "$F/tree3/pystachy" > $F/probe3-native.log 2>&1; tail -1 $F/probe3-native.log
echo "## ubsan (trap mode)"; sh $F/ubsan3.sh > $F/ubsan3.log 2>&1; cat $F/ubsan3.log
