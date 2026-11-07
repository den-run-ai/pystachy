# Guarded batch scoring

A minimal experiment in precompiled callback specialization: select a loss function
at runtime, check its identity once per batch, and run a specialized native loop.
The squared-error and absolute-error paths exceed 2x in the measured AOT workload.
The implementation adds **45 lines of scoring code and no compiler/runtime changes**.

## API and mechanism

```python
from scoring import score_guarded, squared_error

predicted = [1.0, 2.0, 3.0]
expected = [0.0, 1.0, 1.0]
print(score_guarded(squared_error, predicted, expected))  # 6.0
```

Put this directory on `PYSTACHY_PATH` for Pystachy or `PYTHONPATH` for CPython.
Both implementations accept a `Callable[[float, float], float]` and two equally
long native `list[float]` inputs. A length mismatch raises `ValueError` before
calling the callback. Each batch captures one callback; the callback can change
between batches.

`score_generic` is the erased-callback baseline. `score_guarded` recognizes
`squared_error` and `absolute_error`, then passes the known function to `_score`.
The existing compiler specializes `_score`'s unannotated callback parameter:

- One shared Python loop produces two known-target variants and a generic fallback.
- LLVM can inline each known callback, hoist stable buffer information and unroll
  the loop while retaining the original floating-point accumulation order.
- Other callbacks retain their code and captured environment. The fallback also
  preserves callback effects, exceptions and live list mutations.

The public annotations establish the numeric storage layout; callable identity is
the remaining runtime uncertainty. A list of `Any` values needs a different proof.
The two targets are explicit choices compiled ahead of time. No profiling or new
compiler pass is needed for this experiment.

This reuses the callback-template pattern already used by
[`ndarray._binary` and `_unary`](../ndarray/ndarray.py). It follows the bounded
entry-guard approach evaluated in [#1063](https://github.com/den-run-ai/pystachy/pull/1063)
using ordinary Python source. It is independent of the parallel-map and retained
CPU-buffer drafts. This is a new configurable scoring prototype; those existing
applications were not accelerated or benchmarked here.

## Measured results

Measured November 6, 2026 (Pacific): Linux x86-64, AMD EPYC 9V74, LLVM 18.1.3,
CPython 3.13.16, one pinned CPU (8). Compiler sources are current-main commit
`f7103067545b43cdcd8ce20dc66b1571425b3a8d`. The
[published experiment source](https://github.com/den-run-ai/pystachy/commit/d66686bc50d7939f51c85ca6d8b1cdd924725270)
has exactly the measured local source tree; both commit identities are recorded
in the [raw results](results/llvm18-2026-11-06.json).

Seven alternating pairs per scenario and execution mode; three alternating AOT
build pairs. Every output is checked against both CPython variants before accepting
timings. The default large cases score 16,384 values in each of 2,000 batches
(32,768,000 callback invocations per process). Speedups compare the same Pystachy
compiler, input schedule and loop body.

| Scenario | Generic AOT, ms | Guarded AOT, ms | AOT paired speedup | JIT paired speedup |
|---|---:|---:|---:|---:|
| Squared error | 111.967 | 28.110 | **4.00x** | 1.30x |
| Absolute error | 119.941 | 27.504 | **4.20x** | 1.23x |
| 99% squared error, 1% closure fallback | 112.284 | 29.101 | **3.88x** | 1.32x |
| Alternating the two known targets | 119.177 | 27.600 | **4.31x** | 1.36x |
| All closure fallbacks | 119.118 | 119.624 | 1.00x | 1.07x |
| Known target, then two closure environments | 114.813 | 71.469 | 1.61x | 1.21x |
| One value per batch, 200,000 batches | 1.705 | 1.598 | 1.07x | 1.06x |
| Fresh inputs: 1,024 values x 2,000 batches | 39.219 | 33.106 | 1.20x | 1.03x |

Times are medians for each variant; speedups are medians of paired ratios, so
dividing the two displayed time medians need not give the displayed speedup.
The timed region includes schedule lookup, validation, the guard and the complete
reduction. Initial inputs and callback schedules are built before that region.
The final row includes fresh input allocation/conversion in every measured batch.
The one-value control lasts less than 2 ms and is advisory.

The four large known-target AOT scenarios won all seven pairs; their minimum
paired gains were 3.79x or greater. All-miss AOT results span 0.92-1.09x and have
no demonstrated advantage. Fresh-input results span 0.98-1.31x: construction
substantially limits the benefit. This is one shared-host measurement, not a
whole-application forecast or a machine-independent timing gate.

### Startup, code size and memory

For the four large known-target cases, full AOT process times improve 3.70-4.15x,
including initial construction and process startup. JIT process times, including
compilation and startup with a warm runtime cache, improve only 1.06-1.20x. The
one-value JIT process control is 0.96x. JIT therefore does **not** meet the 2x target.

The AOT driver optimizes the program and runtime together with LLVM `-O2`.
The JIT driver inlines program functions and calls a separately compiled runtime.
The [code inspection](results/code-shape.json) verifies that the generic AOT loop
retains an indirect call; the guarded hot loops contain direct arithmetic with
ordered additions, and the fallback retains its indirect call. The scoring call
also remains inside the timed batch loop. The 4x result does not come from moving
the repeated computation outside that loop.

The guarded executable adds **400 bytes to `.text`**. Both ELF files occupy
96,432 bytes because of section alignment. Raw program IR grows from 34,765 to
39,444 bytes. Median warm AOT build times were 0.902 s and 0.964 s; the three-pair
ranges overlap. First runtime-cache construction took 10.76 s and is recorded
separately from all warm compilation and execution measurements.

Separate GC-instrumented squared-error runs report the same **2.0 MiB peak managed
heap** and zero collections for both variants. Those runs are excluded from timing
samples; this is the runtime's managed-heap counter, not resident process memory.

## Reproduce

Use the repository's pinned CPython and an available LLVM 18 toolchain on Linux.
The controller uses the first available CPU unless `--cpu` selects another.

```sh
make
python3.13 examples/guarded_score/bench.py --compiler ./pystachy \
  --smoke --keep build/guarded-score-smoke --json build/guarded-score-smoke.json
python3.13 examples/guarded_score/bench.py --compiler ./pystachy --jit all \
  --keep build/guarded-score-full --json build/guarded-score-full.json
```

Each `--keep` directory must be new. It retains generated entry points, AOT
executables, raw IR and a private runtime cache. `--cases`, `--size`, `--batches`
and `--samples` allow smaller investigations. The report records actual known-target
fractions, commands, sample times, source/tool/binary hashes and compiler settings.
`--smoke` validates outputs and deliberately emits no speedup summary. A failed or
interrupted run leaves an incomplete report.

The [differential fixture](../../tests/programs/apps/guarded_score.py) checks
known targets, unknown functions, distinct closure environments, bound methods,
changing targets, empty/singleton/nonfinite values, signed zero, summation order,
length errors, callback exceptions and list growth/shrinkage. It passes JIT/AOT
normally, under program GC stress and with compiler optimizations disabled.

```sh
make test FILES="tests/programs/apps/guarded_score.py"
PYSTACHY_GC_STRESS_PROGRAM=1 make test FILES="tests/programs/apps/guarded_score.py"
PYSTACHY_OPT=-all make test FILES="tests/programs/apps/guarded_score.py"
```

[Validation details](results/validation.json) include the fresh compiler/runtime
fixed points, syntax/lint checks, initial fixture/setup corrections and unrun full
verification. This remains a draft experiment. A general compiler transformation
should follow only after choosing a real application boundary with comparable
callback time share and a bounded specialization budget.
