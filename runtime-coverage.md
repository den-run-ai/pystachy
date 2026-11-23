## Native runtime coverage

Commit `e124b71e1ef13dde1afad24bb747bb1621285262`: lines **94.5%** (8273 of 8755) and branches **83.2%** (8742 of 10502) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 90.8%. `pys_init` ran 6790 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 9348 passed, 0 failed | 2888 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 149 passed, 0 failed | 135 s |

### Changed since 4998521d28413c6e32506105f836b6db9afeb1d7 (merge base `4998521d2841`)

Changed lines of code: 371 of 388 run (95.6%); their branches: 357 of 478 taken (74.7%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | 168, 6903, 7012, 7747, 8854-8855, 8857, 8862-8865, 8868, 8908-8910, 8996, 9005 | 6924 (1 of 4), 8803 (1 of 2), 8809 (2 of 6), 8814 (2 of 6), 8815 (1 of 4), 8820 (1 of 2), 8821 (1 of 2), 8835 (1 of 2), 8839 (1 of 2), 8842 (1 of 4), 8847 (1 of 4), 8848 (1 of 2), 8850 (3 of 8), 8851 (2 of 6), 8852 (1 of 4), 8853 (1 of 8), 8854 (1 of 2), 8855 (2 of 4), 8857 (1 of 2), 8860 (1 of 2), 8863 (1 of 2), 8864 (1 of 2), 8865 (1 of 2), 8866 (1 of 4), 8867 (1 of 2), 8868 (1 of 2), 8875 (1 of 4), 8876 (1 of 2), 8888 (1 of 2), 8889 (1 of 2), 8892 (1 of 2), 8893 (1 of 6), 8897 (3 of 12), 8902 (1 of 2), 8905 (2 of 4), 8907 (5 of 10), 8915 (2 of 4), 8917 (1 of 2), 8918 (3 of 4), 8929 (2 of 4), 8931 (5 of 12), 8933 (1 of 2), 8935 (1 of 4), 8937 (1 of 6), 8938 (1 of 4), 8939 (1 of 2), 8940 (1 of 4), 8946 (1 of 2), 8953 (1 of 2), 8956 (2 of 4), 8960 (3 of 6), 8963 (1 of 2), 8966 (3 of 6), 8969 (1 of 4), 8978 (1 of 2), 8986 (1 of 2), 8988 (1 of 2), 8996 (1 of 2), 8997 (1 of 4), 9000 (1 of 8), 9011 (1 of 2), 9013 (1 of 2), 9018 (2 of 4), 9020 (1 of 2), 9023 (1 of 2), 9024 (1 of 4), 9033 (1 of 2), 9034 (2 of 4), 9036 (1 of 2), 9043 (3 of 6), 9044 (3 of 6), 9046 (2 of 4), 9049 (3 of 8), 9050 (1 of 2), 9059 (2 of 6), 9064 (1 of 4), 9072 (1 of 2), 9073 (1 of 2), 9076 (1 of 2), 9077 (1 of 2), 9078 (1 of 2), 9086 (1 of 4), 9112 (1 of 4), 9121 (1 of 6), 9126 (1 of 4) |

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
