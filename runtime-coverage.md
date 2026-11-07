## Native runtime coverage

Commit `54ad139a378b2fe8761a44cedf7ff9a317f1d300`: lines **95.5%** (7094 of 7428) and branches **85.6%** (7687 of 8982) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.3%, regions 92.1%. `pys_init` ran 4552 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 6654 passed, 0 failed | 1668 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 116 passed, 0 failed | 99 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 246 | 12 | 95.1% | 272 | 105 | 61.4% | 95.2% | 81.4% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 6220 | 210 | 96.6% | 8058 | 1131 | 86.0% | 97.3% | 92.1% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 7428 | 334 | **95.5%** | 8982 | 1295 | **85.6%** | 96.3% | 92.1% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 8 | 50.0% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 108 | 76 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 339 | 410 | 93.9% | 352 | 81.5% | 44 | 97.7% |
| strings | 870 | 488 | 99.0% | 682 | 93.8% | 72 | 97.2% |
| arithmetic with Python semantics | 1486 | 72 | 100.0% | 118 | 95.8% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1560 | 554 | 98.9% | 576 | 92.0% | 93 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2357 | 521 | 97.1% | 944 | 87.5% | 62 | 96.8% |
| lists | 3015 | 788 | 99.5% | 1048 | 86.6% | 107 | 98.1% |
| dicts: CPython's compact ordered layout | 3936 | 473 | 100.0% | 586 | 93.0% | 104 | 100.0% |
| sets: CPython's setobject.c | 4591 | 65 | 100.0% | 90 | 96.7% | 11 | 100.0% |
| dynamic values | 4696 | 1111 | 97.0% | 1544 | 89.8% | 171 | 99.4% |
| formatting: f"{x:spec}" | 6048 | 66 | 100.0% | 154 | 88.3% | 5 | 100.0% |
| I/O and process | 6127 | 831 | 92.5% | 1064 | 76.7% | 111 | 90.1% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 7173 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 7642 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 7702 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 7782 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8058 | 276 | 92.4% | 364 | 65.1% | 31 | 96.8% |
| tables | 8371 | 66 | 98.5% | 82 | 78.0% | 13 | 92.3% |
