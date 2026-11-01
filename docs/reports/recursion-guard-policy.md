# Recursion guard policy, 1 November 2026

[PR #996](https://github.com/den-run-ai/pystachy/pull/996) enforces `sys.setrecursionlimit()`
in native code ([#988](https://github.com/den-run-ai/pystachy/issues/988)). Its first design
counted every source frame, as CPython does, and recovered performance with whole-program
`recursionleaf` and `recursionregion` passes. Those passes cost more compilation than they
saved: on `bench/smoke/text.py` they added 18.6% to the frontend's instructions and 6% to
the LLVM IR, and every guarded function gained `R I` effects, so pure helpers stopped being
pure for the typed optimizations.

The policy now counts only the functions that recursion can repeat
([internals](../internals.md#native-recursion-depth)): a source function on a cycle of
direct calls and generator resumes, or one that can reach code that graph does not show
(`U`: a call of a function value, a runtime callback such as `__eq__`). A generator resume
counts only if a body of its type can recur. Every other function is at most once on the
native stack, so it neither checks nor counts. The two passes, their private clones and the
related lowering paths are removed. Unbounded recursion is still caught; bounded recursion
can fail at a different call than in CPython
([deviation](../language/compatibility.md#errors-and-control-flow)).

## Inputs and method

| Input | Value |
|---|---|
| Baseline | main [07b26e0](https://github.com/den-run-ai/pystachy/commit/07b26e02425d023288ed95a9d2a5077be5aeb45e) |
| Previous candidate | PR #996 head [43eddb45](https://github.com/den-run-ai/pystachy/commit/43eddb455bc01ad348baec01590b258cacce681b) |
| Candidate | CANDIDATE_SHA (this branch) |
| Compilers | Each revision's native compiler from a fresh `make` bootstrap (three matching IR stages); PR head binary SHA-256 `588eb206…`, matching the PR record |
| Toolchain | LLVM/clang 18.1.3, CPython 3.13.18 (hosted compiler and oracle), Valgrind 3.22.0 |
| Host | Linux x86-64, Intel Xeon @ 2.10 GHz, 4 vCPUs, shared; counts pinned with `taskset` |
| Caches | Private runtime cache per revision, warmed before every measurement |

Instruction counts are Valgrind `callgrind` totals (`Ir`) and are deterministic: they do not
depend on host load. *Frontend* is `pystachy ir`. *AOT* is the whole process of the built
executable. *JIT* is `pystachy run` with every child process traced (frontend, `opt`,
`lli` code generation, execution and teardown). Every executable's output matched CPython's.
Wall-clock samples are reported separately; on this shared host, sides with byte-identical
program IR differed by up to 9% between medians, so instruction counts carry the decision.

RESULTS_PLACEHOLDER
