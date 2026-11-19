## Native runtime coverage

Commit `d35417c967f25ac699bb713f4c796dfaf2c57fac`: lines **94.5%** (8022 of 8486) and branches **84.0%** (8567 of 10200) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 90.9%. `pys_init` ran 6317 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 8784 passed, 0 failed | 2517 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 114 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 7167 | 335 | 95.3% | 9148 | 1439 | 84.3% | 96.8% | 90.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8486 | 464 | **94.5%** | 10200 | 1633 | **84.0%** | 96.0% | 90.9% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 147 | 77 | 100.0% | 72 | 94.4% | 7 | 100.0% |
| the page heap | 390 | 418 | 94.0% | 358 | 81.8% | 44 | 97.7% |
| strings | 932 | 495 | 99.8% | 690 | 94.5% | 72 | 98.6% |
| arithmetic with Python semantics | 1567 | 68 | 100.0% | 104 | 95.2% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1641 | 696 | 98.3% | 688 | 91.4% | 108 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2626 | 603 | 97.8% | 1078 | 87.2% | 67 | 97.0% |
| lists | 3384 | 826 | 99.2% | 1090 | 86.4% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 4371 | 492 | 99.8% | 626 | 92.7% | 105 | 100.0% |
| sets: CPython's setobject.c | 5049 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5173 | 1275 | 97.6% | 1714 | 90.7% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6718 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6797 | 770 | 93.4% | 1040 | 78.2% | 97 | 92.8% |
| child processes (lib/subprocess.py) | 7748 | 461 | 70.7% | 520 | 47.1% | 52 | 76.9% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8357 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 8826 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8886 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8966 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 9242 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 9585 | 117 | 99.1% | 116 | 84.5% | 23 | 95.7% |
