# Independent review of optional dictionary scalar splitting

Reviewed the prototype core in the lifetime worktree against `04860a83618e744c6f461761b6ee7fdbbe21f985`. `reviewed-sources.json` pins the four source files reviewed. No blocking defect found within the bounded prototype scope.

## Source reasoning

- Eligibility requires a default-None `dict.getbox` with exactly one use by a scalar-optional `slot.unpack`, itself used exactly once by a candidate private local store. The existing slot proof rejects escaping, copied or identity-sensitive optional reads. Programs opting into dynamic Any or promoting integers are excluded conservatively.
- The original lookup instruction becomes `dict.find` without moving it, preserving its key descriptor and therefore user-callback/exception effects. Exactly one hash/lookup remains. Its existing block handler remains in force; generated IR for the independent probe uses `invoke ... @pys_dict_find ... unwind ...`.
- A presence bit derives from the found entry index, independently of payload bits. Zero, False, signed zero and NaN do not act as absence sentinels. A negative index returns a zero payload without reading dictionary storage.
- The payload read occurs immediately after lookup, before any subsequent statement can mutate the dictionary. Reentrant hash/equality effects occur inside the lookup exactly where they did before. The result then survives later clear/overwrite operations as an unboxed snapshot.
- The new helper reads dictionary storage and neither allocates nor calls user code. Its `rD` effect matches that behavior. The original lookup’s descriptor retains callback effects. The existing pass contract invalidates value/use/layout/effect caches, and final effects are recalculated.
- No source from pyjs was copied into this reviewed implementation. This is a narrow extension to Pystachy’s existing local optional-slot pass, not interprocedural lifetime analysis or an optional-return ABI change.

## Independent execution

`reentrant_get.py` is newly written and checks mutations and failures during both hash and equality callbacks: clearing storage, clearing/reinserting the query, overwriting the found key, and exceptions. Its consuming function clears the dictionary after get but before reading the saved optional value, testing snapshot timing. CPython 3.13.16 generated the expected output.

Six native configurations match exact stdout/stderr/exit code: JIT O2 with and without program GC stress, AOT O2 with and without runtime GC stress, and AOT O0 with and without runtime GC stress. LLVM 19.1.7; CPython-hosted compiler; IR checker enabled. AOT runs explicitly set `PYSTACHY_GC_STRESS=1`; JIT runs use `PYSTACHY_GC_STRESS_PROGRAM=1`. See `results.json` and saved logs. Generated IR confirms the optimization actually applied to the lookup.

This review does not establish a full compiler bootstrap, full corpus invariance, all optimization variants or full `make verify`. Those broader gates remain necessary before merge readiness. No native jobs remained active at the handoff to the timed benchmark window.
