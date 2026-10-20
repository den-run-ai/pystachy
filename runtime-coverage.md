## Native runtime coverage

Commit `8990e41776e8e74f57812120f81ec3e897065eda`: lines **94.8%** (4268 of 4503) and branches **86.6%** (4378 of 5056) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 95.6%, regions 92.2%. `pys_init` ran 3058 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5007 passed, 0 failed | 924 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 103 passed, 0 failed | 50 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 43 | 69.7% | 100.0% | 83.9% |
| `runtime.c` | 3667 | 107 | 97.1% | 4520 | 522 | 88.5% | 97.2% | 93.1% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 4503 | 235 | **94.8%** | 5056 | 678 | **86.6%** | 95.6% | 92.2% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 76 | 311 | 97.1% | 260 | 89.2% | 31 | 96.8% |
| strings | 553 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1115 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1685 | 415 | 97.6% | 706 | 89.8% | 48 | 95.8% |
| lists | 2189 | 465 | 99.6% | 620 | 91.8% | 72 | 97.2% |
| dicts: CPython's compact ordered layout | 2737 | 238 | 100.0% | 286 | 94.8% | 66 | 100.0% |
| sets: CPython's setobject.c | 3078 | 280 | 100.0% | 342 | 96.2% | 58 | 100.0% |
| formatting: f"{x:spec}" | 3422 | 60 | 100.0% | 138 | 90.6% | 5 | 100.0% |
| I/O and process | 3495 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 4151 | 307 | 92.8% | 350 | 73.7% | 60 | 98.3% |
| the time module: clocks and sleep | 4600 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 4619 | 67 | 86.6% | 52 | 78.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 4693 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 4968 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5067 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
