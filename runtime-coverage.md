## Native runtime coverage

Commit `0536d1a8e009ed59fb6485dd09f2fdd4661bd68a`: lines **94.5%** (4661 of 4930) and branches **86.5%** (4948 of 5722) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 91.9%. `pys_init` ran 3252 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5241 passed, 0 failed | 902 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 106 passed, 0 failed | 46 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4094 | 141 | 96.6% | 5186 | 619 | 88.1% | 97.5% | 92.7% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 4930 | 269 | **94.5%** | 5722 | 774 | **86.5%** | 96.0% | 91.9% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 76 | 312 | 97.1% | 262 | 89.3% | 32 | 96.9% |
| strings | 560 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1122 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1692 | 430 | 97.4% | 722 | 89.8% | 49 | 95.9% |
| lists | 2228 | 465 | 99.6% | 620 | 91.8% | 72 | 97.2% |
| dicts: CPython's compact ordered layout | 2776 | 244 | 100.0% | 300 | 94.0% | 66 | 100.0% |
| sets: CPython's setobject.c | 3128 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 3223 | 604 | 94.4% | 864 | 88.9% | 98 | 100.0% |
| formatting: f"{x:spec}" | 3961 | 65 | 100.0% | 146 | 89.7% | 5 | 100.0% |
| I/O and process | 4039 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 4695 | 322 | 93.2% | 376 | 74.7% | 61 | 98.4% |
| the time module: clocks and sleep | 5164 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 5183 | 67 | 86.6% | 52 | 78.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 5257 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 5532 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5631 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
