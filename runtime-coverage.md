## Native runtime coverage

Commit `9bc02a0f06734c8f2979e8b7bc05e3009a86d263`: lines **95.2%** (7891 of 8291) and branches **85.2%** (8476 of 9944) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.3%, regions 91.9%. `pys_init` ran 6147 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 8544 passed, 0 failed | 2278 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 114 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 6972 | 271 | 96.1% | 8892 | 1274 | 85.7% | 97.2% | 92.0% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8291 | 400 | **95.2%** | 9944 | 1468 | **85.2%** | 96.3% | 91.9% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 144 | 76 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 375 | 418 | 94.0% | 358 | 81.8% | 44 | 97.7% |
| strings | 917 | 495 | 99.8% | 690 | 94.5% | 72 | 98.6% |
| arithmetic with Python semantics | 1552 | 68 | 100.0% | 104 | 95.2% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1626 | 696 | 98.3% | 688 | 91.4% | 108 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2611 | 603 | 97.8% | 1078 | 87.2% | 67 | 97.0% |
| lists | 3369 | 826 | 99.2% | 1090 | 86.4% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 4356 | 492 | 99.8% | 626 | 92.7% | 105 | 100.0% |
| sets: CPython's setobject.c | 5034 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5158 | 1275 | 97.6% | 1714 | 90.7% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6703 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6782 | 1035 | 88.2% | 1304 | 74.2% | 133 | 88.7% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8105 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 8574 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8634 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8714 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8990 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 9333 | 117 | 99.1% | 116 | 84.5% | 23 | 95.7% |
