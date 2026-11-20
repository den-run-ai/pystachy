## Native runtime coverage

Commit `37512410e050da72b97b927f7d69830ed8377faa`: lines **94.5%** (8046 of 8510) and branches **84.1%** (8577 of 10200) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 91.0%. `pys_init` ran 6348 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 8818 passed, 0 failed | 2324 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 149 passed, 0 failed | 159 s |

### Changed since 817c9cd9e8a638232a65adb916af39735e503282 (merge base `817c9cd9e8a6`)

Changed lines of code: 31 of 31 run (100.0%); their branches: 37 of 40 taken (92.5%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | - | 321 (1 of 2), 330 (1 of 2), 494 (1 of 2) |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 7191 | 335 | 95.3% | 9148 | 1429 | 84.4% | 96.8% | 90.9% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8510 | 464 | **94.5%** | 10200 | 1623 | **84.1%** | 96.0% | 91.0% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 9 | 55.6% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 147 | 85 | 100.0% | 74 | 93.2% | 8 | 100.0% |
| the page heap | 401 | 422 | 94.1% | 352 | 82.4% | 44 | 97.7% |
| strings | 947 | 495 | 99.8% | 690 | 94.5% | 72 | 98.6% |
| arithmetic with Python semantics | 1582 | 68 | 100.0% | 104 | 95.2% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1656 | 696 | 98.3% | 688 | 91.4% | 108 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2641 | 604 | 97.8% | 1082 | 87.3% | 67 | 97.0% |
| lists | 3402 | 826 | 99.2% | 1090 | 86.4% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 4389 | 502 | 99.8% | 636 | 92.6% | 106 | 100.0% |
| sets: CPython's setobject.c | 5083 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5207 | 1275 | 97.6% | 1714 | 90.8% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6752 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6831 | 770 | 93.4% | 1036 | 78.3% | 97 | 92.8% |
| child processes (lib/subprocess.py) | 7782 | 461 | 70.7% | 520 | 47.1% | 52 | 76.9% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8391 | 322 | 93.2% | 372 | 75.5% | 61 | 98.4% |
| the time module: clocks and sleep | 8860 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8920 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 9000 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 9276 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 9619 | 118 | 99.2% | 114 | 86.0% | 23 | 95.7% |
