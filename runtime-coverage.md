## Native runtime coverage

Commit `3cf23d20357be84bf731090112cdb89df0749cb4`: lines **95.0%** (7725 of 8129) and branches **85.0%** (8300 of 9766) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.2%, regions 91.8%. `pys_init` ran 5691 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 7924 passed, 0 failed | 2194 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 117 s |

### Changed since d58034c1ca588c90363b8deb3b3c633b1cc90c47 (merge base `d58034c1ca58`)

Changed lines of code: 5 of 5 run (100.0%); their branches: 9 of 10 taken (90.0%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | - | 7607 (1 of 2) |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 6810 | 275 | 96.0% | 8714 | 1272 | 85.4% | 97.0% | 91.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8129 | 404 | **95.0%** | 9766 | 1466 | **85.0%** | 96.2% | 91.8% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 144 | 76 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 375 | 415 | 94.0% | 352 | 81.5% | 44 | 97.7% |
| strings | 911 | 497 | 99.0% | 694 | 93.9% | 73 | 97.3% |
| arithmetic with Python semantics | 1550 | 61 | 100.0% | 96 | 96.9% | 10 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1614 | 633 | 98.1% | 626 | 90.7% | 98 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2504 | 582 | 97.8% | 1032 | 86.3% | 66 | 97.0% |
| lists | 3235 | 826 | 99.2% | 1090 | 86.4% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 4222 | 488 | 99.8% | 616 | 92.7% | 105 | 100.0% |
| sets: CPython's setobject.c | 4893 | 70 | 100.0% | 98 | 94.9% | 12 | 100.0% |
| dynamic values | 5003 | 1263 | 97.6% | 1700 | 90.6% | 179 | 99.4% |
| formatting: f"{x:spec}" | 6531 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6610 | 1018 | 88.0% | 1294 | 74.1% | 129 | 88.4% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 7916 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 8385 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8445 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8525 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8801 | 301 | 93.0% | 402 | 67.4% | 34 | 97.1% |
| tables | 9143 | 92 | 98.9% | 102 | 83.3% | 17 | 94.1% |
