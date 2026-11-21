## Native runtime coverage

Commit `4998521d28413c6e32506105f836b6db9afeb1d7`: lines **94.4%** (7949 of 8418) and branches **83.7%** (8396 of 10036) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 95.9%, regions 90.8%. `pys_init` ran 6656 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 9200 passed, 0 failed | 2282 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 149 passed, 0 failed | 164 s |

### Changed since 41dffd36201e6655c2603b28a458300c864237f7 (merge base `41dffd36201e`)

Changed lines of code: 64 of 70 run (91.4%); their branches: 81 of 112 taken (72.3%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | 1031, 1041-1044, 7801 | 365 (1 of 2), 922 (3 of 6), 929 (1 of 2), 931 (3 of 4), 932 (1 of 2), 950 (1 of 6), 953 (5 of 6), 8147 (1 of 8), 8149 (1 of 2), 8152 (1 of 2), 8165 (4 of 8), 8166 (4 of 10), 8167 (3 of 6), 8507 (2 of 6) |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 364 | 2 | 99.5% | 390 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 7097 | 340 | 95.2% | 8974 | 1446 | 83.9% | 96.7% | 90.7% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8418 | 469 | **94.4%** | 10036 | 1640 | **83.7%** | 95.9% | 90.8% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 162 | 85 | 100.0% | 74 | 93.2% | 8 | 100.0% |
| the page heap | 425 | 440 | 94.3% | 376 | 81.4% | 46 | 97.8% |
| strings | 1017 | 478 | 98.7% | 606 | 93.9% | 73 | 97.3% |
| arithmetic with Python semantics | 1660 | 17 | 100.0% | 22 | 90.9% | 3 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1691 | 652 | 98.2% | 650 | 91.1% | 102 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2633 | 604 | 97.8% | 1082 | 87.3% | 67 | 97.0% |
| lists | 3394 | 803 | 99.1% | 1058 | 86.1% | 100 | 98.0% |
| dicts: CPython's compact ordered layout | 4364 | 502 | 99.8% | 636 | 92.6% | 106 | 100.0% |
| sets: CPython's setobject.c | 5058 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5182 | 1275 | 97.6% | 1714 | 90.8% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6727 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6806 | 770 | 93.4% | 1036 | 78.4% | 97 | 92.8% |
| child processes (lib/subprocess.py) | 7757 | 471 | 71.3% | 542 | 47.4% | 53 | 77.4% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8383 | 334 | 93.4% | 388 | 75.0% | 63 | 98.4% |
| the time module: clocks and sleep | 8868 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8928 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 9008 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 9284 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 9627 | 118 | 99.2% | 114 | 86.0% | 23 | 95.7% |
