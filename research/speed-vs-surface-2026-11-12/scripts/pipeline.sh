#!/bin/bash
# Builder and analyzer loops over sweep/commits.txt (LABEL SHA per line). No timing runs here.
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep
LIST=${1:-$SW/commits.txt}
mkdir -p $S/results $S/logs
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done

builder() {
  while read -r label sha; do
    [ -f $S/results/built-$label ] && continue
    if $SW/build_one.sh "$label" "$sha"; then echo ok > $S/results/built-$label; else echo fail > $S/results/built-$label; fi
  done < "$LIST"
}

analyzer() {
  while read -r label sha; do
    while [ ! -f $S/results/built-$label ]; do sleep 5; done
    [ -f $S/results/perfprep-$label.json ] && continue
    if [ "$(cat $S/results/built-$label)" = ok ]; then
      /usr/local/bin/python3.13 -I $SW/analyze_one.py "$label" >> $S/logs/analyze-$label.log 2>&1
      tail -1 $S/logs/analyze-$label.log
    else
      echo "$label: build failed; skipped"
    fi
  done < "$LIST"
}

builder > $S/logs/builder.log 2>&1 &
bpid=$!
analyzer
wait $bpid
echo "pipeline done"; cat $S/logs/builder.log
