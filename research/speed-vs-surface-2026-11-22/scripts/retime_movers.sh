#!/bin/bash
# After the idle bootstraps: 15 interleaved runs of the benchmarks that moved most between the second edition's
# commit and the latest one in the timing run, to tell a change from that run's noise.
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep; V=$S/v3; PY=/usr/local/bin/python3.13; R=$SW/retime.py
P=1117-1034_3cf23d20; H=1121-1151_4998521d
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
until grep -q "all done" $S/logs/after_builds3.log; do sleep 15; done
sleep 30
(cd $SW && $PY -I $R chaos 15 $V/raw/retime-chaos.json 1111-1943_8434a911 $P 1117-2325_e2b97bb4 1118-1050_8259611e $H)
for b in nqueens regex_dna micro_spectral raytrace richards_super; do
  (cd $SW && $PY -I $R $b 15 $V/raw/retime-$b.json $P 1118-1050_8259611e $H)
done
echo "movers done $(date -u +%H:%M:%S)"
