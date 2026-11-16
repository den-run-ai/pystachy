# Stored typed interface costs

This runner compares four representations of the same integer iterator workload:
ordinary function specialization, the explicitly stored `TypedIterator[int]` from
the [tutorial](../../examples/typed_iterator/README.md), a native
[protocol interface](../../docs/language/typing.md#protocols-and-stored-interfaces), and a
closed union of two concrete iterator classes. The union control runs only for two
implementations.

Each generated source has independent concrete iterator classes and consumer
functions. Every consumer uses every implementation. The specialized variant leaves
its parameter unannotated; the stored variant takes `TypedIterator[int]`; the native
variant takes `IntCursor`, a `Protocol` declaring `__next__(self) -> int`; the union
variant takes `Cursor0 | Cursor1`. All perform the same ordered modular checksum,
with `__next__` calls and `StopIteration` handling. This explicit method call also
keeps the union control independent of broader builtin `iter` support for unions.

Long streams expose per-item dispatch costs. One-item streams expose construction,
one successful call and exhaustion together. The latter are not allocation-only
timings. Increasing the implementation and consumer counts shows the cost of
specializing each consumer versus sharing its typed body. The adapter factories
still specialize for each concrete source; the benchmark uses `int_iterator` so
the same runner can also measure the original prototype.

## Run

Use the pinned Python and LLVM setup from [installation](../../docs/install.md).
The output directory must not exist. Source checkouts must remain unchanged while
the runner executes; it checks compiler, runtime, library and adapter manifests.

```sh
python3.13 bench/typed_interfaces/run.py \
  --checkout . --output /tmp/pystachy-interface-costs \
  --shapes 2x1,8x8 --items 2048 --rounds 20 \
  --construction-rounds 500 --samples 5 --build-samples 3
```

`--cpu` selects an available core; on Linux the first available core is the default.
`--jit` adds launch and in-process JIT timings. `--skip-allocations` omits the separate
instrumented builds for a quick smoke run. A small toolchain check is:

```sh
python3.13 bench/typed_interfaces/run.py \
  --output /tmp/pystachy-interface-smoke --shapes 2x1 \
  --items 32 --rounds 2 --construction-rounds 3 \
  --samples 1 --build-samples 1 --skip-allocations
```

## Read the report

`report.json` records the compiler revision and source hashes, generated inputs,
Python/LLVM/platform/CPU, exact commands, and every sample. CPython establishes the
checksum for each workload, all representations must agree, and every native run
checks it. The runner rotates variant order across samples on one pinned core.
Shared-host contention can still make small timing differences inconclusive.

Frontend and complete AOT build times are separate. Compiler timings use the
CPython-hosted compiler. Each variant's initial build starts with an empty private
runtime cache; subsequent build samples use that variant's warm cache. Execution
reports process wall time and workload time separately. Generated LLVM size,
consumer body counts, static indirect calls and executable bytes describe code
growth; they are not runtime operation counts. LLVM may inline or merge bodies.

Allocation runs rebuild with `PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA` and separate
caches, after the uninstrumented timings. Their C GC counters report requests and
requested bytes before allocator rounding, including process initialization and
shutdown. Compare paired representations and divide differences by the recorded
iterator-construction count when appropriate. Foreign allocations and JIT fast
allocation paths are excluded. These counts are not live bytes or process memory.

The workload is synthetic. It measures the tradeoff between code sharing, indirect
calls and wrapper construction; it does not establish a speedup for mypy, parsers
or complete packages.

## Measured prototype costs

The [recorded samples](results/2026-11-15.json) measure the unchanged prototype at
[`059acef8`](https://github.com/den-run-ai/pystachy/commit/059acef8ccc9e9615989c93ac10a215f37df0dfd),
on Linux x86-64, an Intel Xeon Platinum 8573C, CPU 0, CPython 3.13.16 and LLVM
18.1.3. The checkout was clean and its source manifest remained unchanged. These
measurements describe the stored-callable representation already in that commit;
they are not a before/after timing of the later generic-function binding changes.

All five representations matched CPython in both workloads under AOT and JIT.
The table reports three warm build samples and pre-link program LLVM. Runtime
cache construction is excluded from warm build times; cold builds took 22–24 s.

| Implementations × consumers | Representation | Consumer bodies | LLVM lines | Executable bytes | Median warm AOT build, s |
|---|---|---:|---:|---:|---:|
| 2 × 1 | Specialized | 2 | 545 | 99,584 | 0.590 |
| 2 × 1 | Stored | 1 | 749 | 104,136 | 0.532 |
| 2 × 1 | Union | 1 | 496 | 99,712 | 0.489 |
| 8 × 8 | Specialized | 64 | 6,691 | 136,480 | 2.128 |
| 8 × 8 | Stored | 8 | 3,384 | 121,696 | 0.876 |

At 8 × 8, sharing consumer bodies reduced code size and build time. With only two
implementations and one consumer, the stored wrapper increased program LLVM and
executable size. The two-class union was smaller in that bounded case. The data
therefore supports choosing a boundary based on consumer and implementation counts.

Long-stream runs used 2,048 items per iterator and 20 rounds. Values below are
five-sample workload medians, with minimum–maximum in parentheses, excluding
process startup. Runtime differences overlap the observed variation; these runs
establish no execution speed improvement for stored interfaces.

| Shape and representation | AOT, ms | JIT, ms |
|---|---:|---:|
| 2 × 1 specialized | 0.673 (0.600–0.779) | 1.035 (0.945–1.114) |
| 2 × 1 stored | 0.648 (0.559–0.743) | 1.077 (0.994–1.225) |
| 2 × 1 union | 0.593 (0.561–0.811) | 1.123 (0.975–1.324) |
| 8 × 8 specialized | 21.114 (18.637–22.244) | 35.329 (33.551–37.411) |
| 8 × 8 stored | 20.905 (17.725–30.984) | 36.541 (36.082–40.515) |

Separate counted AOT runs show the allocation tradeoff. Each construction workload
also consumes one item and reaches exhaustion; the counters cover that complete
traversal, not only the constructor.

| Shape | Traversals | Specialized C GC requests | Stored C GC requests | Union C GC requests |
|---|---:|---:|---:|---:|
| 2 × 1 | 1,000 | 1,006 | 6,006 | 3,006 |
| 8 × 8 | 32,000 | 32,006 | 192,006 | — |

Stored adaptation added five C GC allocation requests and approximately 64
requested bytes per measured traversal. Byte differences include output formatting
and are approximate. At 8 × 8, the counted collector's peak heap capacity increased
from 3,866,624 to 7,274,496 bytes; this is neither live memory nor process RSS.
These costs justify investigating a cheaper adapter representation, but do not
predict the performance of an unimplemented native interface table.

## Measured native interface costs

The [recorded samples](results/2026-11-16.json) measure all four representations at
[`8eabad6d`](https://github.com/den-run-ai/pystachy/commit/8eabad6d1cd25e6861db0f8a7e9e9eefd359689e)
on Linux x86-64, an Intel Xeon processor at 2.10 GHz, CPU 3, CPython 3.13.18 (not the pinned
3.13.16) and LLVM 18.1.3. The checkout was clean and its source manifest remained unchanged.
Other cores built the compiler during the run, so timings come from a shared host. All seven
variants matched CPython in both workloads under AOT and JIT. Cold builds took 15–17 s.

| Implementations × consumers | Representation | Consumer bodies | LLVM lines | Executable bytes | Median warm AOT build, s |
|---|---|---:|---:|---:|---:|
| 2 × 1 | Specialized | 2 | 545 | 99,728 | 0.302 |
| 2 × 1 | Stored adapter | 1 | 752 | 104,280 | 0.353 |
| 2 × 1 | Native protocol | 1 | 561 | 104,312 | 0.314 |
| 2 × 1 | Union | 1 | 496 | 99,864 | 0.371 |
| 8 × 8 | Specialized | 64 | 6,691 | 136,624 | 1.579 |
| 8 × 8 | Stored adapter | 8 | 3,387 | 121,840 | 0.619 |
| 8 × 8 | Native protocol | 8 | 2,720 | 121,416 | 0.642 |

The native protocol shares consumer bodies as the stored adapter does, with 20% fewer program
LLVM lines at 8 × 8: its tables replace the adapter's wrapper class and closures. With two
implementations and one consumer, it stays larger than specialization or the two-class union.

Long-stream runs used 2,048 items per iterator and 20 rounds; values are five-sample workload
medians in milliseconds, with minimum–maximum in parentheses.

| Shape and representation | AOT, ms | JIT, ms |
|---|---:|---:|
| 2 × 1 specialized | 0.473 (0.467–0.550) | 0.948 (0.820–0.984) |
| 2 × 1 stored adapter | 0.555 (0.522–0.632) | 0.935 (0.897–1.130) |
| 2 × 1 native protocol | 0.554 (0.515–0.586) | 0.870 (0.860–0.915) |
| 2 × 1 union | 0.548 (0.492–0.595) | 0.922 (0.857–1.002) |
| 8 × 8 specialized | 16.404 (15.646–19.063) | 29.261 (28.518–33.092) |
| 8 × 8 stored adapter | 16.633 (15.695–17.407) | 31.694 (29.216–38.079) |
| 8 × 8 native protocol | 16.628 (16.319–17.254) | 28.876 (28.485–30.927) |

The ranges overlap except at 2 × 1 AOT, where specialization's direct calls were faster.
These runs establish no execution speed improvement for either stored representation.

| Shape | Traversals | Specialized C GC requests | Stored adapter | Native protocol | Union |
|---|---:|---:|---:|---:|---:|
| 2 × 1 | 1,000 | 1,006 | 6,006 | 3,006 | 3,006 |
| 8 × 8 | 32,000 | 32,006 | 192,006 | 96,006 | — |

Each native traversal makes two more C GC requests and about 40 more requested bytes than
specialization; the adapter makes five more and about 64 bytes. One of the two is the 16-byte
box of the traversal's conversion; the two-class union's traversals make the same count, and
these counters do not attribute the other request. At 8 × 8 the counted
collector's peak heap capacity was 3,866,624 bytes specialized, 5,701,632 native and 7,274,496
with the adapter; this is neither live memory nor process RSS.
