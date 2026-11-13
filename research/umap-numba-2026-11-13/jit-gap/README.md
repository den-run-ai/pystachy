# Where the JIT tier loses to AOT on the UMAP probe (13 November 2026)

UMAP probe, 10,000 points, `pystachy run` with the program cache off (`PYSTACHY_PROGRAM_CACHE=0`:
an experiment's setting is not in the cache's key), pinned to one CPU, single runs; the runtime PR
stack (#1436, #1437, #1442) plus #1450 (`stacklg2`). Seconds of the probe's own stage timers.

| Variant | kNN | layout |
|---|---:|---:|
| AOT | 0.92 | 4.16 |
| JIT | 2.42-2.53 | 5.39-5.50 |
| JIT, listfast also for `list[float]` reads | 2.66-2.68 | 5.06-5.17 |
| JIT, `loop-mssa(licm),gvn` added to its function passes | 2.55 | 5.00 |
| JIT, also loop-rotate and loop-unroll | 2.38 | 5.40 |

Replaying the JIT's passes (`globaldce,always-inline,cgscc(inline,function(mem2reg,instcombine,
simplifycfg)),function(early-cse,adce)`, then `llc -O2`) on the program's IR shows #1450's copy of
the distance loop at about 13 instructions per element, against AOT's 4: the list and its items
pointer reloaded on each iteration (no LICM), no unrolling, the accumulator spilled to the stack,
and the counter's increment checked for overflow. The copy calls no runtime function, so inlining
runtime.c would not change it; the JIT tier's short pipeline, chosen for start-up, is the gap.
The JIT optimizes this program in 0.06-0.11 s.
