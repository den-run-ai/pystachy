# Character-offset identity in JSON repair

Compared #1650 (`a0137c9723ef`) with [`cabc03f92812`](https://github.com/den-run-ai/pystachy/commit/cabc03f92812cd1f66c3e51d5cbb9bfe61dc92f9) on Linux x86-64, AMD EPYC
9V74, LLVM 18.1.3 and CPython 3.13.16. Both used the CPython-hosted compiler,
checked typed IR and AOT tier 2. Every pair matched on all result witnesses.
The core repair fixture went from 403 to 301 LLVM call sites to
`pys_dyn_int_box`; the scanner lost four pointer fields. An explicit raw-decode
index still calls `seek_char` and retains the stored position on error.

## Allocation requests

Whole-process counters include program initialization, initial validation,
the measured batch and exit. Each scaling run below performs **11 repairs**,
one during setup and ten in its measured batch. The facade uses four inputs
per round and performs 1,604 repairs. Peak heap is the allocator's high water
mark. Neither the counts nor the peak measure retained bytes after collection.

| Probe and arguments | GC allocation requests, before → after | Requested bytes, before → after | Peak heap bytes, before → after |
|---|---:|---:|---:|
| scaling `raw-prefix 2000 10 1 0` | 44,182 → 941 | 1,203,563 → 553,981 | 2,883,584 → 2,162,688 |
| scaling `unicode 2000 10 1 0` | 44,333 → 1,081 | 1,211,945 → 562,549 | 2,949,120 → 2,228,224 |
| scaling `valid 2000 10 1 0` | 652 → 652 | 94,670 → 94,317 | 1,376,256 → 1,376,256 |
| facade `valid 400 1 0` | 51,479 → 51,479 | 3,327,394 → 3,276,068 | 4,653,056 → 4,587,520 |
| facade `malformed 400 1 0` | 191,867 → 191,867 | 9,255,291 → 9,152,637 | 11,534,336 → 11,272,192 |

The `raw-prefix` input omits the opening object brace. The port inserts it, then
successfully raw-decodes the 6,008-character candidate with its 6,000-character
Unicode value intact. The `unicode` input takes the trailing-comma error path.
The two checkout paths had different lengths, adding a few bytes to process
startup strings.

## Throughput

Uninstrumented AOT binaries ran in nine alternating process pairs per case on a
shared host. Times are medians in milliseconds per timed batch, excluding startup
and validation. The ratio column is the median of individual after/before
pairs. Each facade round processes four repairs, each scaling round one.

| Run | Probe and arguments | Before ms | After ms | Paired ratio | Faster pairs |
|---|---|---:|---:|---:|---:|
| Initial | facade `valid 30000 3 1` | 201.237 | 219.405 | 1.065 | 1/9 |
| Initial | facade `malformed 2000 3 1` | 127.225 | 153.599 | 1.207 | 2/9 |
| Initial | scaling `valid 4000 200 3 1` | 3.667 | 3.719 | 1.035 | 4/9 |
| Initial | scaling `unicode 2000 30 3 1` | 3.991 | 3.014 | 0.747 | 8/9 |
| Repeat | facade `valid 40000 1 0` | 169.379 | 163.824 | 1.002 | 4/9 |
| Repeat | facade `malformed 4500 1 0` | 183.781 | 184.962 | 0.930 | 5/9 |
| Repeat | scaling `valid 4000 14000 1 0` | 161.658 | 152.922 | 0.977 | 5/9 |
| Repeat | scaling `unicode 2000 950 1 0` | 147.452 | 99.205 | 0.674 | 9/9 |
| Successful prefix | scaling `raw-prefix 2000 950 1 0` | 143.374 | 69.066 | 0.444 | 9/9 |

The initial run used each process's median of three batches after one warmup.
The facade ran on CPU 0 and scaling on CPU 8. The repeat pinned all binaries to
CPU 8 and randomized case order per round (seed 257). The earlier small-record
slowdown did not repeat. Both Unicode workloads improved across all repeat
pairs. The initial and repeat facade candidate emitted byte-identical LLVM to
the checked change. The successful-prefix timing and the three scaling
allocation rows used the expanded scaling probe and the checked compiler.

## Reproduce

Use `bench/json_repair/facade.py` and this branch's `bench/json_repair/scaling.py`
for both checkouts. Set `probe` to the absolute path of each input and build in
each checkout with the same Python and LLVM. For the initial and repeat scaling
timings, use the original `scaling.py` from #1650.

```sh
PYSTACHY_IRCHECK=1 PYSTACHY_PATH="$PWD/ports" python3.13 pystachy.py build "$probe" -o "$output"
PYSTACHY_IRCHECK=1 PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA PYSTACHY_PATH="$PWD/ports" \
  python3.13 pystachy.py build "$probe" -o "$output-counted"
"$output-counted" raw-prefix 2000 10 1 0
taskset -c "$cpu" "$output" raw-prefix 2000 950 1 0
```

Repeat the commands with the arguments above. Alternate before/after and
after/before process order for nine pairs. Compare the `witness` lines for
scaling and the `outputs` and `witness` lines for the facade. The counted
binaries write the `pystachy-data` JSON line to stderr.
