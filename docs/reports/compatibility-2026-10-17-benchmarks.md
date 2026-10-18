# Benchmark and upstream-suite compatibility audit — 2026-10-17

Compiler baseline: `d3fbfc6f5f6d5650f25ffc0d97be93b512f41a6f`, CPython 3.13.16,
LLVM 18.1.3, Linux x86-64. Native execution used `build/pystachy1` from this source;
the full bootstrap subsequently verified compiler and runtime IR fixed points.
The controller and this report changed during the audit; compiler/runtime sources
did not. This is a bounded compatibility assessment, not a full CPython or PyPI
certification. [Machine-readable evidence](compatibility-2026-10-17-benchmarks.json)
retains commands, outputs, hashes and timing samples with installation paths normalized.

## What works now

| Surface | Fresh evidence | Interpretation / remaining adaptation |
|---|---|---|
| Delivered pyperformance 1.14.0 ports | **18/18** small-input programs matched CPython under native JIT and AOT | Adapted source, custom deterministic runners; not upstream pyperformance scores |
| Upstream pyperformance algorithms, only their runner replaced | **6/52 compile**: `fannkuch`, `generators`, `nbody`, `nqueens`, `regex_v8`, `unpack_sequence` | The other 46 reject, including licence-deferred `deltablue`; first-error census is compile-only |
| Newly usable unchanged algorithm bodies | `generators`, `nqueens`, `fannkuch` executed with checksum/assertion runners under CPython, JIT and AOT | No algorithm/type changes: see exact runners below; `generators` is not yet a delivered benchmark |
| pyperf 2.10.0 controlling a Pystachy executable | CPython `python -m pyperf command` successfully ran compiled `richards` | pyperf and psutil remain on CPython; this measures a subprocess, not a compiled pyperf package |
| Pinned upstream port-preservation tests | fnmatch **17/17**, textwrap **66/66**, no skips | Unedited upstream tests run on CPython against the adapted module; dependencies remain CPython's |
| Compiled CPython-derived tests | Existing explicit fnmatch/textwrap/functools and regex selections | Adapted assertions in differential programs; not the unmodified unittest/regrtest harness |

