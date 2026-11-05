# Native float-map benchmark

Two bounded workloads for the experimental [`parallel.map_float`](../../lib/parallel.py)
API. See the [concurrency contract](../../docs/concurrency.md) for supported kernels
and sequential fallback behavior.

| Kernel | Work per element | Purpose |
|---|---|---|
| `score` | Degree-32 polynomial, 32 multiplies and 32 adds | Synthetic batch scoring with enough arithmetic to test scaling |
| `affine` | One multiply and one add | Cheap control where allocation, memory traffic and dispatch can dominate |

Both use ordinary Python syntax, the same scalar function for every variant, and
a fresh ordered `list[float]` result. The polynomial is written out because this
prototype does not parallelize worker loops. These are microbenchmarks, not a
measurement of a complete RL pipeline or compiler workload.

## Reproduce

From the repository root, after building the prototype:

```sh
python3.13 bench/parallel/run.py --compiler ./pystachy --cpython python3.13 \
  --n 262144 --samples 5 --batches 3 --jit --output build/parallel.json
```

`--compiler 'python3.13 pystachy.py'` uses the hosted compiler. For a quick check,
use `--smoke --output build/parallel-smoke.json`; add `--reference-only` to check
the CPython fallback without building. Small smoke inputs exercise correctness,
not native thread scaling. Native scheduling needs at least 32,768 elements for
two workers, 65,536 for four and 131,072 for eight. To bind CPUs, run the command
under `taskset -c` with a set containing enough CPUs; one CPU cannot show scaling.

## Reading results

The runner checks CPython first, requires both native worker thunks in emitted
IR, and checks every output element before accepting timings. Binary-exact inputs
repeat every 1,024 elements; the complete distinct-input witness and ordered
checksum must agree with CPython, including float bit patterns. Input mutation,
length changes and reused result objects fail the check.

Samples interleave CPython, the ordinary native `for` loop and native
`map_float` with 1/2/4/8 requested workers. Compare **map1 against mapN** for
parallel scaling; serial-loop against map1 also includes specialization and
allocation differences. Timers include output allocation, worker dispatch/join
and scoring, but exclude input generation, validation and checksums. Each batch
is checked outside its timer. Medians summarize each process's batch medians;
raw samples remain in the JSON. There are no timing gates.

AOT build wall time uses a private, initially empty runtime cache. Optional JIT
startup uses empty inputs and the warmed runtime cache, and includes frontend,
LLVM and process startup; it is separate from kernel time. JIT also checks one
full-size batch per kernel. The report records source/binary hashes, command,
CPU affinity/quota and host load. Other `PYSTACHY_*` overrides are cleared except
`PYSTACHY_LLVM`. Shared-host results need repetition before drawing conclusions.

## Recorded result

[Linux x86-64 samples](results/linux-x86_64.json), measured source
[`afa9529`](https://github.com/den-run-ai/pystachy/commit/afa952955c2c39326aa2800d0dd4f56225e35994):
AMD EPYC 9V74, eight-CPU cgroup quota, LLVM 18.1.3 and CPython 3.13.16.
262,144 values, five interleaved process samples, three timed batches after one
warmup. All outputs matched the CPython oracle; JIT and AOT both passed.

| Workload | Native for loop | Map 1 | Map 2 | Map 4 | Map 8 |
|---|---:|---:|---:|---:|---:|
| Polynomial scoring | 5.742 ms | 2.879 ms | 1.904 ms | 1.053 ms | 0.826 ms |
| Cheap affine control | 0.797 ms | 0.111 ms | 0.217 ms | 0.248 ms | 0.352 ms |

Scoring gained **2.73x at four workers**, **3.48x at eight**, relative to the same
native map at one worker. The affine map became slower with more workers: dispatch
and memory costs dominate. This supports explicit worker selection and a serial
default. The serial-loop/map1 difference includes direct-call specialization and
preallocation; it is not threading speedup. These are synthetic kernel results,
not a compiler or production application speedup.

Cold AOT build including the runtime cache was 8.479 s. The first JIT process
took 5.465 s while materializing its native runtime; four later empty-input
processes took 0.130-0.151 s. Every JIT process still compiles the source.

Local safety evidence: 22 proof/driver tests; six native JIT/AOT differential
checks, repeated with per-allocation GC; 34 C probe maps including real concurrent
entry, partial launch failures and GC; SIGINT delivered after all joins;
ThreadSanitizer clean for the C probe and the four actual generated worker kernels
with per-allocation GC. The compiler/runtime table also passed its 645-entry
ABI/effect check. Three-stage self-hosting reached identical compiler and runtime
IR; both new IR probes passed the verifier and LLVM assembler. Mypy accepted all
50 compiler source files.

All 4,247 existing corpus inputs produced identical IR, diagnostics and exit status
against baseline `45fda27`. Both compilers used one library path after checking
that pre-existing library sources were unchanged. An initial separate-checkout run
reported 261 differences from embedded absolute library paths. The compiler's
changed own source and the new fixtures were validated separately as described above.

The first CI run caught module-layering violations: worker ABI text and the
runtime-declaration predicate lived outside the backend. They now live in
`lower_module.py`; the typed proof returns kernel symbols and diagnostic messages.
All 182 typed-IR tests and the remaining fast unit suites pass. Eight representative
programs, including this benchmark, retain byte-identical IR after that relocation.
The measurements above remain pinned to their original source commit.

Run `make parallelprobe` and
`python3 -m unittest discover -s tools -p test_parallel.py` for the focused controls.
Full execution verification and macOS testing remain requirements before merging.

## Related implementations

| Project | Relevant practice or pitfall |
|---|---|
| [Codon](https://docs.exaloop.io/parallel/multithreading/) | Explicit parallel loops use OpenMP; shared container mutation still needs synchronization. Its loop-decorator syntax differs from CPython. |
| [Numba](https://numba.readthedocs.io/en/stable/user/parallel.html) | `parallel=True` and `prange` select parallel work. Iteration independence and supported reductions are required; some races escape detection. |
| [Cython](https://cython.readthedocs.io/en/latest/src/userguide/nogil.html) | Declaring a function `nogil` does not release the GIL or create threads. Exception checking can introduce repeated GIL acquisition. |
| [mypyc](https://mypyc.readthedocs.io/en/stable/differences_from_python.html#free-threading) | Supports free-threaded CPython, with documented atomicity and memory-safety boundaries; synchronization still matters. |
| [Mojo](https://mojolang.org/docs/std/runtime/initialize_runtime/) | Shared-library hosts initialize the parallel runtime explicitly. [Ownership](https://mojolang.org/docs/manual/pointers/) does not synchronize shared pointees. |

[LLVM's memory model](https://llvm.org/docs/LangRef.html#memory-model-for-concurrent-operations)
supports threads created by platform runtimes; it has no thread-spawn instruction.
This prototype uses a synchronous runtime call and disjoint output slots.
