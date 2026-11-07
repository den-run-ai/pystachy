## Native runtime coverage

Commit `a402509c527d934c7f9e1a365df1a0dbeadb2ee9`: lines **94.8%** (7378 of 7785) and branches **84.5%** (7879 of 9326) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.1%, regions 91.2%. `pys_init` ran 4749 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 6845 passed, 0 failed | 2075 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 112 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 6466 | 278 | 95.7% | 8274 | 1253 | 84.9% | 97.0% | 91.2% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 7785 | 407 | **94.8%** | 9326 | 1447 | **84.5%** | 96.1% | 91.2% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 138 | 76 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 369 | 415 | 94.0% | 352 | 81.5% | 44 | 97.7% |
| strings | 905 | 493 | 99.0% | 686 | 93.9% | 71 | 97.2% |
| arithmetic with Python semantics | 1535 | 61 | 100.0% | 96 | 96.9% | 10 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1599 | 545 | 98.9% | 564 | 91.8% | 90 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2390 | 527 | 97.0% | 952 | 87.5% | 62 | 96.8% |
| lists | 3055 | 774 | 99.5% | 1016 | 86.2% | 103 | 98.1% |
| dicts: CPython's compact ordered layout | 3968 | 473 | 100.0% | 586 | 93.0% | 104 | 100.0% |
| sets: CPython's setobject.c | 4623 | 65 | 100.0% | 92 | 95.7% | 11 | 100.0% |
| dynamic values | 4728 | 1263 | 96.4% | 1700 | 87.4% | 179 | 98.9% |
| formatting: f"{x:spec}" | 6256 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6335 | 917 | 87.4% | 1152 | 73.0% | 118 | 89.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 7495 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 7964 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8024 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8104 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8380 | 276 | 92.4% | 364 | 65.1% | 31 | 96.8% |
| tables | 8693 | 92 | 98.9% | 102 | 83.3% | 17 | 94.1% |
