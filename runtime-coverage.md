## Native runtime coverage

Commit `f5a09d4223139d7255e31051be97fc509e1ca1fe`: lines **94.7%** (4701 of 4963) and branches **86.8%** (5000 of 5762) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 92.1%. `pys_init` ran 3462 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5438 passed, 0 failed | 1103 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 106 passed, 0 failed | 70 s |

### Changed since v0.1.0-alpha.2 (merge base `afb59cd3c32e`)

Changed lines of code: 159 of 159 run (100.0%); their branches: 234 of 252 taken (92.9%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | - | 2225 (1 of 2), 2879 (1 of 4), 2939 (1 of 6), 3319 (1 of 10), 3404 (2 of 10), 3413 (1 of 4), 3414 (1 of 2), 3458 (1 of 4), 3460 (1 of 4), 3693 (1 of 4), 3721 (1 of 6), 4058 (2 of 6), 4994 (1 of 4), 4999 (2 of 12), 5001 (1 of 2) |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4127 | 134 | 96.8% | 5226 | 607 | 88.4% | 97.5% | 93.0% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 4963 | 262 | **94.7%** | 5762 | 762 | **86.8%** | 96.0% | 92.1% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 80 | 312 | 97.1% | 262 | 89.3% | 32 | 96.9% |
| strings | 578 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1142 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1712 | 430 | 97.4% | 722 | 89.8% | 49 | 95.9% |
| lists | 2249 | 465 | 99.6% | 620 | 91.8% | 72 | 97.2% |
| dicts: CPython's compact ordered layout | 2798 | 248 | 100.0% | 302 | 94.0% | 66 | 100.0% |
| sets: CPython's setobject.c | 3156 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 3251 | 633 | 95.7% | 902 | 90.7% | 100 | 100.0% |
| formatting: f"{x:spec}" | 4032 | 65 | 100.0% | 146 | 89.7% | 5 | 100.0% |
| I/O and process | 4110 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 4773 | 322 | 93.2% | 376 | 74.7% | 61 | 98.4% |
| the time module: clocks and sleep | 5242 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 5261 | 67 | 86.6% | 52 | 78.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 5335 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 5611 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5711 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
