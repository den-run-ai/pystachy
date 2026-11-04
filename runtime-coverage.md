## Native runtime coverage

Commit `4b995516b792a820907506b234dc679601be3343`: lines **95.4%** (7063 of 7403) and branches **85.5%** (7665 of 8964) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.3%, regions 92.0%. `pys_init` ran 4528 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 6619 passed, 0 failed | 1991 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 115 passed, 0 failed | 106 s |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 236 | 18 | 92.4% | 264 | 105 | 60.2% | 95.2% | 80.5% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 42 | 70.4% | 100.0% | 83.9% |
| `runtime.c` | 6205 | 210 | 96.6% | 8048 | 1134 | 85.9% | 97.3% | 92.1% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 7403 | 340 | **95.4%** | 8964 | 1299 | **85.5%** | 96.3% | 92.0% |

`runtime.c` by section (the comments that start them):

| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |
|---|---:|---:|---:|---:|---:|---:|---:|
| (declarations) | 1 | 8 | 50.0% | 2 | 50.0% | 2 | 50.0% |
| memory: conservative mark-and-sweep garbage collector | 108 | 76 | 100.0% | 72 | 93.1% | 7 | 100.0% |
| the page heap | 339 | 410 | 93.9% | 352 | 81.5% | 44 | 97.7% |
| strings | 870 | 481 | 99.0% | 680 | 93.7% | 71 | 97.2% |
| arithmetic with Python semantics | 1479 | 72 | 100.0% | 118 | 94.9% | 11 | 100.0% |
| promoting ints (# pystachy: python-int, docs/python-int.md) | 1553 | 554 | 98.9% | 576 | 92.0% | 93 | 100.0% |
| generic repr / equality / ordering driven by a type descriptor | 2350 | 521 | 97.1% | 944 | 87.5% | 62 | 96.8% |
| lists | 3008 | 783 | 99.5% | 1046 | 86.6% | 106 | 98.1% |
| dicts: CPython's compact ordered layout | 3922 | 473 | 100.0% | 586 | 93.0% | 104 | 100.0% |
| sets: CPython's setobject.c | 4577 | 65 | 100.0% | 90 | 96.7% | 11 | 100.0% |
| dynamic values | 4682 | 1108 | 97.0% | 1538 | 89.8% | 170 | 99.4% |
| formatting: f"{x:spec}" | 6029 | 66 | 100.0% | 154 | 88.3% | 5 | 100.0% |
| I/O and process | 6108 | 831 | 92.5% | 1064 | 76.7% | 111 | 90.1% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 7151 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 7620 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 7680 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 7760 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 8036 | 276 | 92.4% | 364 | 65.1% | 31 | 96.8% |
| tables | 8349 | 66 | 98.5% | 82 | 78.0% | 13 | 92.3% |
