## Native runtime coverage

Commit `06e3ad5d08514ba31fb231fe4636a962fe6578e3`: lines **95.6%** (6243 of 6527) and branches **87.5%** (6860 of 7836) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.6%, regions 92.9%. `pys_init` ran 4100 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 6104 passed, 0 failed | 1400 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 108 passed, 0 failed | 86 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 5329 | 154 | 97.1% | 6920 | 811 | 88.3% | 97.8% | 93.2% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 6527 | 284 | **95.6%** | 7836 | 976 | **87.5%** | 96.6% | 92.9% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 8 | 50.0% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 100 | 323 | 97.2% | 270 | 89.6% | 32 | 96.9% |
| strings | 616 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1183 | 72 | 100.0% | 118 | 94.9% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1257 | 554 | 98.9% | 574 | 92.2% | 93 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2054 | 521 | 97.1% | 942 | 87.5% | 62 | 96.8% |
| lists | 2712 | 783 | 99.5% | 984 | 88.9% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 3619 | 472 | 100.0% | 582 | 93.1% | 104 | 100.0% |
| sets: CPython's setobject.c | 4265 | 65 | 100.0% | 90 | 96.7% | 11 | 100.0% |
| dynamic values | 4370 | 929 | 96.4% | 1320 | 91.1% | 150 | 99.3% |
| formatting: f"{x:spec}" | 5497 | 66 | 100.0% | 154 | 88.3% | 5 | 100.0% |
| I/O and process | 5576 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 6239 | 322 | 93.2% | 376 | 75.0% | 61 | 98.4% |
| the time module: clocks and sleep | 6708 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 6727 | 73 | 87.7% | 60 | 73.3% | 2 | 100.0% |
| the errno module: the platform's error numbers | 6807 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 7083 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 7183 | 66 | 98.5% | 82 | 78.0% | 13 | 92.3% |
