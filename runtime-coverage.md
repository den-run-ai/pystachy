## Native runtime coverage

Commit `abb5159c23ac0e259b5e32f79c5e2ebacc3ac47c`: lines **95.4%** (6331 of 6634) and branches **87.0%** (6954 of 7996) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.1%, regions 92.8%. `pys_init` ran 4222 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 6226 passed, 0 failed | 1375 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 111 passed, 0 failed | 94 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 5436 | 173 | 96.8% | 7080 | 877 | 87.6% | 97.2% | 93.0% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 6634 | 303 | **95.4%** | 7996 | 1042 | **87.0%** | 96.1% | 92.8% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 8 | 50.0% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 105 | 333 | 97.3% | 278 | 88.8% | 34 | 97.1% |
| strings | 641 | 478 | 99.0% | 680 | 93.7% | 71 | 97.2% |
| arithmetic with Python semantics | 1247 | 72 | 100.0% | 118 | 94.9% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1321 | 554 | 98.9% | 576 | 92.0% | 93 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2118 | 521 | 97.1% | 944 | 87.5% | 62 | 96.8% |
| lists | 2776 | 783 | 99.5% | 1046 | 86.2% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 3690 | 473 | 100.0% | 586 | 93.0% | 104 | 100.0% |
| sets: CPython's setobject.c | 4345 | 65 | 100.0% | 90 | 96.7% | 11 | 100.0% |
| dynamic values | 4450 | 929 | 96.4% | 1320 | 91.1% | 150 | 99.3% |
| formatting: f"{x:spec}" | 5577 | 66 | 100.0% | 154 | 88.3% | 5 | 100.0% |
| I/O and process | 5656 | 609 | 91.1% | 728 | 77.1% | 96 | 88.5% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 6452 | 322 | 93.2% | 376 | 75.0% | 61 | 98.4% |
| the time module: clocks and sleep | 6921 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 6940 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 7020 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 7296 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 7396 | 66 | 98.5% | 82 | 78.0% | 13 | 92.3% |
