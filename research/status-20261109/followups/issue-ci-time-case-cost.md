# Reduce per-case AOT and import cost in corpus suites

## Problem

On ARM64 runners, the native suite's summed case time rose 38% between Nov 2 ([41400680948](https://github.com/den-run-ai/pystachy/actions/runs/41400680948)) and Nov 8 ([42500300686](https://github.com/den-run-ai/pystachy/actions/runs/42500300686)).

- 72% of the increase came from 401 new cases averaging 2.4 times an existing case. Six `lib_logging*` cases take 15–18 s each.
- 28% came from existing cases, which got 10.7% slower.

Locally, on unchanged programs, the frontend and JIT cost no more, but AOT builds of 20 ordinary programs take 19% longer (six heavy ones: 9%). For small programs, `PYSTACHY_TIMING` attributes about 90% of an AOT build to `-O2` and code generation of the program with its runtime functions. AOT is about 85% of native time: PR JIT halves take 88–123 s, AOT halves 435–800 s. In `gc-ir`, 100 cases take 77% of the time.

## Scope

First measure, per corpus case, the AOT stage costs, the size of the linked-in runtime code and the cost of each import graph. Then candidates:

- Cache optimized runtime code across AOT builds.
- Trim heavy cases' imports.
- Reuse compiled library modules.

## Done when

Summed corpus case time falls by at least 15%, with unchanged coverage and AOT semantics. Refs #41, #1011.
