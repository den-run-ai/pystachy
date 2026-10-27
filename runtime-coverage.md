## Native runtime coverage

Commit `6c81644536bebeb330d02e778da409fa61d7f3ed`: lines **95.5%** (5706 of 5977) and branches **87.2%** (6121 of 7020) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.4%, regions 92.6%. `pys_init` ran 3818 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5817 passed, 0 failed | 1213 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 108 passed, 0 failed | 63 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 11 | 97.1% | 100.0% | 98.9% |
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4779 | 141 | 97.0% | 6104 | 733 | 88.0% | 97.6% | 92.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 5977 | 271 | **95.5%** | 7020 | 899 | **87.2%** | 96.4% | 92.6% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 82 | 312 | 97.1% | 262 | 89.3% | 32 | 96.9% |
| strings | 580 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1147 | 72 | 100.0% | 118 | 94.9% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1221 | 543 | 98.9% | 546 | 93.0% | 90 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1990 | 478 | 97.3% | 832 | 89.1% | 59 | 94.9% |
| lists | 2593 | 753 | 99.5% | 948 | 88.0% | 103 | 98.1% |
| dicts: CPython's compact ordered layout | 3467 | 314 | 100.0% | 376 | 93.9% | 75 | 100.0% |
| sets: CPython's setobject.c | 3906 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 4001 | 638 | 95.9% | 914 | 90.4% | 102 | 100.0% |
| formatting: f"{x:spec}" | 4789 | 65 | 100.0% | 146 | 89.7% | 5 | 100.0% |
| I/O and process | 4867 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 5530 | 322 | 93.2% | 376 | 75.0% | 61 | 98.4% |
| the time module: clocks and sleep | 5999 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 6018 | 73 | 87.7% | 60 | 73.3% | 2 | 100.0% |
| the errno module: the platform's error numbers | 6098 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 6374 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 6474 | 66 | 98.5% | 82 | 78.0% | 13 | 92.3% |
