## Native runtime coverage

Commit `870bfa154f940026a7135f5c285fb0df7148ee88`: lines **94.0%** (4550 of 4838) and branches **85.7%** (4776 of 5572) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 95.9%, regions 91.2%. `pys_init` ran 3122 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 5097 passed, 0 failed | 1003 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 106 passed, 0 failed | 68 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 4002 | 160 | 96.0% | 5036 | 641 | 87.3% | 97.4% | 92.0% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 4838 | 288 | **94.0%** | 5572 | 796 | **85.7%** | 95.9% | 91.2% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 3 | 100.0% | 0 | - | 0 | - |
| memory: conservative mark-and-sweep garbage collector | 76 | 311 | 97.1% | 260 | 89.2% | 31 | 96.8% |
| strings | 553 | 447 | 98.9% | 650 | 93.5% | 69 | 97.1% |
| arithmetic with Python semantics | 1115 | 376 | 99.5% | 318 | 96.5% | 76 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 1685 | 420 | 97.1% | 716 | 89.7% | 48 | 95.8% |
| lists | 2206 | 465 | 99.6% | 620 | 91.8% | 72 | 97.2% |
| dicts: CPython's compact ordered layout | 2754 | 240 | 100.0% | 292 | 94.9% | 66 | 100.0% |
| sets: CPython's setobject.c | 3097 | 64 | 100.0% | 78 | 94.9% | 11 | 100.0% |
| dynamic values | 3192 | 546 | 90.5% | 762 | 83.5% | 88 | 100.0% |
| formatting: f"{x:spec}" | 3837 | 61 | 100.0% | 140 | 90.7% | 5 | 100.0% |
| I/O and process | 3911 | 541 | 93.5% | 678 | 78.8% | 86 | 93.0% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 4567 | 307 | 92.8% | 350 | 73.7% | 60 | 98.3% |
| the time module: clocks and sleep | 5016 | 17 | 94.1% | 16 | 43.8% | 10 | 90.0% |
| select: a POSIX integer-descriptor subset | 5035 | 67 | 86.6% | 52 | 78.8% | 2 | 100.0% |
| the errno module: the platform's error numbers | 5109 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 5384 | 96 | 90.6% | 130 | 67.7% | 8 | 100.0% |
| tables | 5483 | 65 | 98.5% | 82 | 78.0% | 13 | 92.3% |
