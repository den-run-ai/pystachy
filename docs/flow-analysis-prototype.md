# Flow analysis prototype

This draft tests three ideas from gradual typing and static analysis against
Pystachy's existing native backend. It starts at `aad4f1c` and keeps the two
language experiments opt-in. It does not add an external type checker or a new
runtime interpreter.

Tracking: [local retyping #248](https://github.com/den-run-ai/pystachy/issues/248),
[reusable summaries #380](https://github.com/den-run-ai/pystachy/issues/380), and
[closed unions / runtime handoff #381](https://github.com/den-run-ai/pystachy/issues/381).

| Experiment | Implemented approach | Boundary |
|---|---|---|
| Local retyping | Give eligible straight-line assignments separate internal local bindings. | No type-changing branch/back-edge joins, captured cells, globals, exception scopes or explicitly annotated binding contracts. |
| Function summaries | Reuse existing argument/return specializations; retain effect summaries and propagate changes through reverse caller dependencies. | In-memory reuse within one compilation, not a persistent module cache. Unknown calls retain conservative effects. |
| Closed unions | Explicit scalar union annotations, tagged storage, branch assignments and `isinstance` narrowing. | `int`, `float`, `bool`, `str`, optionally `None`; no open `Any`, automatic heterogeneous inference or general union operator dispatch. |

## Run

Build the compiler normally, then enable both language experiments:

```sh
make
PYSTACHY_FLOW_LOCALS=1 PYSTACHY_CLOSED_UNIONS=1 \
  ./pystachy run examples/flow_analysis.py
PYSTACHY_FLOW_LOCALS=1 PYSTACHY_CLOSED_UNIONS=1 \
  ./pystachy build examples/flow_analysis.py -o build/flow-analysis
./build/flow-analysis
```

The example also runs unchanged under CPython. It prints:

```text
42
2.3333333333333335
0 4 12
READY -3
4 6 aa bb
```

The combined check compares the hosted and self-hosted compilers' IR, JIT and
AOT results against CPython, and executes the AOT output with garbage collection
at every allocation:

```sh
make flow-analysis-check
```

Set `FLOW_ANALYSIS_COMPILER=build/verify/pystachy2` to reuse a verified compiler.
`PYSTACHY_SUMMARY_STATS=1` prints effect-summary reuse, invalidation and propagation
counters during compilation. These counters are diagnostics, not program output.

## Why these boundaries

The local retyping experiment addresses the straight-line portion of
[#248](https://github.com/den-run-ai/pystachy/issues/248). For example, a parsing
helper can reuse a name after converting text to an integer; a loop accumulator
can become a float after the loop. The RHS still reads the preceding binding.
The pass leaves unsupported scopes on the existing compiler path, where existing
diagnostics still apply. It is not a general SSA construction or loop-inference
algorithm.

Pystachy already specializes unannotated functions and retains their inferred
return types. The summary prototype uses that cache rather than introducing a
second inference engine. Effects are recomputed only for changed summaries and
their dependent callers after rescanning local operations. Resetting the affected
part of the graph handles removed effects, including recursive call cycles. A
finite effect-bit lattice bounds propagation; an unknown indirect call never
becomes a proof of purity. This also addresses the algorithmic defect in
[#83](https://github.com/den-run-ai/pystachy/issues/83).

The union implementation adapts the explicit storage and narrowing machinery of
[#238](https://github.com/den-run-ai/pystachy/pull/238), following its review's
request to separate explicit unions from automatic widening and general
arithmetic/comparison dispatch. An annotated union fixes the representation at a
branch join. Narrowed operations use runtime tag checks; facts about mutable
globals, fields and captured bindings must not be treated as stable local facts.

## Relationship to dynamic execution

The tagged interpreter and runtime specialization in
[#376](https://github.com/den-run-ai/pystachy/pull/376) remain a separate draft.
That experiment's `mixed_local` example is an integer/string branch join. The
`event_label` example here demonstrates that the same shape can compile directly
when a finite union is explicitly declared and operations are narrowed.

This draft does **not** connect the two runtimes, import #376's scalar ABI, or
claim that an observed tag is a static proof. A later integration needs a shared
eligibility/summary contract, checked representation boundaries and a defined
fallback for unknown types. Runtime profiles may select a specialization; entry
guards are still required. Arbitrary dynamic Python and mid-function
deoptimization remain outside this prototype.

## References

- [TypeScript narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html):
  types at program points, assignments and control-flow joins.
- [Zuban development notes](https://github.com/zubanls/zuban/blob/master/development-notes.md):
  separate syntax/analysis data, incremental locality and explicit limitations.
- [Jedi development](https://jedi.readthedocs.io/en/latest/docs/development.html):
  demand-driven inference and bounded exploration; the documentation notes that
  some implementation details are historical.
- [Clang dataflow introduction](https://clang.llvm.org/docs/DataFlowAnalysisIntro.html):
  lattices, joins and worklists.
- [mypyc representations](https://mypyc.readthedocs.io/en/latest/using_type_annotations.html):
  efficient representations, erased types and runtime checks.

These are design references. No Zuban, Jedi, TypeScript or mypyc implementation
code is included.
