# Ordered row scoring measurements

Measured implementation `99ffe9bdea48455ac310a89ebbaa6bb63fa58f5c`, Linux x86-64,
LLVM 18.1.3, CPython 3.13.16. One frozen native executable; 8,192 rows x 32
values = 262,144 input floats. Five interleaved fresh-process samples per policy,
one warmup and three timed batches per process. Affinity is CPUs 0-7 with an
eight-CPU quota. This is a shared hosted machine, not an isolated performance lab.

| Requested workers | Polynomial rows | vs serial row thunk | Cheap affine rows |
|---:|---:|---:|---:|
| Direct loop | 5.868 ms | 0.96x | 0.210 ms |
| 1 | 5.640 ms | 1.00x | 0.137 ms |
| 2 | 3.295 ms | 1.71x | 0.171 ms |
| 4 | 2.095 ms | 2.69x | 0.217 ms |
| 8 | 2.570 ms | 2.19x | 0.335 ms |

Four workers improve the polynomial row thunk by 2.69x; eight workers are slower
than four on this run. The cheap affine control is 1.58x slower at four workers
than the serial row thunk, and 2.44x slower at eight. Requested workers therefore
remain explicit with a default of one; this does not establish an automatic
break-even threshold or a persistent-pool benefit.

The direct-loop policy is in the same executable and has the same scalar callback
and sequential row reductions. The primary parallel ratio uses the proven serial
row thunk to hold its generated loop and callback policy constant. Do not multiply
these ratios by #1122's callback-specialization measurements.

Timers include fresh output allocation and dispatch/join. Input construction,
complete output validation, process startup and native compilation are outside
those narrow batch timers; raw JSON records preparation and whole-process CPU/RSS
separately. Every row's 64-bit output representation agrees with an independent
CPython direct-loop oracle and the native direct loop. No partial-row witness or
numerical tolerance is used. The dedicated fixtures separately cover NaNs,
infinities, signed zeros, nonassociative sums, errors and serial fallback effects.

- [All samples, source identities and resource observations](native-2026-11-07.json)
- [Native harness smoke](smoke-2026-11-07.json)

Reproduce from this branch:

```sh
PYSTACHY_LLVM=/path/to/llvm-18/bin python3.13 bench/parallel_rows/run.py \
  --compiler 'python3.13 pystachy.py' --cpython python3.13 \
  --output /tmp/parallel-rows.json
```

Use an allowed CPU set with `taskset -c` when comparing worker counts. The measured
run used a hosted wrapper only to prepare one native executable; the timed kernels
run without CPython. The validation below uses the same frozen implementation.

## Validation

Compiler, runtime, library and workload hashes remain identical to implementation
`99ffe9bdea48455ac310a89ebbaa6bb63fa58f5c`; subsequent changes add this evidence and
documentation. [The compact validation record](validation-2026-11-07.json) retains
commands, source/toolchain identities, witness hashes, return codes and
representative raw differences. Full generated IR remains a build intermediate.

| Check | Outcome |
|---|---|
| Full native self-bootstrap | Three identical compiler IR witnesses, 836,028 lines; three identical runtime IR witnesses, 18,805 lines |
| Rebuilt native compiler | Five IR/`llvm-as` fixtures; eight JIT/AOT map/row checks; four additional row checks with collection on every program allocation |
| Fast/lint gate | 440 unit tests, mypy on 50 source files, Ruff, ShellCheck, runtime root audit and strict Clang warnings pass |
| Runtime ABI/effects | 646 entries and 70 exception classes agree |
| Exact #1088 reference, each compiler's own library | 3,978 of 4,246 cases identical; 268 differ; `make irsame` returns 2 |
| Controlled IR-only replay with identical inputs and paths | 4,239 of 4,246 identical; seven intended parallel fixtures differ; oracle returns 1 |

The raw comparison rebuilt reference
`163fe22c9bfcdb6c299bf65998cf003d151b6132` and preserves each compiler's own library.
Embedded import-error strings include absolute checkout paths, so many otherwise
identical programs differ under `build/ref/lib/` versus `lib/`. There are 88 Python
library files: 87 and `runtime.py` are byte-identical to the base; only
`lib/parallel.py` adds the row helper. Its existing `map_float` body is unchanged.

The separate shared-home replay is a diagnostic control, not an unchanged-library
compatibility result. Both compilers consume the candidate's exact library/runtime
files at the same physical paths, including the newly added row helper. It emits
IR only; no base-produced executable is linked or run against the changed worker
ABI. In this control 261 additional differences disappear. All seven remaining
cases were then reproduced individually in both library configurations:

| Cases | Count | Controlled difference |
|---|---:|---|
| Existing map, nested fallback map and map IR fixture | 3 | Only the generated internal map thunk's additional immutable width parameter |
| Dynamic-Any parallel fixture | 1 | Only an additional conservative serial row-eligibility comment |
| Ineligible row fallback fixture | 1 | Only serial eligibility comments; fallback function IR is identical |
| Pure row library and row IR fixtures | 2 | Proven native row calls and ordered reduction thunks replace serial library calls |

Removing only those explicit internal-signature/comment differences reproduces
the reference IR exactly for the first five controlled cases. The two pure row
cases intentionally introduce the native operation. The row library fixture's
results match the CPython oracle in both execution modes, including bit-pattern
checks; the smaller IR fixture pins the native call and thunk boundary.

Original-library acceptance is recorded separately: six parallel fixtures remain
accepted, and `tests/ir/parallel_rows.py` changes from a missing-`sum_rows_float`
import rejection to acceptance. The two new library programs already compile on
the base through their explicit `parallel_reference` fallback; that does not mean
the base provides the new public API. No new rejection was found.

These correctness runs shared a bounded validation budget with another checkout;
their durations are not performance measurements. No timing campaign was repeated
for this validation. Full `make verify`, full native corpus execution, the complete
GC matrix, ThreadSanitizer and macOS remain unrun on this revision. The draft does
not claim #1122/#1125 composition, external-buffer alias safety or general
shared-heap threading.
