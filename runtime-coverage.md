## Native runtime coverage

Commit `de65c6fbfeb101e46f25e59f5940dd51b4cdb369`: lines **95.2%** (5167 of 5430) and branches **87.1%** (5471 of 6284) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.2%, regions 92.5%. `pys_init` ran 3665 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5655 passed, 0 failed | 1005 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 107 passed, 0 failed | 53 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 275 | 2 | 99.3% | 310 | 12 | 96.1% | 100.0% | 98.6% |
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4319 | 133 | 96.9% | 5438 | 646 | 88.1% | 97.6% | 92.9% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 5430 | 263 | **95.2%** | 6284 | 813 | **87.1%** | 96.2% | 92.5% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 82 | 312 | 97.1% | 262 | 89.3% | 32 | 96.9% |
| strings | 580 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1147 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1717 | 437 | 97.5% | 742 | 89.9% | 51 | 96.1% |
| lists | 2267 | 620 | 99.7% | 766 | 88.9% | 88 | 97.7% |
| dicts: CPython's compact ordered layout | 2992 | 271 | 100.0% | 336 | 94.3% | 69 | 100.0% |
| sets: CPython's setobject.c | 3385 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 3480 | 636 | 95.9% | 910 | 90.7% | 102 | 100.0% |
| formatting: f"{x:spec}" | 4266 | 65 | 100.0% | 146 | 89.7% | 5 | 100.0% |
| I/O and process | 4344 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 5007 | 322 | 93.2% | 376 | 74.7% | 61 | 98.4% |
| the time module: clocks and sleep | 5476 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 5495 | 71 | 87.3% | 56 | 76.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 5573 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 5849 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5949 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
