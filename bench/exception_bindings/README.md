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

The index has two costs: each `IFn` still gains one optional field, and a lone legacy
query can stop at an early ordinary binding, while the first indexed query walks the
whole scope.

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
builds and tests. Omit both native arguments for a hosted-only comparison. Start
with a small calibration run before choosing the larger timing sizes; the original
scanner's quadratic work can dominate an instrumented run.

The runner alternates the baseline/candidate order each round, starts a fresh
process for every observation, and gives both variants the same generated source
file. It records source and executable hashes, all raw timings, child CPU, affinity
and host load, but not RSS. Every timed output must have identical LLVM IR,
diagnostic text and exit status, and generated programs must print their independent
CPython oracle (`1` for handler shapes, `N + 20` for the no-handler control).
Outputs are removed before each compile, so failed compilation cannot reuse one.
Each frontend process has a 180-second limit. A timeout or other failed comparison
leaves an incomplete report with the failed observation and error.

With `--counts`, separate instrumented hosted processes count actual statement
visits in `binds_other` and `other_bindings`. These runs must reproduce the same
LLVM IR; their elapsed times are not frontend timing samples. The unit tests assert
linear work and exercise the original scanner as a negative control. `--ops` in
the maintained scaling harness independently checks total compiler line execution,
flow work and copied/scanned collection items, avoiding a timing-based CI gate.

The generated shapes isolate repeated binding lookups. Native execution of the
CPython-recorded cleanup and scope fixtures, full corpus IR/diagnostic parity, and
self-hosting are separate correctness checks.

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
was shared to control those path literals.

Lint and repository checks passed in the same replay. The 12 focused unit tests, 18
frame tests, 16 state-contract tests, and the 424-test fast suite also passed. Full
local `make verify`, the broader compiler GC-self group, and macOS validation have
not been run for this prototype.

## Counter and timing results

The [raw cohorts](results/scope-timing/cohorts.json) ran on an AMD EPYC 9V74 host,
with the benchmark pinned to CPU 0, an eight-CPU container quota and an 8 GiB memory
limit. Hosted compilation used CPython 3.13.16; native compilation used the ordinary
LLVM 18.1.3 O2 binaries recorded above. This team serialized heavy jobs. No other
compiler process was observed at the sampled cohort boundaries, but the host was
shared; those observations and the recorded load averages do not prove an otherwise
idle host. RSS was not measured.

The measured local commit was `bb9ffdfbfb0f9f9afca73987c66fa5081c24e84f`. The initial
published PR head `8c32e0767bdaaab2e7e1bb8284e09423c23edc9a` has the identical tree,
`e6b73a7c14a58152564b6690390c697b0d3627dd`; publication changed commit metadata.
Both native binaries and all their consumed compiler/library/runtime source files
were checked against their fresh-bootstrap manifests before measurement. The
later evidence-only commits do not change those compiler inputs.

### Deterministic work

Separate [instrumented hosted runs](results/scope-timing/counts.json) measured
actual statement visits. Each generated case retained matching uninstrumented and
instrumented LLVM IR. Distinct names require one index, and no-handler functions
create none.

| Handlers N | Distinct names, old visits | Distinct names, indexed visits | Same name, old and indexed visits |
|---:|---:|---:|---:|
| 32 | 3,104 | 97 | 97 |
| 64 | 12,352 | 193 | 193 |
| 128 | 49,280 | 385 | 385 |

These are exactly `3*N*N + N` versus `3*N + 1` for distinct handler names. The
same-name control already avoided repeated queries through the existing local type
information. All three no-handler sizes recorded zero scans and zero index builds.

### Repeated frontend timings

The [primary timing cohort](results/scope-timing/timing.json) used five interleaved,
fresh-process samples per compiler, host and workload. All **180/180** primary
outputs matched in LLVM IR, diagnostics and exit status. Compiler preparation,
LLVM optimization/code generation and execution of the generated programs are
outside these timings. The generated programs separately passed their CPython
execution oracles; native execution is covered by the fixtures above.

Median milliseconds for the distinct-name workload:

| Handlers N | Hosted baseline | Hosted indexed | Hosted speedup | Native baseline | Native indexed | Native speedup |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 503.86 | 194.24 | 2.59x | 102.07 | 28.77 | 3.55x |
| 1,000 | 1,666.26 | 314.41 | 5.30x | 320.21 | 51.73 | 6.19x |
| 2,000 | 5,822.34 | 594.63 | 9.79x | 1,366.16 | 111.42 | 12.26x |

The before/after sample ranges were disjoint at every distinct-name size in both
hosts. At N=2,000, native ranges were 1,319.13–1,450.78 ms and 102.69–128.98 ms;
hosted ranges were 5,688.30–6,134.83 ms and 573.17–607.50 ms. These measurements
establish a gain on the generated many-handler frontend workload, not an ordinary
self-build or general compiler speedup.

Each control cell below gives baseline → indexed median milliseconds, then the
indexed time change:

| Control | N | Hosted frontend | Native frontend |
|---|---:|---:|---:|
| Same handler name | 500 | 166.03 → 170.63 (+2.8%) | 26.49 → 26.66 (+0.6%) |
| Same handler name | 1,000 | 301.69 → 304.22 (+0.8%) | 53.86 → 53.53 (-0.6%) |
| Same handler name | 2,000 | 553.13 → 561.21 (+1.5%) | 112.31 → 111.43 (-0.8%) |
| No handlers | 500 | 289.58 → 274.22 (-5.3%) | 46.34 → 45.12 (-2.6%) |
| No handlers | 1,000 | 593.86 → 538.62 (-9.3%) | 121.03 → 95.00 (-21.5%) |
| No handlers | 2,000 | 1,208.26 → 1,199.25 (-0.7%) | 211.98 → 223.83 (+5.6%) |

This cohort neither establishes a control speedup nor rules out a small regression:
every control's before/after ranges overlap. The N=1,000 native no-handler ranges
were 93.72–140.54 ms and 91.57–140.03 ms; N=2,000 ranges were 208.45–266.40 ms and
219.59–229.81 ms. The observed 5.6% slower N=2,000 median is reported alongside the
inconsistent smaller-size results. The
[derived summary](results/scope-timing/summary.json) includes all medians, ranges,
CPU medians and raw-report hashes.

The [bounded controller](results/scope-timing/controller.py) preserved the small
counter cohort, a separate N=500 [calibration](results/scope-timing/calibration.json),
and the primary timing cohort. After calibration, the cost-only sizing rule kept
500/1,000/2,000: projected timing duration was 66.6 s under a linear model or 199.8 s
under an all-quadratic model; actual primary-cohort duration was 92.9 s. Cohort limits
were 120/180/600 seconds and each direct frontend also had a 180-second limit.
All three cohorts completed; no measured process timed out or was aborted. The
controller is retained verbatim as execution evidence with its original paths;
use the portable commands under **Reproduce** for another checkout.
