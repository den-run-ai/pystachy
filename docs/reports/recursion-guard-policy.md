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
direct calls, or one whose effect summary has `U` (it can run code the direct call graph
does not show). Every other function is at most once on the native stack, so it neither
checks nor counts. The two passes, their private clones and the related lowering paths are
removed. Unbounded recursion is still caught; bounded recursion can fail at a different
call than in CPython ([deviation](../language/compatibility.md#errors-and-control-flow)).

RESULTS_PLACEHOLDER
