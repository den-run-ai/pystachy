## Native runtime coverage

Commit `3da553ee569d519031508f2177cdb04f9f436991`: lines **95.0%** (7720 of 8124) and branches **85.0%** (8291 of 9756) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.1%, regions 91.8%. `pys_init` ran 5477 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 7660 passed, 0 failed | 2139 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 112 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 6805 | 275 | 96.0% | 8704 | 1271 | 85.4% | 97.0% | 91.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8124 | 404 | **95.0%** | 9756 | 1465 | **85.0%** | 96.1% | 91.8% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 143 | 76 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 374 | 415 | 94.0% | 352 | 81.5% | 44 | 97.7% |
| strings | 910 | 497 | 99.0% | 694 | 93.9% | 73 | 97.3% |
| arithmetic with Python semantics | 1549 | 61 | 100.0% | 96 | 96.9% | 10 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1613 | 633 | 98.1% | 626 | 90.7% | 98 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2503 | 582 | 97.8% | 1032 | 86.3% | 66 | 97.0% |
| lists | 3234 | 826 | 99.2% | 1090 | 86.4% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 4221 | 488 | 99.8% | 616 | 92.7% | 105 | 100.0% |
| sets: CPython's setobject.c | 4892 | 70 | 100.0% | 98 | 94.9% | 12 | 100.0% |
| dynamic values | 5002 | 1263 | 97.6% | 1700 | 90.6% | 179 | 99.4% |
| formatting: f"{x:spec}" | 6530 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6609 | 1013 | 88.0% | 1284 | 74.0% | 128 | 88.3% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 7910 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 8379 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8439 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8519 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8795 | 301 | 93.0% | 402 | 67.4% | 34 | 97.1% |
| tables | 9137 | 92 | 98.9% | 102 | 83.3% | 17 | 94.1% |
