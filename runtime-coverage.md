## Native runtime coverage

Commit `817c9cd9e8a638232a65adb916af39735e503282`: lines **94.5%** (8032 of 8496) and branches **84.0%** (8576 of 10210) of `runtime.c` (with the `ryu/` and `mpz/` files it includes), `pyembed.c` and `pyext.c`, as clang's source-based coverage counts them; functions 96.0%, regions 90.9%. `pys_init` ran 6327 times: the program runs whose profiles were written.
Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy, is not measured, nor are the C probes. The compiler's own coverage is the [hosted compiler coverage](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md).

| Suite | Runs | Checks | Time |
|---|---|---|---:|
| corpus | `tests/run.sh`, JIT and AOT (6 shards) | 8794 passed, 0 failed | 2105 s |
| ffi | `tests/ffi/run.sh`, AOT and extension modules | 148 passed, 0 failed | 111 s |

### Changed since d58034c1ca588c90363b8deb3b3c633b1cc90c47 (merge base `d58034c1ca58`)

Changed lines of code: 356 of 420 run (84.8%); their branches: 332 of 512 taken (64.8%).

| File | Lines not run | Branches not taken |
|---|---|---|
| `runtime.c` | 7794-7797, 7802-7827, 7834-7835, 7837-7839, 7841-7859, 7891-7892, 7901-7905, 7965-7967 | 3073 (3 of 14), 4460 (1 of 6), 4461 (1 of 2), 4560 (1 of 2), 5147 (1 of 2), 6591 (1 of 2), 7731 (2 of 4), 7773 (1 of 2), 7775 (2 of 4), 7776 (1 of 2), 7777 (1 of 2), 7783 (1 of 2), 7790 (3 of 4), 7791 (1 of 2), 7796 (4 of 4), 7804 (2 of 2), 7807 (2 of 2), 7809 (8 of 8), 7810 (2 of 2), 7822 (6 of 6), 7823 (2 of 2), 7825 (6 of 6), 7826 (4 of 4), 7837 (6 of 6), 7838 (4 of 4), 7839 (4 of 4), 7841 (8 of 8), 7842 (8 of 8), 7843 (8 of 8), 7844 (4 of 4), 7845 (2 of 2), 7846 (4 of 4), 7848 (2 of 2), 7850 (2 of 2), 7851 (2 of 2), 7852 (6 of 6), 7854 (2 of 2), 7857 (4 of 4), 7874 (1 of 2), 7875 (3 of 10), 7876 (1 of 2), 7880 (1 of 4), 7882 (1 of 2), 7884 (1 of 2), 7889 (2 of 6), 7890 (1 of 2), 7900 (1 of 2), 7901 (2 of 2), 7903 (2 of 2), 7909 (1 of 2), 7914 (5 of 8), 7919 (3 of 4), 7930 (3 of 6), 7931 (3 of 4), 7936 (1 of 2), 7937 (1 of 2), 7938 (1 of 2), 7942 (4 of 6), 7943 (1 of 2), 7947 (2 of 4), 7950 (1 of 4), 7954 (1 of 2), 7963 (1 of 2), 7964 (1 of 2), 7965 (2 of 2), 7966 (4 of 4), 7996 (1 of 2), 7997 (1 of 2), 8064 (1 of 2), 9266 (1 of 4), 10858 (1 of 4), 10871 (1 of 2), 10935 (1 of 2) |

| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mpz/mpz.c` | 362 | 2 | 99.4% | 380 | 10 | 97.4% | 100.0% | 99.1% |
| `pyembed.c` | 357 | 17 | 95.2% | 400 | 135 | 66.2% | 96.9% | 84.9% |
| `pyext.c` | 128 | 10 | 92.2% | 142 | 41 | 71.1% | 100.0% | 83.9% |
| `runtime.c` | 7177 | 335 | 95.3% | 9158 | 1440 | 84.3% | 96.8% | 90.8% |
| `ryu/common.h` | 66 | 46 | 30.3% | 6 | 6 | 0.0% | 44.4% | 23.5% |
| `ryu/d2s.c` | 284 | 13 | 95.4% | 118 | 2 | 98.3% | 71.4% | 98.3% |
| `ryu/d2s_intrinsics.h` | 84 | 41 | 51.2% | 2 | 0 | 100.0% | 69.2% | 76.5% |
| `ryu/d2s_small_table.h` | 38 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| **Total** | 8496 | 464 | **94.5%** | 10210 | 1634 | **84.0%** | 96.0% | 90.9% |

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
| dicts: CPython's compact ordered layout | 4371 | 502 | 99.8% | 636 | 92.6% | 106 | 100.0% |
| sets: CPython's setobject.c | 5065 | 82 | 100.0% | 106 | 95.3% | 13 | 100.0% |
| dynamic values | 5189 | 1275 | 97.6% | 1714 | 90.7% | 180 | 99.4% |
| formatting: f"{x:spec}" | 6734 | 66 | 100.0% | 158 | 87.3% | 5 | 100.0% |
| I/O and process | 6813 | 770 | 93.4% | 1040 | 78.2% | 97 | 92.8% |
| child processes (lib/subprocess.py) | 7764 | 461 | 70.7% | 520 | 47.1% | 52 | 76.9% |
| exceptions: table-driven unwinding (the Itanium C++ ABI's) | 8373 | 322 | 93.2% | 376 | 75.3% | 61 | 98.4% |
| the time module: clocks and sleep | 8842 | 51 | 98.0% | 50 | 48.0% | 11 | 90.9% |
| select: a POSIX integer-descriptor subset | 8902 | 73 | 87.7% | 62 | 71.0% | 2 | 100.0% |
| the errno module: the platform's error numbers | 8982 | 4 | 50.0% | 4 | 75.0% | 1 | 100.0% |
| temporary directories: tempfile.mkdtemp, os.remove, os.rmdir | 9258 | 302 | 93.0% | 406 | 67.5% | 35 | 97.1% |
| tables | 9601 | 117 | 99.1% | 116 | 84.5% | 23 | 95.7% |
