# Exception-binding indexing

This experiment addresses [#90](https://github.com/den-run-ai/pystachy/issues/90):
each new `except ... as name` used to walk its whole function looking for a binding
outside exception targets. For the generated `handlers` shape, N distinct names
cause exactly `3*N*N + N` statement visits. Reusing one name is a control: the
existing compiler already avoids subsequent queries once that name has a type.
The separate `nohandlers` timing control uses the maintained `funcs` shape, N
small annotated functions without handlers, to expose costs unrelated to indexing.

The prototype builds the same set of names in one traversal and uses membership
for later queries. The index belongs to the current `IFn`, starts absent, and is
released when `Gen.function` completes, including module initialization functions.
Nested compilation preserves it through the existing `Frame.fn` transfer. A local
retry creates a fresh `IFn`; `dry()` may retain the syntax-only summary because it
contains no inferred types, flow decisions, generated instructions, or diagnostics.
Functions that need no binding query create no dictionary. The index is built
after inherited-method materialization and local-version rewriting.
Each `IFn` still gains one optional field. A lone legacy query can also stop at an
early ordinary binding, while the first indexed query walks the whole scope.
Neither case is evidence of an ordinary compiler speedup or memory reduction;
the controls and any noisy/regressing timings must remain visible.

The scope and binding rules are those of `analysis.binds_other`, including imports,
assignment expressions and nested-definition headers, with nested function/class
bodies excluded. `global_reader` keeps its original query and rejection behavior.
Empty-container lookahead (#217), source profiling (#1108), and program caching
(#1103) are separate work.

## Reproduce

Use the repository's pinned CPython and matching LLVM toolchain. Create a baseline
checkout at `f7103067545b43cdcd8ce20dc66b1571425b3a8d`, build both checkouts normally
with `make`, and retain each build's compiler/runtime fixed-point result. The
benchmark takes those already built native compilers; it does not include their
preparation or LLVM optimization/code generation in frontend timing.

```sh
python3.13 -m unittest discover -s tools -p test_exception_bindings.py
python3.13 tools/scaling.py -c 'candidate=python3.13 pystachy.py' \
  -s handlers,samehandlers -n 32,64,128 -r 1 --ops --check
python3.13 bench/exception_bindings/run.py \
  --baseline ../pystachy-before --candidate . \
  --sizes 32,64,128 --rounds 1 --counts --cpu 0 \
  --output bench/exception_bindings/results/counts.json
python3.13 bench/exception_bindings/run.py \
  --baseline ../pystachy-before --candidate . \
  --baseline-native ../pystachy-before/pystachy --candidate-native ./pystachy \
  --sizes 500,1000,2000 --rounds 5 --cpu 0 \
  --output bench/exception_bindings/results/run.json
```

Choose a CPU in the process's allowed affinity. Run timing alone, apart from other
builds and tests. Omit both native arguments for a hosted-only comparison. The
runner alternates the baseline/candidate order each round, starts a fresh process
for every observation, and gives both variants the same generated source file.
It records source and executable hashes, all raw timings, child CPU, affinity and
host load. Every timed output must have identical LLVM IR, diagnostic text and exit
status, and generated programs must print their independent CPython oracle (`1`
for handler shapes, `N + 20` for the no-handler control).
Outputs are removed before each compile, so failed compilation cannot reuse one.
Each frontend process has a 180-second limit. A timeout or other failed comparison
leaves an incomplete report with the failed observation and error. Start with a
small calibration run before choosing the larger timing sizes; the original
scanner's quadratic work can dominate an instrumented run.
RSS is not measured by this runner.

With `--counts`, separate instrumented hosted processes count actual statement
visits in `binds_other` and `other_bindings`. These runs must reproduce the same
LLVM IR; their elapsed times are not frontend timing samples. The unit tests assert
linear work and exercise the original scanner as a negative control. `--ops` in
the maintained scaling harness independently checks total compiler line execution,
flow work and copied/scanned collection items, avoiding a timing-based CI gate.

The generated shapes isolate repeated binding lookups; they do not establish an
ordinary self-build speedup. Native execution of the CPython-recorded cleanup and
scope fixtures, full corpus IR/diagnostic parity, and self-hosting are separate
correctness checks.

## Native validation

The fresh [main bootstrap](results/main/report.json) used source
`f7103067545b43cdcd8ce20dc66b1571425b3a8d`; the fresh
[candidate bootstrap](results/scope-index-bootstrap/report.json) used
`cbf4b9c9cefe088124ecab134d88c2eaadcc174f`. Both ordinary `make -B pystachy`
builds passed three compiler IR and three runtime IR fixed-point witnesses.
Their records include source, tool and executable hashes. Those single build
durations are validation observations, not a controlled self-build comparison.

The [native check record](results/scope-validation/report.json) contains 30 passing
JIT/AOT/rejection checks across 16 selected cases, then the same 30 checks with
program collection on every allocation. The two new fixtures also emitted
[identical frontend IR under compiler collection stress](results/scope-validation/compiler-stress-witnesses.json).

The first [independent-home full-corpus comparison](results/scope-validation/corpus.log)
failed: 261 of 4,240 outputs differed. Its displayed examples embed the two checkout
library paths in raw IR strings. This failure is preserved; no maintained oracle
normalization was changed. A [second, explicit shared-home comparison](results/scope-validation-shared-home/report.json)
hashed all 104 library/runtime files equal across the two checkouts before and
after execution, then passed [4,240 exact IR, diagnostic and exit-status comparisons](results/scope-validation-shared-home/corpus.log).
The compiler binaries remained distinct; only the identical library/runtime home
was shared to control those path literals. Lint and repository checks passed in
the same replay. The 12 focused unit tests, 18 frame tests, 16 state-contract tests,
and the 424-test fast suite also passed. Full local `make verify`, the broader
compiler GC-self group, and macOS validation have not been run for this prototype.
