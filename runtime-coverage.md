## Native runtime coverage

Commit `6f5b169bc289e31d0c0c783a01329b06c01f7e62`: lines **94.9%** (4867 of 5129) and branches **86.5%** (5138 of 5938) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.1%, regions 92.0%. `pys_init` ran 3563 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5544 passed, 0 failed | 1086 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 107 passed, 0 failed | 51 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4293 | 134 | 96.9% | 5402 | 645 | 88.1% | 97.6% | 92.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 5129 | 262 | **94.9%** | 5938 | 800 | **86.5%** | 96.1% | 92.0% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 82 | 312 | 97.1% | 262 | 89.3% | 32 | 96.9% |
| strings | 580 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1144 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1714 | 434 | 97.5% | 740 | 90.0% | 50 | 96.0% |
| lists | 2257 | 620 | 99.7% | 766 | 88.9% | 88 | 97.7% |
| dicts: CPython's compact ordered layout | 2982 | 248 | 100.0% | 302 | 94.0% | 66 | 100.0% |
| sets: CPython's setobject.c | 3340 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 3435 | 636 | 95.8% | 910 | 90.5% | 102 | 100.0% |
| formatting: f"{x:spec}" | 4221 | 65 | 100.0% | 146 | 89.7% | 5 | 100.0% |
| I/O and process | 4299 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 4962 | 322 | 93.2% | 376 | 74.7% | 61 | 98.4% |
| the time module: clocks and sleep | 5431 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 5450 | 71 | 87.3% | 56 | 76.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 5528 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 5804 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5904 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
