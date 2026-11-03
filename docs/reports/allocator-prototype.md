# Allocator prototype: a page heap for the collector, and the JIT's allocation fast path

Date: 2 November 2026 (UTC). Baseline: main
[`ec442a2`](https://github.com/den-run-ai/pystachy/commit/ec442a20927f7d2968db5ce554d8ba39aff503bd).
Branch: `claude/intelligent-faraday-gfw8bc`.

## Question and scope

Would a general-purpose allocator such as [mimalloc](https://github.com/microsoft/mimalloc) v3
make Pystachy's native code faster or smaller, and which allocator work pays off in a runtime
whose heap belongs to a conservative, non-moving mark-and-sweep collector?

The prototype stays inside the collector's contract: the same size classes, page map, roots and
`PYSTACHY_GC*` behaviour, no new dependency. Generational collection
([#715](https://github.com/den-run-ai/pystachy/issues/715)), escape analysis
([#1017](https://github.com/den-run-ai/pystachy/issues/1017)) and threads are out of scope.

## Summary

- **A drop-in `malloc` does not help.** The collector already allocates every small object
  itself; the C allocator only supplied its 1 MiB arenas and its large objects. Through
  `LD_PRELOAD`, mimalloc v3.6.1 was slower than glibc on 9 of 12 workloads (up to 5.4× on
  #615's program) and jemalloc 5.3 7 to 9 times slower on large-string churn. Both general
  allocators return the memory a sweep frees to the system, and the next cycle faults it back in
  and clears it again.
- **What costs is clearing and page faults.** In #127's tokenizer loop, `memset` was 56% of the
  instructions and the copies the program asked for 39%: `calloc` cleared each large string,
  plus a spare page for alignment, and the slices then overwrote it.
- **The prototype** maps the collector's pages itself (a page heap of 2 MiB regions with
  used/dirty bitmaps), keeps the pages a cycle frees for the next one, clears only dirty pages and
  never the bytes a new string's maker writes anyway, and gives the JIT tier the allocator fast
  path that AOT builds get by inlining. `PYSTACHY_GC_MIN` sets the 32 MiB window (#650).
- **Results** (medians of five interleaved runs, one pinned core): #127's string loops 24 to
  38% faster in both tiers with up to 94% fewer page faults, a JIT loop of small objects 19%
  faster, #650's object graph 6 to 8%, the rest within noise; peak RSS within 1 MiB except
  `words` (+4 MiB) and `dictcount` (+2 MiB). Outputs are identical.

## 1. Drop-in C allocators

Main `ec442a2`, AOT, with `LD_PRELOAD` of each library (`bench/allocator/run.py`'s `+LIB`).
The program's own timer, median of three, pinned to one core; peak RSS from `getrusage`.

| Workload | glibc 2.39 | mimalloc 3.6.1 | mimalloc, no purge | jemalloc 5.3 | RSS glibc / mimalloc |
|---|---:|---:|---:|---:|---:|
| `nodes` (#650) | 0.349 s | 0.600 s | 0.331 s | 0.568 s | 41 / 69 MiB |
| `slice20k` (#127) | 0.130 | 0.146 | 0.131 | 1.188 | 16 / 17 |
| `slice4k` (#127) | 0.091 | 0.323 | 0.087 | 0.118 | 37 / 67 |
| `chevron` (#127) | 0.493 | 0.428 | 0.416 | 3.489 | 16 / 23 |
| `peak` (#615) | 0.665 | 3.615 | 0.398 | 0.603 | 681 / 767 |
| `strbuild` | 0.302 | 0.314 | 0.349 | 0.341 | 36 / 53 |
| `lists` | 0.217 | 0.349 | 0.214 | 0.350 | 39 / 67 |
| `json_repair` | 0.167 | 0.171 | 0.175 | 0.167 | 35 / 53 |
| `words` (wall) | 0.100 | 0.134 | 0.082 | 0.109 | 54 / 81 |
| `dictcount` (wall) | 0.209 | 0.161 | 0.164 | 0.200 | 35 / 63 |
| `dynany_graph` | 0.040 | 0.152 | 0.034 | 0.040 | 36 / 49 |
| microGPT, 150 steps | 1.571 | 1.943 | 1.666 | 1.897 | 62 / 87 |

mimalloc with `MIMALLOC_PURGE_DELAY=-1` keeps freed pages and was the fastest on #615's program,
`words` and `dictcount`, which is where the prototype's design comes from, but its peak RSS was
16 to 85% higher. Its default purging, with the transparent huge pages it requests, made #615's
program 5.4 times slower. Google's TCMalloc was not measured: it builds with Bazel only, and its
per-CPU caches serve concurrent allocation, which Pystachy's single-threaded runtime does not do.

## 2. What the prototype changes

All in [runtime.c](../../runtime.c)'s memory section, except the JIT fast path in
[lower_module.py](../../src/pystachy_compiler/lower_module.py) and
[driver.py](../../src/pystachy_compiler/driver.py).

- **Page heap.** Chunks of small objects (64 KiB) and large objects take runs of whole pages from
  2 MiB regions the runtime maps aligned (`map_pages`), not from `calloc`; an object larger than a
  region gets a mapping of its own. A large object no longer carries a spare alignment page. Each
  region has bitmaps of used and dirty pages. Only sweeps free pages, so a sweep rebuilds the
  coalesced free runs from the bitmaps; between sweeps an allocation takes the shortest run that
  fits, preferring runs with dirty pages (already resident) over clean ones (a page fault and the
  kernel's clearing each).
- **Retention and purging.** A sweep keeps as many dirty free pages as the next cycle may need
  (its allocation window and half again; the window is the larger of 32 MiB and the live bytes,
  so a large heap keeps correspondingly more) and purges the rest with `MADV_DONTNEED` (elsewhere a
  fresh mapping over them): pages idle for a whole cycle first, then regions that are all free
  (unmapped), then other runs. Freed own mappings count against the same budget, newest kept
  first, for a large object of up to a quarter fewer pages. `str_trim` gives a trimmed string's
  pages back to the page heap.
- **Clearing only what needs it.** A zeroed allocation clears only the dirty pages it takes.
  `gc_raw` hands out pointer-free memory without clearing, for callers that write every byte
  they read: new strings (`pys_str`, concatenation, `str_grow`, `*`, stepped slices) and `Buf`
  data. Pointer-free slots of more than 136 bytes are no longer cleared by the sweep; an
  allocation clears the bytes it asks for (`LAZY`). Scanned slots are still cleared by the
  sweep: a stale pointer in a dead slot that a conservative root reaches would retain garbage.
- **JIT fast path.** The JIT tier never inlines the shared runtime, so every allocation was a call
  into it. The driver now puts the allocator's fast path in the program's module (`JITFAST`, in
  `lower_module.py`, where LLVM module templates belong):
  `pys_new` and `pys_alloc` stay `noinline` calls through the cleanup pipeline, so allocation
  elision still sees `pys_new`'s marked calls, and a last `forceattrs,always-inline` step inlines
  the calls left: a pop of the runtime's free list (`pys_fl`, a constant slot once inlined), and
  `pys_gc_slow` for everything else. Inlining `pys_alloc` before the cleanup instead made `nodes`
  about 10% slower in the JIT, as its larger bodies changed the inliner's decisions.
- **`PYSTACHY_GC_MIN=N`** allocates at least N MiB between collections instead of 32 (#650);
  `tools/aotprobe.py` checks it.

## 3. Results

`python3 -I bench/allocator/run.py --variant main=…:… --variant proto=./pystachy:. --rounds 5
--cpu 3 --tiers aot,jit --names names.txt`: medians of five rounds, the variants interleaved in
rotating order, pinned to one core of a shared 4-vCPU Intel Xeon at 2.10 GHz (Linux 6.18, glibc
2.39, LLVM 18.1.3). Seconds of each program's own loop (wall time where a workload has no timer);
peak RSS and minor page faults of the whole process (the JIT's include LLVM's).

| Workload | AOT main | AOT proto | change | JIT main | JIT proto | change | AOT peak RSS main / proto | AOT page faults main / proto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `nodes` (#650) | 0.338 s | 0.317 s | -6% | 0.381 s | 0.351 s | -8% | 41 / 40 MiB | 12,985 / 9,915 |
| `vectors` | 0.059 s | 0.056 s | -5% | 0.061 s | 0.050 s | -19% | 38 / 38 MiB | 10,312 / 9,427 |
| `slice20k` (#127) | 0.134 s | 0.085 s | -36% | 0.134 s | 0.086 s | -36% | 17 / 17 MiB | 1,436 / 1,227 |
| `slice4k` (#127) | 0.090 s | 0.068 s | -25% | 0.106 s | 0.074 s | -30% | 37 / 36 MiB | 17,858 / 8,940 |
| `chevron` (#127) | 0.488 s | 0.302 s | -38% | 0.499 s | 0.311 s | -38% | 17 / 17 MiB | 47,577 / 2,673 |
| `peak` (#615) | 0.591 s | 0.585 s | -1% | 0.598 s | 0.589 s | -1% | 681 / 679 MiB | 173,948 / 173,533 |
| `strbuild` | 0.294 s | 0.289 s | -2% | 0.291 s | 0.277 s | -5% | 36 / 36 MiB | 10,636 / 8,876 |
| `lists` | 0.202 s | 0.193 s | -4% | 0.202 s | 0.213 s | +5% | 39 / 38 MiB | 10,150 / 9,439 |
| `json_repair` | 0.153 s | 0.155 s | +2% | 0.184 s | 0.183 s | -1% | 35 / 36 MiB | 9,663 / 8,716 |
| `words` (wall) | 0.099 s | 0.098 s | -2% | 0.163 s | 0.159 s | -3% | 54 / 58 MiB | 16,526 / 15,466 |
| `dictcount` (wall) | 0.169 s | 0.175 s | +4% | 0.257 s | 0.241 s | -6% | 35 / 37 MiB | 10,155 / 9,514 |
| `dynany_graph` | 0.042 s | 0.040 s | -4% | 0.043 s | 0.044 s | +0% | 35 / 36 MiB | 8,694 / 8,700 |
| microGPT, 150 steps | 1.527 s | 1.659 s | +9% | 1.686 s | 1.722 s | +2% | 62 / 62 MiB | 29,853 / 22,214 |

Every output agreed across variants and tiers, and the allocator workloads print what CPython
prints. On this shared host a single run varies by about ±6%: microGPT's AOT row above did not
repeat in ten further paired runs of the two executables, whose median ratio was 0.994 (0.91 to
1.06), with the same 71 collections, 14.7 MiB live at the last and GC time within 3%. The
changes outside noise are #127's string loops (24 to 38% faster, with 15 to 94% fewer page
faults), `vectors` in the JIT (19%: its objects hold no reference, so the JIT's allocations are
`pys_new`'s, now inlined) and `nodes` (6 to 8%, a quarter fewer page faults). Peak RSS is the
same within 1 MiB except `words` (+4 MiB) and `dictcount` (+2 MiB), presumably the free pages
their sweeps keep for the next cycle (not measured separately).

The allocation window that `PYSTACHY_GC_MIN` sets trades memory for collections. microGPT
(AOT, this runtime, median of three):

| `PYSTACHY_GC_MIN` | Collections | GC time | Training (150 steps) | Peak RSS |
|---:|---:|---:|---:|---:|
| 32 (default) | 71 | 590 ms | 1.707 s | 62 MiB |
| 64 | 35 | 310 ms | 1.686 s | 97 MiB |
| 128 | 17 | 150 ms | 1.574 s | 164 MiB |

Collection time falls with the window, but the program itself runs slower on the larger heap,
so 128 MiB saves 8% of the run for 2.6 times the memory (#650 measured 22% for 100 steps with
the previous allocator, on another host). The default stays 32 MiB.

## 4. What did not work

- **Transparent huge pages** (`MADV_HUGEPAGE` on regions): #615's program peaked at 932 MiB of
  RSS instead of 679 MiB, as partly used regions became resident 2 MiB at a time; smaller heaps
  ran no faster. Left off.
- **Purging pages idle for one cycle**, the time-based decay of general allocators, counted in
  collections: #127's loop collects every 4 MiB of large strings (#658), and it refaulted the
  same pages each cycle, 320,000 page faults and twice main's time. Purging is driven by the
  retention budget instead, idle pages first.
- **Freed own mappings kept for one cycle.** `nodes` grows a list to a 2 MiB array (513 pages,
  one more than a region) three or four times a cycle, and each cycle with one more than the last
  mapped a fresh array: 21 new mappings, about 10,800 page faults, more than main's 12,900 in
  all. Kept within the retention budget instead, 4 mappings serve 196 arrays and the run takes
  9,800 faults.
- **Large objects from the high end of free runs**, chunks from the low end, to keep long runs
  free of surviving chunks: no page-fault count measured here changed (`nodes`, `lists`, `peak`,
  microGPT). The best fit already prefers dirty runs, and each sweep coalesces them again.
- **A larger collector frame.** Inlined into `collect`, the purge step's 2 KiB array of runs made
  `collect`'s frame 2,120 bytes, and marking scans the frames above `mark_roots`. Its stale words
  kept dead lists alive: microGPT's last collection kept 20.6 MiB instead of 14.7, and training
  ran 6% slower. `pages_settle` is out of line now, and the page heap's calls that return results
  through memory (`chunk_new`, `big_new`) run in frames of their own after any collection, so
  `gc_slow` and `collect` have main's frame sizes (24 and 72 bytes on x86-64).

## 5. Validation

On the final tree, Linux x86-64, LLVM 18.1.3, CPython 3.13.18 for the controllers (recordings
are 3.13.16's):

| Check | Result |
|---|---|
| `make` (bootstrap) | the compiler's IR and `runtime.py`'s each reach their fixed point (stage 1 = 2 = 3) |
| `tests/run.sh ./pystachy "jit aot"`, the whole corpus | 6,252 passed, 0 failed |
| The same with `PYSTACHY_GC_STRESS_PROGRAM=1` (a collection at every program allocation) on `strings`, `containers`, `runtime`, `io`, `classes`, `optimizations`, `generators` | 624 cases, 1,248 passed, 0 failed |
| `make listprobe eqprobe fileprobe selectprobe weakrefprobe boxprobe dictprobe unicodeprobe bytescanprobe` (each also with `PYSTACHY_GC_STRESS=1`) | passed |
| `make jitprobe aotprobe` (hosted and native compilers) | passed; 4 collections in the default window, 136 with `PYSTACHY_GC_MIN=1`, 0 with 256 |
| `make check-ir` | 2,201 programs |
| `tools/test_runtime_*.py` (64 tests, including the ASan and UBSan runtime builds and the page heap's below) and `tools/test_*verif*.py` | passed |
| `make lint check-runtime typecheck` | passed |
| `make check-recordings` | 1,998 of 2,000: `sys_version_info` and `upstream_sys_version_info` print this container's CPython 3.13.18, not the pinned 3.13.16 |
| `tools/irsame.sh` with main's compiler and this one, both reading one library home | 3,985 programs: the same IR, messages and exit status (each with its own home, 194 differed only in the library path that `ImportError` messages embed) |

`tools/test_runtime_pages.py` now compiles the page heap's purge with simulated 4, 16 and 64 KiB
kernel pages for a string in a region and in its own mapping; its negative control, a purge that
rounds to the collector's 4 KiB pages, fails on 64 KiB pages. `tools/test_runtime_pageheap.py`
replays seeded random cycles of chunks and large objects (in regions and in mappings of their own,
some of them strs that `str_trim` trims), sweeps and budgets through the page heap's own
functions, against a model of the object on each page: no two live objects share a page; zeroed
allocations, chunks taken as clean and free pages marked clean read zero; live objects keep their
bytes; the bitmaps, free runs and heap count agree with the model, a reused mapping counted in
full; and the free memory a sweep keeps fits its budget. Its negative controls, freed pages left
marked clean, a split run that overlaps its allocation and a reused trimmed mapping counted short,
fail. `tools/test_runtime_jitfast.py` compiles `lower_module.py`'s `JITFAST` beside `runtime.c`'s own
`gc_alloc` and `cls()` and checks, for every size up to 300 bytes, that both return the same slot
or make the same slow call; its negative control shifts the size class by one.
`tools/test_runtime_frames.py` compiles `runtime.c` with `-fstack-usage` and bounds the frames that
marking scans (`gc_slow` with `refill` inlined, `collect`, `mark_roots`: 72, 120 and 24 bytes) at
256 bytes; with `pages_settle` inlined, `collect`'s exceeds it. `tools/jitprobe.py` expects the
padded object's allocation as the fast path's slow call, `pys_gc_slow(i64 56, i64 0)`.
Not run locally: the full `make verify` matrix (sanitizer and Python-free rebuilds, all GC shards,
`gc-self`), Linux ARM64 and macOS (whose purge maps fresh pages over the old instead of
`MADV_DONTNEED`). The pull request's CI runs the matrix on Linux x86-64 and ARM64, and the
bootstrap on macOS.

## 6. Follow-ups

- **Arrays written in full.** `[x] * n`, list growth and copies of pointer-free lists clear new
  storage the next statement overwrites (#650, #649): `gc_raw` with an explicit fill would
  remove a pass, after an audit of the readers of a list's spare capacity.
- **Pacing.** The window stays max(32 MiB, live). `PYSTACHY_GC_MIN` makes a larger one a
  setting; a pacer that widens the window while collections take a large share of run time
  (GOGC-like) would have to weigh the slower mutator and higher peak RSS measured above (#615).
- **Retention on large heaps.** The budget follows the window, so a program with a large live set
  keeps up to 1.5 times it in free pages after a sweep, where main returned dead large objects at
  once. The next cycle allocates up to the window anyway, so the peak moves less (#615's 128 MiB
  program peaked at 679 MiB against 681), but RSS stays near the peak between collections. A cap,
  or a time-based decay as mimalloc's purge delay, would bound it; it needs a large-heap workload
  to measure.
- **Runtime globals in AOT builds.** `pys_fl` is exported for the JIT tier's fast path, so an AOT
  build, which links the runtime without internalizing it, cannot prove that external calls leave
  it unchanged. Internalizing the runtime's globals there would restore that for all of them; the
  AOT results above include the cost.
- **mimalloc** remains an option for the C allocator the runtime still uses (`malloc` for the
  page map, tables and file buffers), not for the heap, and only if a workload shows a cost there.

## Provenance

The prototype, its measurements and this report were prepared with an AI coding assistant
(Claude); measurements are from the assistant's runs in this environment and are advisory.