The 52-file census's provenance, changed-hunk notes and timed-region checks passed.
The release has another 21 dependency-bearing benchmarks outside this census;
they were not counted as compiler failures. Within the 33 nondeferred sources
without a delivered port, 32 reject and `generators` compiles. The remaining
undelivered source is licence-deferred `deltablue`, which also rejects. See the refreshed
[per-source table](../../bench/pyperformance/README.md#blocked).

Several old port edits are now optional. Upstream `nqueens` uses generators,
runtime-length tuples, range values, reverse slices and slice assignment;
`fannkuch` uses slice assignment; `generators` uses recursive `yield from` and
range slicing. The original algorithm bodies now compile. Restoring these sources
would simplify their ports, but should retain result checks and refresh timing
records because list materialization and work performed would change.

## Test and benchmark harnesses

These probes supplied the pinned upstream package, `lib/`, then CPython 3.13.16's
stdlib in `PYSTACHY_PATH`. This explicitly tries available Python dependencies,
instead of treating the default missing-module search result as the final answer.
Each entry is a first observed blocker, not an exhaustive assessment.

| Harness / source | Probe | First compiler blocker | Adaptation assessment |
|---|---|---|---|
| pyperf 2.10.0 | `import pyperf; print(pyperf.__version__)` | `pyperf/_utils.py`: missing native `select` module | Substantial harness work: process control, metadata, platform APIs, psutil; keep controller on CPython |
| pyperformance 1.14.0 CLI | `import pyperformance.cli; pyperformance.cli.main()` | `importlib`: missing native `_imp` module | Substantial environment/package-management machinery; use the existing adapted workload controller |
| pytest 8.4.2 | `import pytest; print(pytest.__version__)` | `ast.py`: missing native `_ast` module | Substantial dynamic test collection/assertion machinery; run pytest as a CPython controller for compiled programs |
| CPython 3.13.16 unittest | Minimal `TestCase`, `assertEqual`, `unittest.main()` | `unittest/util.py`: `namedtuple` absent from the selected subset `collections` | This is the current library-path choice's first failure; changing the collections implementation is not proof the harness works |
| Unmodified CPython `test_fnmatch.py` | Compile the pinned original test file | Same unittest/collections failure | Its passing CPython-hosted suite cannot be relabelled a passing compiled suite |

The audit environment's installed CPython has no `test` package/regrtest, so the
full CPython test driver was not executed here. No full regrtest claim follows from
the selected differential tests. Missing C runtime modules and dynamic harness
operations require more than annotation changes. Extracting supported upstream
assertions into ordinary compiled functions is already the repository's practical
approach; it avoids making the compiler implement a test framework first.

The current acceptance manifest inventories **fnmatch and textwrap only**:

| Upstream test methods | Complete compiled mappings | Partial | Deviation | Unsupported |
|---|---:|---:|---:|---:|
| fnmatch: 17 | 12 | 2 | 0 | 3 |
| textwrap: 66 | 63 | 1 | 2 | 0 |

Seven selected cache/lru_cache methods and four large regex methods are separate
explicit selections. The mappings describe retained upstream assertions, not every
API in those modules. See [port acceptance](../porting.md), `make port-check`,
`make test-cpython-subset`, `make port-check-large`, `make re-fuzz` and the normal
GC-stress/UBSan/optimization-disabled differential suite. Issue
[#361](https://github.com/den-run-ai/pystachy/issues/361) tracks expanding this evidence;
[#120](https://github.com/den-run-ai/pystachy/issues/120) remains relevant to Unicode
deviations. Passing imports and hosted tests are separate evidence categories.

## Remaining workload adaptations

Small, concrete next steps are adding `generators` with deterministic results and
removing now-obsolete `fannkuch`/`nqueens` workarounds. Numeric literal/field
annotations remain the first problems for `barnes_hut`, `float`, `go`,
`meteor_contest`, `spectral_norm`, `richards` and `richards_super`; their existing
ports demonstrate bounded adaptations. That is stronger evidence than a first
error alone, but does not establish every upstream input is supported.

Larger gaps include async/event-loop/network workloads, multiprocessing, decimal
arithmetic, arbitrary-precision `pidigits`, pickle/copy/object reflection,
CPython-GC-specific workloads, and dependency-heavy frameworks. `array` remains
the first blocker for upstream `raytrace`/`scimark`; their delivered ports use
lists. `regex_dna` now reaches `bytearray()` rather than failing at bytes syntax.
`crypto_pyaes` reaches the unsupported CTR class hierarchy; basic AES port success
does not establish that mode. These are work to assess individually, not promises
that adding one missing module completes an entire benchmark.

## Correctness and performance gaps

No new compiler crash or wrong result was observed in the 18 delivered smoke
benchmarks or the three additional upstream-body probes. Their checks have two
important limits that remain actionable under
[#530](https://github.com/den-run-ai/pystachy/issues/530):

1. **SciMark SOR and sparse checksums are insensitive to a missing kernel.** Both
   operate on zero-filled inputs and return zero. A fresh CPython mutation probe
   replacing SOR with a no-op and sparse multiplication with `return 0.0` preserved
   these checksums. Add separate nonzero correctness fixtures without silently
   changing the benchmark's timed workload/provenance.
2. **`unpack_sequence`'s AOT timing is not an unpacking speedup.** The repeated
   unchanged inputs permit dead-work removal; its AOT ratio must remain excluded
   from performance conclusions. The CLI still prints a numeric ratio, so read
   that row with this limitation even when all output comparisons pass.

Fresh timing observations are recorded below. Timings use three processes per
mode with rotated order and a primed runtime cache. This host was shared with
other audits; no regression threshold or revision-to-revision speedup is inferred.
Whole-process JIT includes compilation; the printed timed region does not.

| Workload | CPython wall / timed | JIT wall / timed | AOT wall / timed | AOT build |
|---|---:|---:|---:|---:|
| `richards` | 1.042 s / 1.021 s | 0.437 s / 0.027 s | 0.025 s / 0.018 s | 1.40 s |
| `regex_effbot` | 0.692 s / 0.635 s | 3.723 s / 1.815 s | 1.399 s / 1.384 s | 6.35 s |
| `regex_v8` | 1.063 s / 0.350 s | 4.585 s / 1.372 s | 2.316 s / 1.276 s | 7.70 s |
| `unpack_sequence` | 0.747 s / 0.731 s | 0.195 s / 0.029 s | 0.002 s / 20.50 µs | 0.67 s |

The one-minute load average was 8.7 at start and 7.8 at end. The largest
within-mode wall spread was 58%; a process spent as little as
48% of its wall time on CPU. `regex_effbot` and `regex_v8` remained slower than
CPython in these samples, while `richards` was much faster. Those directions are
useful leads for profiling; the precise ratios are not stable performance promises.

The prior [published snapshot](../pyperformance.md) is historical, not a measurement
of this baseline. Regex matching remains a performance concern worth profiling
separately from startup. [#430](https://github.com/den-run-ai/pystachy/issues/430)
already supplies the opt-in `PYSTACHY_JIT_CODEGEN=0` alternative; it is not a
universal fix for sustained matching. [#358](https://github.com/den-run-ai/pystachy/issues/358)
tracks dead code consuming the JIT inlining budget. Neither is resolved by a
passing output comparison or a noisy small-input wall-time ratio.

## Reproduce

Use `.python-version`, LLVM 18 and the pinned pyperformance 1.14.0 sdist. Its
SHA-256 remains `91f74393997b604375ad5b79bf569a24076d70181c076a53abad5383a238a8aa`.
pyperf 2.10.0's source archive hash is
`dd93ccfda79214725293e95f1fa6e00cb4a64adcf1326039486d4e1f91caaa62`; pytest 8.4.2's
wheel hash is `872f880de3fc3a5bdc88a11b39c9710c3497a547cfa9320bc3c5e62fbf272e79`.

```sh
make
python3.13 -m unittest discover -s tools -p test_bench_pyperformance.py
python3.13 tools/bench_pyperformance.py --census pyperformance-1.14.0.tar.gz
python3.13 tools/bench_pyperformance.py --smoke
python3.13 tools/bench_pyperformance.py --benchmarks richards regex_effbot regex_v8 unpack_sequence --runs 3
python3.13 tools/port_check.py
./pystachy build bench/pyperformance/richards.py -o build/richards
# In a separate CPython environment with pyperf 2.10.0 and psutil installed:
python3.13 -m pyperf command --processes 1 --values 2 --warmups 0 --loops 1 --name pystachy-richards-aot ./build/richards 1
```

The last command is a harness smoke check, with too few samples for performance
claims. For the extra upstream-body checks, apply `census_source()` from
`tools/bench_pyperformance.py` to the pinned `bm_NAME/run_benchmark.py`, replacing
only its runner with the corresponding body below, then run CPython, JIT and AOT:

```python
# generators: retained bench_generators(1) also checks its own 10-element tree.
bench_generators(1)
values = list(tree(range(100000)))
assert values == list(range(100000))
print("generators", len(values), sum(values))  # generators 100000 4999950000

# nqueens
solutions = list(n_queens(8))
assert len(solutions) == 92
print("nqueens", len(solutions), solutions[0], solutions[-1])

# fannkuch
print("fannkuch", fannkuch(7))  # fannkuch 16
```

The census controller now records `compile_status` independently of delivered-port
membership, and labels a successful unported source `runner-only compiles; not
ported`. Its regression test covers successful and rejected unported sources;
the 16 controller tests pass. This prevents the formerly contradictory
`generators | blocked | none: compiles` report.
