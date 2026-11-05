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
