## Native runtime coverage

Commit `4f936ff6b01c666f57d248c54621596eb8680afe`: lines **94.5%** (8273 of 8755) and branches **83.2%** (8742 of 10502) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 90.8%. `pys_init` ran 6838 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 9398 passed, 0 failed | 2954 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 149 passed, 0 failed | 133 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 364 | 2 | 99.5% | 390 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 7434 | 353 | 95.3% | 9440 | 1566 | 83.4% | 96.8% | 90.7% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8755 | 482 | **94.5%** | 10502 | 1760 | **83.2%** | 96.0% | 90.8% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 174 | 85 | 100.0% | 72 | 93.1% | 8 | 100.0% |
| the page heap | 438 | 443 | 94.4% | 380 | 81.6% | 46 | 97.8% |
| strings | 1042 | 479 | 98.7% | 610 | 93.9% | 73 | 97.3% |
| arithmetic with Python semantics | 1687 | 17 | 100.0% | 22 | 90.9% | 3 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1718 | 652 | 98.2% | 650 | 91.1% | 102 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2660 | 605 | 97.9% | 1086 | 87.4% | 67 | 97.0% |
| lists | 3422 | 803 | 99.1% | 1058 | 86.1% | 100 | 98.0% |
| dicts: CPython's compact ordered layout | 4392 | 502 | 99.8% | 636 | 92.6% | 106 | 100.0% |
| sets: CPython's setobject.c | 5086 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5210 | 1275 | 97.6% | 1714 | 90.8% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6755 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6834 | 773 | 93.4% | 1038 | 78.4% | 98 | 92.9% |
| child processes (lib/subprocess.py) | 7791 | 469 | 71.2% | 542 | 47.4% | 53 | 77.4% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8415 | 667 | 94.8% | 842 | 74.2% | 84 | 98.8% |
| the time module: clocks and sleep | 9277 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 9337 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 9417 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 9693 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 10036 | 118 | 99.2% | 114 | 86.0% | 23 | 95.7% |
