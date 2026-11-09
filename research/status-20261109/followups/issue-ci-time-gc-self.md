# Make gc-self cost scale linearly with compiler size

## Problem

`gc-self` runs `PYSTACHY_GC_STRESS=5000 pystachy2 ir pystachy.py` with a 10-minute limit. Between Nov 2 and Nov 8 it grew:

- from 313 s to 391 s on ARM64;
- from 357 s to 454 s on x86-64 EPYC 7763 runners.

Meanwhile the compiler grew from 57.7k to 64.5k lines, and (64.5/57.7)² = 1.25 = 391/313.

Without stress the same compile takes about 5 s. The Nov 8 compiler compiles the Nov 2 source no slower (4.5 s against 4.7 s). Collections are therefore about 99% of `gc-self` time.

At about 1k compiler lines a day, `gc-self` reaches 600 s on EPYC 7763 near 74k lines, in 9–11 days. PR `cache-gc` (12.5 minutes there) has about 2.5 minutes left.

## Scope

Fix compiler cost, not the bound (#581). Measure collections, mark time and live heap during self-compilation with `PYSTACHY_GC=stats`. Then cut retained compiler state, for example per-function state after lowering, or the cost of each collection. Keep the 5,000 interval and the identity check.

## Done when

On a source-size sweep, gc-self time grows at most linearly, and it stays at or below 60% of its limit on `znver3`. Refs #41. Prepared with Claude Code assistance.
